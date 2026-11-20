# Routing pipeline: door-to-door minutes from real timetables

This package answers one question for the engine: *"if a student leaves home X to be at building B by 9:55 on a
Tuesday, when do they leave, and how is the trip made up?"* It also answers the reverse question for the trip
home. It combines the **UM Transit and AAATA (TheRide) GTFS timetables** with a **pedestrian graph from Overture
Maps / OpenStreetMap**. It implements `TravelTimeProvider` (`ledger/pipeline/provider.py`).

```
make data            # = python3 -m ledger.pipeline.build   (~20 s, writes data/artifacts/)
python3 -m pytest tests/pipeline
```

| Module | Role |
|---|---|
| `feeds.py` | Finds the feeds, applies the selection policy and maps each day to a service date |
| `gtfs.py` | Parses GTFS into a time-sorted connection array per day type; builds the stop-to-stop footpaths |
| `walkgraph.py` | Builds the Overture walk and bike graph; KD-tree snapping; cached Dijkstra; `nearby_stops` |
| `csa.py` | Forward and backward Connection Scan; two-label footpaths; rebuilds journeys from labels |
| `build.py` | Builds the artifacts (graph, timetable, precomputed labels per building) and `manifest.json` |
| `transit.py` | `load_provider()`: the runtime provider with caching and an LRU |

## 1. Walking network
- **Source.** Overture `segment` features of subtype `road`, split at connectors (intersections). Pieces are
  densified to edges of 40 m or less, so a home or stop snaps within about 20 m along the street.
- **Kept.** Footways, sidewalks, crossings, paths, steps, residential and service roads, driveways and parking
  aisles.
- **Removed.** Motorways, and segments that unconditionally deny pedestrians.
- **Size.** About 100k nodes and 120k edges. Only the largest connected component is used (98k nodes).
- **Bike graph.** The same graph without steps and without segments that deny bicycles. Speed is 4.2 m/s, plus
  2 min to lock and unlock.
- **Walking speed.** 1.34 m/s (set with `LEDGER_WALK_MPS`).
- **Sanity check.** Shapiro Library (UgLi) to Beyster (BBB) is 3,588 m on foot, a 44.6 min walk. The straight
  line is 2.6 km.

## 2. Timetable
- **What a connection is.** Every pair of consecutive stops on a trip is one connection
  `(dep_stop, arr_stop, dep_t, arr_t, trip, board/alight flags)`. Connections are sorted by departure time.
- **What the parser handles.**
  - Exceptions in `calendar_dates.txt`.
  - Times past 24:00 (BB runs until about 02:28).
  - `frequencies.txt`, expanded into explicit trips.
  - Blank times, interpolated by `shape_dist_traveled`, or by stop order when that is missing.
  - Stations: only stops with `location_type` 0 can be boarded.
  - `pickup_type` and `drop_off_type` = 1.
  - Charter and test routes, which are dropped.
  - Namespaced ids (`UM:…`, `AA:…`), because the two agencies reuse stop ids.
- **Footpaths.**
  - Any two stops within **300 m of walking on the network** are linked, including **UM↔AAATA transfers**
    (500 directed cross-agency links).
  - If a stop is off the graph, the length falls back to straight-line distance × 1.3.
  - `transfers.txt` type 2 sets minimum transfer times (the 17 AAATA rows at Blake Transit Center are applied).
    Type 3 forbids a transfer.
- **Day types.** Each schedule day M…U is mapped to a date in the chosen week. Days whose connection arrays are
  identical (compared by hash) are merged. With the live feeds this gives **MTWR, F, S, U**. With the 2021-22 UM
  feed, Monday is its own type because it has its own service id.

## 3. Connection Scan Algorithm (CSA)
CSA (Dibbelt et al., 2013/2018) makes one pass over the time-sorted connections. A connection is usable if
either:
- its trip has already been boarded, or
- one can stand at its departure stop by its departure time.

**Backward scan (arrive-by).** For one target and deadline, it scans connections in *descending* order. It
produces `LV[s]`, the latest time one can board at stop `s` and still arrive in time. It produces this for
**every stop at once**. So **one backward scan per (building, day type, deadline) serves every possible home**. A
query from any origin then costs only `max over the 20 nearest stops s of (LV[s] − walk(origin, s))`. That is
O(k) work and needs no graph search at query time.

**Forward scan (depart-at).** It does the same for return trips: the earliest arrival at every stop, leaving the
building at time t.

**Two-label footpath fix.** Footpaths are not transitively closed, so a naive CSA can chain walks:
stop → stop → stop. To prevent this, each stop keeps two labels:
- `EV` / `LV`: arrived by vehicle, or board here.
- `EA` / `LA`: available to board after at most one walk.

Footpaths are relaxed only from vehicle labels. The tests check this exactly against an independent
time-expanded Dijkstra that has the same semantics.

