# Lease Ledger — design v3: a search-results product, not a pitch

Status: implemented in `web/` (2026-11-20). Supersedes the layout parts of `DESIGN-notes.md` (v2);
the visual language still descends from `DESIGN-reference.md` (paper-white, black pills, gray neutrals,
hairlines, no shadows or gradients).

Direction from the user: *a professional platform that looks like the established housing products people
already know, made more modern, and very close to `DESIGN-reference.md`, adapted to every feature we have.*
Not a startup landing page, not "vibe-coded".

What that means in practice:

1. **Borrow the interaction grammar, not the look.** Renters have a decade of muscle memory from the large
   rental portals: a sticky search bar with pill filters, a list of cards next to a map with price pins,
   a detail view, saved/compare. We reuse those conventions so nothing has to be learned. We do not copy any
   portal's branding, logo, colours, type, iconography, copy or assets.
2. **Keep the reference's restraint.** One sheet of white, black for the one primary action, three grays,
   1px hairlines, pills for controls, 12px cards. Colour only where it encodes data (transit modes, better/worse).
3. **Density of a tool, not air of a brochure.** Real products put 6–10 homes on a 900px-tall screen. Type
   steps are small (13–15px body in the app), numbers are tabular, and whitespace is spent on grouping, not on
   drama.

---

## (a) How established rental platforms work — interaction conventions

Described from general product knowledge (Zillow, Apartments.com, Zumper, Redfin rentals, StreetEasy), as
patterns only. These are the conventions renters bring with them.

### A1. The search-results page is the product
Every one of these platforms lands a searcher on the same layout: **list + map, side by side**, under a
sticky search/filter bar. The homepage exists mainly to get you into this page (a single location field and a
button). Everything else — detail, saved homes, comparisons — branches off it and returns to it.

- **Desktop split.** The map takes roughly half (sometimes 55–60%) of the width; the list is a scrollable
  column of cards (one or two cards across depending on width). Some put the map on the left (Zillow-style),
  others on the right (StreetEasy-style list-first). The page itself does not scroll; the list pane does.
  The map stays put.
- **Bidirectional hover.** Hovering a card highlights its pin (raised, inverted, or enlarged); hovering a pin
  highlights or previews its card. Clicking a pin either opens a small preview card on the map or scrolls the
  list to the card.
- **"Search as I move the map"** is a common option; we do not need it (our set is small and city-bounded).
- **Result count + sort** sit at the top of the list: "312 rentals · Sort: Recommended ▾". The sort menu
  typically offers price low→high, newest, beds, square footage.

### A2. Sticky search bar with pill filters
- One row under the global header: a location field on the left, then a row of **pill-shaped dropdown
  filters**: *Price*, *Beds & baths*, *Home type*, *More*. Each pill shows its current value when set
  ("$1,000–$1,500", "2+ bd") and gets a darker outline/fill when active. Clicking opens a small popover
  with the controls and an "Apply"/"Done" button; "More" opens a larger panel or modal with everything else.
- A "Save search" button on the far right; a "Reset"/"Clear" link when filters are active.
- On phones the filters collapse into one "Filters" button (with a count badge) that opens a full-screen sheet.

### A3. Listing cards
- **Photo slot on top** (≈ 3:2 or 16:10), carousel dots, a heart (save) in the corner, and sometimes a
  status chip on the photo ("New", "Price cut", "3D tour").
- **Price first and largest** under the photo ("$1,450/mo", or a range "$1,200+"), then a compact facts line
  ("2 bds | 1 ba | 850 sqft"), then the address, then the building/broker name in small gray text.
- Cards are clickable as a whole; secondary actions (save, share, contact) are icon buttons that do not
  navigate.
- Rentals add a small availability line ("Available now") and sometimes a commute line when a commute
  destination is set ("18 min to Downtown by transit") — the closest existing analogue to what we do.

### A4. Listing detail
- Opens as a **large overlay/drawer over the results** (Zillow-style, so the search context is preserved
  and Esc/back closes it) or as a **full page** (StreetEasy/Redfin-style). Both keep a back-to-results link.
- Structure: photo gallery → price + facts header with primary actions (Contact / Apply / Save / Share) →
  sticky in-page tab bar (Overview · Facts & features · Costs/fees · Neighborhood/Commute · Similar) →
  sections in that order. Fee and cost breakdowns are increasingly shown as a **line-item table**
  ("Monthly costs: base rent, utilities, pet rent, parking…") with a total — very close to our receipt.
- A "Commute" or "Getting around" module with a mini map and transit/walk times to a chosen destination.
- Source/listing provenance appears as small gray text near the bottom ("Listed by…", "Last updated…").

### A5. Compare tray and saved homes
- Some platforms let you tick "Compare" on several cards; a **tray** pins to the bottom of the viewport
  with the chosen homes and a "Compare (2)" button that opens a side-by-side table (price, beds, fees,
  amenities, commute) — rows aligned, differences highlighted.
- "Saved homes" (hearts) persist across sessions and get their own page.

