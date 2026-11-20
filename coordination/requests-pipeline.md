# Requests from the pipeline agent

## 1. Add numba as an optional dependency (pyproject.toml)
**Why.** Numba JIT-compiles the CSA kernels: 0.11 ms per scan instead of 3.3–3.9 ms in pure Python. That takes the
full `make data` (92,872 precomputed scans) from minutes down to about 20 s. Without numba everything still works
and gives identical results, only slower. A test checks that the numba and pure-Python kernels agree.

**Proposed change:**
```toml
[project.optional-dependencies]
fast = ["numba>=0.60"]
```
Alternatively, add `"numba"` to `dependencies`. It is installed in this environment (0.68.1).

## 2. Contract notes for the engine (no schema change needed)
- `Trip.arrive_min` is the **actual** arrival time, which can be earlier than the deadline.
  `total_min = arrive_min - depart_min`. Slack before the deadline is not counted; the engine adds its own
  arrival buffer.
- **Arrive-by** returns the trip that leaves **latest**, with each transfer counting as 2 min.
  **Depart-at** returns the trip that arrives earliest.
- **Use building ids for speed.** Pass `Point.id == Building.id` (from `data/campus/buildings.json`) to get the
  precomputed path, about 0.5 ms per first call. Any other point triggers a live scan, about 0.2 ms, which is
  then cached.
- **Exact deadlines.** Deadlines on 5-minute marks between 06:00 and 26:30 are answered exactly from the table.
  Other times use the documented floor/ceil slot rule.
- **Batch helper.** `TransitProvider.arrive_by_many(origins, dest, day, t, modes)` is available as an extra
  method.
- **Night exposure.** `outdoor_after_22_min` counts walk and wait legs between 22:00 and 06:00. It does not
  count bike legs; their time is in `bike_min`.