**Journey reconstruction without parent pointers.** Only `LV` (or `EV`) is stored. `LA` (or `EA`) is re-derived
exactly from it in O(#footpaths). A greedy trace over this label field rebuilds the journey:
- **Backward:** board the earliest valid departure, then get off where the final walk works.
- **Forward:** board as close to the origin as possible.

The trace returns the routes, stops, waits and walks. This is what keeps the precomputed table small: 2 bytes per
(stop, slot).

**Complexity and measured timings** (4-vCPU container, live feeds, weekday 70,325 connections, 4 h scan window):

| Operation | Time |
|---|---|
| One scan, numba JIT | **0.11 ms** |
| One scan, pure Python (identical code on lists, when numba is missing) | 3.3–3.9 ms |
| Full build: graph, GTFS, 92,872 precomputed scans | **20 s**; artifacts 58 MB |
| `trip_arrive_by` to a building, first call (2,000 queries) | **0.49 ms/query** |
| `trip_arrive_by`, cached | **0.03 ms/query** |
| `trip_depart_at` from a building (return trip), uncached | 0.44 ms/query |
| Point-to-point query (destination is not a building) | about 0.2 ms with numba (one live scan), then cached |

## 4. Precomputed labels and the slot rule
- For each of 47 buildings × 4 day types × 247 slots (every 5 min from 06:00 to 26:30), the build stores the
  backward `LV` and the forward `EV` as uint16 second offsets from the slot time.
- **Arrive-by deadline t.**
  - The query uses the labels of slot `floor(t)`. This is conservative: the journey arrives by the slot time,
    which is at or before t.
  - If t falls between slots, journeys from the next slot are also traced. They are used if they verifiably
    arrive by t. This usually gives the exact answer.
- **Depart-at time d.**
  - The query uses slot `ceil(d)`. The student leaves at d and waits longer at the first stop.
  - It also uses floor-slot journeys whose first boarding is still reachable when leaving at d.
- Times outside the grid, and any point that is not a building, are scanned live and exactly. The results are
  cached by (snapped node, day type, minute).

## 5. Choosing the trip
The provider builds three candidates: walk-only, bus (if allowed) and bike (if allowed).
- **Arrive-by** returns the candidate that leaves **latest**, so a bus is only shown when it actually beats
  walking. Its total is then never above the walking total.
- **Depart-at** returns the candidate that arrives **earliest**.
- A transfer must save at least 2 min to be preferred (`TRANSFER_TIEBREAK_S`). Interlined continuations (the next
  trip of the same route leaving the same stop within 1 min) are shown as one ride.

The returned `Trip` reports these quantities:
- `walk_min`, `wait_min` (at the first stop and at transfers) and `in_vehicle_min`. They add up to `total_min`,
  which equals `arrive_min − depart_min`.
- `arrive_min` is the **actual** arrival. Slack before the deadline is not counted; the engine adds its own
  arrival buffer.
- `outdoor_after_22_min`: walking and waiting minutes between 22:00 and 06:00.
- `legs`, with route short names, agency and stop names.
- `note`, for example "last CN from Michigan Union S. State departs 02:08".

If no bus journey exists, the trip falls back to walking and says so in the note.

## 6. Feed selection policy and honesty labels
The full policy is in `feeds.py` and is recorded in `manifest.json → feeds`.
1. **Live feeds** in `data/raw/gtfs_live/*.zip`. The agency is detected from `agency.txt`.
   - The feed must have full weekday service in an upcoming week. The week with the most weekday trips is chosen.
     This is how Thanksgiving week is skipped.
   - **Current build:** UM `um_gtfs.zip` (S1000100, valid 2026-08-23..2027-01-02) and AAATA `aaata_gtfs.zip`
     (S1000304, valid 2026-11-15..2027-01-23). Both use the **week of Mon 2026-11-30**.
   - Provenance from `RECEIVED_ON.txt`: "provided by team member, downloaded from official URLs, received
     2026-11-20".
2. **Fallbacks**, each labelled in the manifest:
   - AAATA: winter-term 2026 service (week of Mon 2026-03-16), labelled "proxy".
   - UM: the **2021-22 term feed** (week of Mon 2022-02-14), labelled "historical term schedule (2021-22) —
     frequencies may differ". The summer-2026 UM feed is deliberately not used, because it has no weekday
     BB/DD/NX/OS service.
   - Rebuild with the fallbacks: `python3 -m ledger.pipeline.build --live-dir /some/empty/dir`.
3. **Overrides:** `--um-feed/--aaata-feed/--um-week/--aaata-week/--reference-date`, or `LEDGER_FEED_*`,
   `LEDGER_WEEK_*`, `LEDGER_REFERENCE_DATE`, `LEDGER_LIVE_DIR`.

**Last boardable UM departures**, live feed, week of 2026-11-30 (from `manifest.json → late_night`):

| Route | Mon–Thu | Fri | Sat | Sun |
|---|---|---|---|---|
| BB | 02:28 | 03:13 | 03:13 | 02:43 |
| CN | 02:26 | 02:26 | 02:26 | 02:26 |
| CS | 02:28 | 02:28 | 02:28 | 02:28 |
| NW | 02:34 | 03:14 | 03:14 | 02:34 |
| OS | 01:57 | 01:57 | 21:57 | 21:57 |
| WX | 01:14 | 01:14 | — | — |

Routes that stop in the evening on weekdays: DD 19:16, MX 19:45, NES 20:16, WS 19:10, CSX 19:04, NX 13:13.

### How to refresh with live feeds
Put the new zips in `data/raw/gtfs_live/` (any names; the agency is read from `agency.txt`). Optionally update
`RECEIVED_ON.txt`, then run `make data`. Check `data/artifacts/manifest.json → feeds.*.source == "live"` and the
chosen `week_monday`.

## 7. Buildings
`data/campus/buildings.json` lists 47 buildings with the ids the other agents use.
- **Sources.** Coordinates come from Overture Places 2026-11-18; each record's `source` field holds the POI id.
- **Rejected duplicates.** Two bogus Overture duplicates are not used: "Duderstadt Center" at 42.246 and
  "Michigan Union" at 42.286.
- **Moved to the walk network.** Michigan Stadium and Briarwood, whose POI centroids sit inside the building, were
  moved to the nearest point on the walk network (112 m and 91 m). This is recorded.
- **Approximate.** `medsci` and `ioe` have no clean POI and are placed by hand. They are marked "approximate
  (unverified)".
- **Snapping.** Every building snaps to the walk graph within 60 m; the build fails otherwise.

## 8. Tests (`tests/pipeline`, 16 tests, about 7 s)
- Forward CSA equals an independent Dijkstra (EV and EA arrays exactly) on 50 random multi-source queries over a
  sampled 40% subnetwork; the median query reaches 988 stops.
- The backward scan is exact: boarding at `LV[s]` reaches the target, and boarding 1 s later does not (over 400
  checks).
- The numba and pure-Python kernels give identical results.
- Traced journeys respect the timetable, the board and alight flags, and the footpaths.
- Trip invariants hold: `total = arrive − depart`; walk + wait + ride (+ bike) = total; the bus total never
  exceeds the walking total; arrive-by trips never arrive after the deadline.
- Monotonicity holds exactly with the transfer tie-break off. With it on, it holds within 3 tie-break units; the
  observed worst case is 3.8 min.
- Known geography: UgLi→BBB walk is 3.5 km ± 10%. A Tuesday 10:00 trip uses UM BB and takes 22.4 min, against
  44.6 min walking.
- Late night: the last-departure table is printed, and night-exposure accounting is checked on synthetic legs.
- Feed policy, on synthetic GTFS zips: live feeds beat fallbacks; expired live feeds are skipped; Thanksgiving week
  is skipped; overrides work; `RECEIVED_ON` is recorded. GTFS edge cases are covered: times past 24:00, distance
  interpolation, pass-through stops, frequencies, stations, namespacing, charter filtering.
- Performance: ms per query is printed, with an assertion of under 5 ms.

## 9. Limitations (stated, not hidden)
- **Schedule.**
  - No real-time delays, early departures or missed connections; the schedule is taken as exact.
  - Each day type is one representative service date. Exam weeks, breaks and special events differ.
- **Walking.**
  - Walking speed is constant. There is no penalty for weather or slope here; the engine applies the winter
    multiplier.
  - Waits at signalised crossings are ignored. Private or closed paths may be included where OSM tags allow them.
- **Search.**
  - Scans look at most 4 h back or ahead; within Ann Arbor, walking always bounds the useful trip length.
  - At most one footpath between two rides; stops are within 900 m of each end (the 20 nearest).
  - Labels are exact in time but do not track the number of transfers. The 2 min-per-transfer tie-break picks
    among traced candidates, not over all Pareto journeys.
- **Exposure.** Bike legs count as outdoor time only in `bike_min`, not in `outdoor_after_22_min`.
- **Coordinates.** Building coordinates are POI points, not entrances. Two are approximate (see §7).

## Leg geometry (`TripLeg.path`)
Every non-wait leg carries `path: [(lat, lon)]`, Douglas-Peucker-simplified (5 m) and thinned to <= 40 points,
rounded to 1e-5 deg. Bus legs: the trip's stop sequence from boarding to alighting stop (GTFS stop_times order;
interlined continuations are concatenated). Walk/bike legs: the street-network shortest path (scipy Dijkstra
predecessors rooted at the home / building end, LRU-cached, so one search serves all of a home's legs; access and
egress searches are limited to STOP_RADIUS_M + 100 m), or [origin, destination] when the points are not connected.
Walk-only trip geometry is computed only for the chosen trip. Cost: about +0.1 s on a cold 13-listing evaluation,
nothing when warm. Tests: `tests/pipeline/test_leg_paths.py`.