### A6. Mobile
- Results default to the **list**; a floating **"Map" / "List" toggle** pill at the bottom centre swaps
  the whole viewport. On the map, tapping a pin shows a **peek card** at the bottom; tapping it opens the
  detail as a full-height sheet or page.
- Filters behind a single button; the header shrinks to the search field.
- Bottom tab bars appear in the native apps (Search · Saved · Inbox · Profile).

### A7. Visual habits worth noting (generic, not brand-specific)
- White canvas, gray hairlines, very light gray page fills behind cards; price in heavy weight; metadata in
  13–14px gray; small all-caps or medium-weight section labels.
- Price pins are white rounded rectangles with dark text; the selected/hovered pin inverts.
- Map basemaps are deliberately desaturated so the pins carry the colour.
- Very little decoration: the photos are the visual interest. **We have no photos** — so the
  map-thumbnail and the receipt must carry that role, honestly.

---

## (b) How Lease Ledger maps onto those conventions

| Portal convention | Lease Ledger | Notes |
|---|---|---|
| Location search field | **"Your week" summary pill** — "12 blocks · M–F · North Campus" | Our search input is a routine, not a place. Clicking it opens the week editor. |
| Price filter | **Budget** pill — rent cap (per person) and optional all-in cap | Current value shown in the pill: "Rent ≤ $1,500". |
| Beds & baths | **Household** pill — people sharing, min bedrooms, parking, pet | |
| Home type / More | **Getting around** pill (walk/bus/bike) and **More** (value of time, late-night weight, winter, season/month, nice-to-haves) | "More" opens the full constraints panel. |
| Sort ▾ | **Sort: Best for your week** (engine rank) · lowest all-in · lowest cash · least travel · lowest rent | Re-sorting the view never changes the engine's rank numbers. |
| Result count | "**12 homes fit your week** · 3 don't" | Infeasible homes stay visible, dimmed, with their reason. |
| Map with price pins | Ann Arbor offline basemap (Overture/OSM streets, no tile server) with **numbered all-in pins** ("1  $1,166") | Campus anchors (Central, North, Medical, South) labelled; your places drawn as ink rings. |
| Hover/select on map | Hover a card → its pin inverts. Select → **that home's real week routes** (walk paths, bus legs with route labels from the API `TripLeg.path`). | This is our "commute module", but on the main map. |
| Listing photo | **Generated map thumbnail**: the streets around the home from the same basemap, the home's own walk path and nearest bus leg, a home marker. | Never a fake photo. Labelled as a map. |
| Price on card | **All-in $/mo** big; cash $/mo and hours/week underneath | All-in is our price. |
| Facts line (bd/ba/sqft) | "2 bd · 1 ba · 850 sqft · co-op" and "4.8 h/wk travel · 28 min out after 10 PM" | |
| Status chips on photo | Rank badge (#1…), "lowest rent" when relevant | |
| Listing source line | Quiet provenance: "Observed · search text · Nov 20" or "Synthetic (fictional)" | Badges are smaller and gray; synthetic keeps the dashed hatch. |
| Detail drawer/page | **Detail panel** replacing the list pane (desktop) / **bottom sheet** (phone), map stays visible | Sections: Overview · Monthly receipt · Why this one · Your week from here · Listing facts · Sources. |
| Cost table on detail | **Receipt** (mono ledger, dotted leaders, low–high bands, all-in rule) | |
| Commute module | **Week timeline** (Mon–Sun legs) + trip list | |
| Compare tray | **Compare tray**: tick "Compare" on 2 cards → tray → side-by-side table, trip differences and the **value-of-time breakeven** | Also links to *Portal vs. your week*, our proof page. |
| Saved homes | Not built (no accounts). Pinning a snapshot in "What changed" plays the "save this state" role. | Honest omission. |
| Secondary nav | Homes · Your week · How sure · Portal vs. your week · Group Week · Add a listing · Methods | Text links in the global header, like a portal's top nav. |
| Mobile | List/Map toggle pill, bottom-sheet detail, 5-item tab bar (Homes, Week, Sure?, Group, More) | PWA unchanged. |

"What changed" (the diff drawer) appears only on Homes and Your week, as before.

### Information architecture

```
/                      Landing: search-first hero → product screenshot → 3 steps → sources → footer
/app#results           Homes (map + list) — the default once a week exists
/app#results + detail  Detail panel (list pane swaps to detail; ← Back to results)
/app#week              Your week editor (AI parse + weekly grid + constraints)
/app#robustness        How sure are we?
/app#baseline          Portal vs. your week
/app#group             Group Week
/app#add               Add a listing
/app#methods           Methods & sources
```

Hash routes and `?demo=` deep links remain valid.

---

## (c) Tokens

### Colour (unchanged from v2 except where noted)
| Token | Light | Use |
|---|---|---|
| `--bg` / canvas | #ffffff | page |
| `--raised` | #fafafa | list pane background, table heads |
| `--soft` | #f5f5f5 | pill fill, chips, hover |
| `--line` | #e5e5e5 | hairlines, card borders |
| `--line-strong` | #d4d4d4 | input outlines, active pill outline |
| `--ink` | #0a0a0a | text, primary pill, selected pin (v3: off-black, slightly softer on screen) |
| `--charcoal` | #404040 | secondary text in dense UI (v3: one notch darker for 13px legibility) |
| `--faint` | #737373 | metadata |
| `--mute` | #a3a3a3 | disabled, tertiary |
| `--bus` | #2563eb | bus legs, route labels |
| `--bike` | #16a34a | bike legs |
| `--wait` | #ca8a04 | waiting legs |
| `--walk` | #737373 | walk legs (gray, dashed) |
| `--good` / `--bad` | #15803d / #b91c1c | better/worse deltas only |

Rules: one black primary pill per view; colour only in maps, timelines, deltas. Dark theme = inversion (kept).

### Typography
The reference's rounded display face (SF Pro Rounded; Nunito in v2) reads soft and consumer-playful at our
sizes, and is the main reason v2 looked like a startup site. Established listing products use neutral
grotesques. v3:

| Role | Face | Size / weight | Notes |
|---|---|---|---|
| Display (landing h1/h2, detail title) | **Inter Tight Variable** | 40/32/24px, 600, −0.01em | restrained, tighter; bundled `@fontsource-variable/inter-tight@5.2.7` |
| UI + body | **Inter Variable** | 15px landing body, 14px app body, 13px metadata, 12px captions | `@fontsource-variable/inter@5.2.8`; `cv11`, `ss01` off |
| Prices & stats | Inter, **tabular numerals** (`.num`), 600–700 | card price 20px, detail price 32px | no monospace for prices — mono reads "terminal" |
| Receipt, provenance codes | JetBrains Mono Variable | 12–13px | only inside the receipt and tiny codes |

Pills keep the reference geometry (`rounded-full`), so the roundness lives in the shapes, not the letters.

### Spacing & density
- 4px base; app uses 8/12/16/24. Section rhythm on landing 88px (reference `section`), app panes 16–20px.
- Header 56px; filter bar 52px; both sticky. Results page = full viewport height below them (no page scroll).
- List pane: 1 column of horizontal cards ≤1279px, **2-column grid of vertical cards ≥1280px**
  (thumbnail 16:9 on top, like the portals), ~620px pane at 1440, ~880px at 1920.
- Cards: 12px radius, 1px hairline, 12px padding; hover = `line-strong` border; selected = ink border.
  No shadows anywhere (pins included: a 1px border separates them from the map).

### Components (new in v3)
- `SearchBar` — week pill, Budget, Household, Getting around, More, Sort, count. Popovers are 12px cards with
  hairline borders, `Esc` closes, focus returns to the pill.
- `HomeCard` — thumbnail, rank chip, all-in price, cash + hours, facts, quiet provenance, Compare checkbox.
- `MapThumb` — SVG mini map: basemap streets within ±450m, the home's walk path(s) and first bus leg, home dot.
- `SearchMap` — MapLibre, HTML price pins, campus labels, your places, selected home's routes.
- `HomeDetail` — sticky header with price + actions, section tabs (anchors), sections listed above.
- `CompareTray` — fixed bottom bar, 2 slots, "Compare" opens the comparison in the detail pane.
- `BottomSheet` (phone) — detail at 92vh, drag handle, `Esc`/backdrop closes.

### States
- Loading: skeleton cards (same footprint as cards) and a map that renders streets first, pins second.
- Updating (debounced re-evaluation): a thin "Updating…" text in the result count, previous data kept.
- Empty (no week): list pane shows a "Start with your week" panel; map still shows all listings as gray dots.
- Infeasible: banner at the top of the list with one-click relaxations (unchanged behaviour).
- API offline: the existing mock fallback banner under the header.

### Accessibility
- All pins are real `<button>`s with "Rank 1, ICC Escher House, $1,166 a month all-in" labels; cards are
  buttons with `aria-pressed` for selection; list is an `<ol>`.
- Filter popovers: `aria-expanded`, `aria-controls`, Esc closes, focus returns.
- Contrast: body text ≥ 4.5:1 (charcoal #404040 on white = 10.4:1; faint #737373 = 4.7:1).
- Hit targets ≥ 36px desktop, ≥ 44px phone. Reduced motion respected (no pin/route animation).
- Map is supplementary: every fact on it is also in the list or detail.

### Provenance, quieter
v2 showed mono pill badges everywhere. v3: on cards, one line of small gray text
("Observed · search text · Nov 20" / dashed "Synthetic"); full badges only inside the receipt and the
Sources section of the detail. The header keeps a single "synthetic n/N" indicator.

### Landing
A plain product homepage in the reference's README spirit: header (logo, three links, "Open the app"),
search-first hero ("Describe your week" input + black "See homes" pill — submitting parses the text and opens
the results), one real product screenshot of the results page (captured from the running app, labelled as
such), three steps, sources with live dates and counts, a short limits note, footer.
No hype copy, no testimonials, no invented stats, no stock photos.
