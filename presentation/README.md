# Lease Ledger — showcase deck (`presentation/`)

This is a cross-fading slide deck built with Vite and TypeScript, designed in the **Cartesian** editorial system (`design/CARTESIAN.md`): a museum-catalogue monograph on a stone canvas — Playfair Display 400 headlines and numerals, Inter body, taupe uppercase labels, 1px hairlines, compass-ring geometry, no shadows or gradients. The embedded app keeps its own black-and-white style inside hairline device frames (the deck is the monograph, the app is the instrument). It runs fully offline: fonts come from `@fontsource` (Playfair Display 5.2.8, Inter 5.2.8), KaTeX is bundled, and nothing loads from a CDN. It embeds the real app and calls the real API. Every number on a slide comes from one of two places:
- the API, live or from its cached snapshot;
- `presentation/data/facts.json`, which the evidence agent writes.

## Run order (three terminals, from the repo root)

| # | What | Command | URL |
|---|---|---|---|
| 1 | API | `make api` (or `LLM_MODE=cached python3 -m uvicorn ledger.api.app:app --port 8000`) | http://localhost:8000/api/health |
| 2 | App | `make web` | http://localhost:5173 |
| 3 | Deck | `cd presentation && npm install && npm run dev` | http://localhost:4400 |

- **`npm run snapshot`** captures every API response the deck uses into `public/snapshot.json`. The API must be up. The script also checks that the three scripted flips still flip the way `execution/demo-flips.md` says, and exits non-zero if they don't. Re-run it after any engine or data change.
- **`npm run build`** runs the honesty checks (below), then `tsc`, then `vite build` into `dist/`. Serve the result with `npm run preview`, also on :4400.
- **`npm run screenshots`** (the deck must be running) does two things:
  - writes every chapter at 1920×1080 to `screenshots/cartesian/` (plus extra states: pipeline intro, demo before the flip, the all-city plate and the catalogue; `--out=` and `--only=` override);
  - checks that every visible number on a slide carries `data-src`.
- **`npm run check`** runs the honesty checks and only warns about placeholders.
- **`npm run export`** (the deck must be running) writes a backup PDF of every slide, every multi-city plate and the catalogue to `export/lease-ledger-deck.pdf`.

### URL options
- `?app=http://host:5173` points the device frames at a different app URL.
- `?api=http://host:8000/api` calls an API directly. This needs CORS. By default the Vite proxy forwards `/api` to `API_TARGET`, which defaults to `http://localhost:8000`.
- `?offline` forces snapshot mode, so you can rehearse a network failure.
- `?appendix` shows the appendix chapters.
- `#demo`, `#robust`, … deep-link to a chapter.

## Keys
- `→` `Space` `PgDn`, the mouse wheel, the bottom-left arrow buttons or the right-edge dots: next reveal, then the next chapter (0.6 s fade). `←` `Shift+Space` `PgUp`: back.
- `1`…`9`, `0`: jump to that chapter.
- `T`: start or pause the timer. `Shift+T`: reset it. The timer targets 5:00 and shows each chapter's budget.
- `S`: open the speaker-notes window. It syncs over BroadcastChannel and has its own prev/next and timer buttons.
- `A`: show or hide the appendix.
- `F`: fullscreen. `?`: help.
- After you click inside the embedded app, click the slide margin to get the keys back.

## Chapters (budget sums to 5:00)

| # | Chapter | Budget | Source of every number |
|---|---|---|---|
| — | Cover — title plate (geo ring, ink accent) | 0:08 | none |
| — | Contents — agenda generated from the chapter list (Roman numerals, clickable) | 0:07 | none |
| I | The decision — "Lowest rent ≠ cheapest week" (two receipts, count-up totals) | 0:22 | `POST /evaluate` north-engineer |
| II | Why it's hard — Plate I week strip, citations, interviews "in progress" unless `data/interviews.json` | 0:25 | `/demo-profiles`, `/evaluate` |
| III | How it works — five-step timeline, KaTeX from `GET /methods` revealed per step | 0:35 | `/methods`, `/manifest` |
| IV | **Live demo** — app in hairline laptop + phone frames; 3 scripted flips in a ledger table with animated ranks | 1:15 | `/evaluate` + `/diff` (flips from `execution/demo-flips.md` only) |
| V | How sure are we — 100-mark frequency array plus the breakeven number line | 0:28 | `/robustness`, `/compare` |
| VI | Evidence — one anchor vs two, ablation, validation (field rides "pending" unless `data/field.json`) | 0:25 | `data/facts.json` (with 95% CIs) |
| VII | Same city, different map — Plate II cost-surface morph (stone→ink tones) | 0:15 | `data/surface-*.geojson`, `facts.json` |
| VIII | Seven cities — rapid-fire catalogue plates (~3 s each, click to pause, click a numeral to jump), all-city plate, catalogue grid + stats; honesty footer from feed statuses | 0:22 | `data/multicity.json`, `media/multicity/*` |
| IX | Group Week — surplus ledger, fair split, envy matrix | 0:18 | `POST /group` |
| X | Limits & next — API limitations, campus scaling, **plan** (not traction) | 0:12 | `/methods`, `/manifest` |
| — | Close — geo ring, one sentence, the ask | 0:08 | none |
| A | Appendix: the math under the hood — Sobol, τ(t) sawtooth, CVaR, EVPI | Q&A | `/api/advanced/*` (optional — shows "pending") |

