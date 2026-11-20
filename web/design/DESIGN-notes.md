# Lease Ledger design notes (v2, 2026-11-20)

Routes: `/` landing, `/app#<screen>` app. Old links still open the app: any URL with a screen hash
(`/#results`) or `?demo=` (e.g. `/?demo=north-engineer#results`). Keys 1–7 jump to app screens from the
landing too; `P` toggles presentation mode in the app.

System (adapted from `DESIGN-reference.md`, no borrowed brand, name, mascot or assets):
- Paper-white canvas, black ink, grays #525252 / #737373 / #a3a3a3, 1px #e5e5e5 hairlines. No shadows, no gradients.
  Dark theme = inversion (#171717 surfaces). Tokens: `src/index.css` (`:root`, `.dark`).
- Pills for every control (`.btn`, `.input`, `.chip`, `.tag`, Segmented, nav items); cards 12px + hairline.
- Type: Nunito (headings), Inter (body), JetBrains Mono (numbers, receipts, tags). Bundled via
  `@fontsource-variable/*` (pinned), so the demo runs offline.
- One inverted "look here" surface per page: `.surface-invert` (app: the #1 home card; landing: the #1 receipt).
- Colour only inside charts/timelines/maps (walk/wait/bus/bike) and for better/worse deltas.
- Signature input: `components/WeekPill.tsx` (landing hero + close, "Your week"). Landing text is handed to the app via `weekDraft` in the store.
- Receipt: `components/Receipt.tsx` renders the API ledger as a mono receipt (dotted leaders, low…high bands, rule above all-in).
- Mark: `Header.tsx` `Logo` — house outline whose roofline is a bus-route polyline with three stops.

Landing content rules: every number is computed live (north-engineer demo via /evaluate, /robustness, /compare, /group)
or read from cited data (/listings counts and dates, /manifest GTFS validity). No testimonials, logos, user counts or stats.
No photographs: no licensed images were available offline, so the product's own receipt, timelines and the offline
basemap are the pictures. The design-taste skill's scripts (gate/consistency) were not run, so no `.taste-skill/` dir exists.

Screenshots: `node scripts/screenshots-v2.mjs` (env ONLY, SIZE, PRESENT=1, DARK=1, FULL=1) → `screenshots/v2/`.