If time is tight, skip chapter VIII: press `→` twice, or jump with the number keys. The multi-city GIFs are shown grayscale and multiplied into the stone canvas (CSS `mix-blend-mode: multiply`), so their white becomes the page.

## Honesty checks (`scripts/check-copy.mjs`; `--strict` in `npm run build`)
1. **No hard-coded digits in slide copy.**
   - The checker parses every `html\`…\`` template in `src/chapters/*.ts` and fails if any literal text contains a digit.
   - Numbers must arrive through `${num(…)}`, `${F('fact_id')}` or `${said(apiString)}`, all of which tag `data-src`.
   - `scripts/copy-whitelist.json` holds the tiny label whitelist (`#1`, `#2`).
   - Citation `finding` prose may not contain digits either.
2. **Placeholders fail the build.**
   - `src/required-data.json` lists the `facts.json` ids and the surface files the deck needs.
   - In dev a missing one renders a hatched PLACEHOLDER box; in `npm run build` it is an error.
3. **DOM check** (`npm run screenshots`): any visible text with a digit that is not inside `[data-src]` or `[data-ok]` (presenter chrome) fails.
4. **Live vs snapshot indicator** (bottom right):
   - `LIVE API`: the request was answered by the API.
   - `SNAPSHOT · <time>`: the request fell back to the snapshot.
   - The fallback happens per request, so a dead API never blanks a slide.

## Presenter checklist
- [ ] API up and warm: `curl localhost:8000/api/health`, which should report `"warmup":{"state":"done"…}`. Optionally run `python3 analysis/tools/demo_check.py`.
- [ ] App up on :5173, and `/app?demo=north-engineer#results` loads.
- [ ] `cd presentation && npm run snapshot`. It must print "as documented" for all 3 flips.
- [ ] `npm run build && npm run preview`. The build must pass with no placeholders; present from the preview, or from dev.
- [ ] Projector at 1920×1080. Browser fullscreen with `F`. Zoom at 100%: the stage scales itself.
- [ ] Press `S` and drag the notes window to the laptop screen. Press `T` when you start talking.
- [ ] Rehearse once with `?offline`: the indicator must read SNAPSHOT and the demo buttons must still work.
- [ ] Demo beat:
  - Press button 1 (VOT $8→$20). The tower wins, and the breakeven is on the next slide.
  - Press button 2 (hospital shift). It is a **knife-edge**: the lead is tiny, so say so.
  - Press button 3 (exclude co-ops).
- [ ] Evidence wording:
  - The portal gap is mostly rent and all-in accounting, **not routing**.
  - The fair test is the single-destination commute model.
  - **Never claim field rides** unless the slide shows field results.
- [ ] Interviews: say exactly what slide 2 shows. If none are logged, it says "in progress".

## Files
- `src/requests.js`: every API request (shared with `scripts/snapshot.mjs`). The flip definitions live here, along with `ADVANCED` request bodies (adjust them once `/api/advanced/*` schemas are final).
- `src/api.ts`: the live → snapshot fallback and the status indicator.
- `src/deck.ts`: fade navigation, reveal steps, Cartesian chrome (dots, arrows, counter), timer, notes channel and appendix mode.
- `src/styles.css` (tokens, components, chrome) and `src/chapters.css` (per-chapter layouts): the Cartesian system.
- `src/facts.ts`: the `facts.json` accessors `F()` and `CI()`, and placeholders.
- `src/chapters/*.ts`: one file per chapter, including its speaker notes.
- `scripts/prep-basemap.mjs`: turns `web/public/basemap.geojson` into compact SVG paths (`public/basemap-paths.json`).
