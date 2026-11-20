# Lease Ledger — showcase deck (`presentation/`)

This is a cross-fading slide deck built with Vite and TypeScript. It uses the Cartesian palette (`design/CARTESIAN.md`: stone canvas, ink, 1px hairlines, no shadows) with the v3 type and layout rules in **`design/DECK-NOTES.md`**:
- **Fraunces** headlines and **Inter Tight** body and numbers (tabular figures), both bundled through `@fontsource-variable` (Fraunces 5.2.8, Inter Tight 5.2.7). KaTeX is bundled too; nothing loads from a CDN.
- Each slide has one headline, one hero image or number, and at most one supporting line.
- Nothing on a slide is smaller than 22px, except the live/snapshot indicator.
- Caveats and detail live in the speaker notes and on the Limits slide.

The deck runs fully offline. It embeds the real app and calls the real API.
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
  - writes every chapter at 1920×1080 to `screenshots/v3/` (plus extra states: each how-it-works step, the demo before the flip, the first city plate, the pre-reveal states; `--out=` and `--only=` override);
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

| # | Chapter | Budget | Hero (source) |
|---|---|---|---|
| 1 | Cover — full-bleed Ann Arbor with one engineer's week of trips drawn on in ink | 0:08 | `POST /compare` trip legs over `basemap-paths.json` |
| 2 | The decision — two homes, two route maps, two all-in totals | 0:29 | `POST /evaluate` north-engineer, `POST /compare` (`routes`) |
| 3 | A whole week — the week grid plus one number (trips routed) and author-year chips | 0:25 | `/demo-profiles`, `/evaluate` |
| — | *What students told us* — collage + keyword chips. **Only in the talk when `data/interviews.json` or `public/interviews/*.jpg\|png` exists**; then it takes 0:10 from chapter 3 | (0:10) | user-supplied only |
| 4 | How it works — five steps, one picture or number each (app screenshot, timetable count, a real day tour, the walk/wait weight, the receipt) | 0:35 | `public/img/*`, `/manifest`, `/compare`, `facts.json` |
| 5 | **Live demo** — app in hairline frames; three scripted flips with animated ranks | 1:15 | `/evaluate` + `/diff` (flips from `execution/demo-flips.md` only) |
| 6 | How sure — 100-mark array and "n in 100", then → the breakeven number line | 0:28 | `/robustness`, `/compare` |
| 7 | Evidence — two-anchor hero %, one-anchor %, then → validation | 0:25 | `data/facts.json` |
| 8 | Same city, different map — two cost surfaces side by side, one overlap % | 0:15 | `data/surface-*.geojson`, `facts.json` |
| 9 | Seven cities — rapid fire: each city's map + one %, then a catalogue of all seven (tag: simulated · travel-only) | 0:22 | `data/multicity.json`, `media/multicity/*` |
| 10 | Group Week — app screenshot, fair rent each, largest envy | 0:18 | `POST /group` |
| 11 | Limits & next — six short limits (the full API list is in the notes), then → the plan | 0:12 | `/methods` |
| 12 | Close — the city again, one sentence, the ask | 0:08 | none |
| A | Appendix: the math under the hood — Sobol, τ(t) sawtooth, CVaR, EVPI | Q&A | `/api/advanced/*` |

The receipt lines, CIs, portal comparison, ablation, citations' findings and every caveat are in each chapter's speaker notes (`S`).

If time is tight, skip the seven-cities chapter (jump with the number keys). The multi-city GIFs are cropped to their map, shown grayscale and multiplied into the stone canvas (CSS `mix-blend-mode: multiply`), so their white becomes the page.

**Interviews:** drop photos into `public/interviews/` and/or write `data/interviews.json` (`{completed?, keywords|themes|tags: [string | {label, count}], images?, note?}`). `npm run prep` lists the images, and the chapter joins the talk after chapter 3. With neither present it stays out entirely. Nothing is ever invented.

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
- [ ] Interviews: the "What students told us" slide exists only when real material is in `public/interviews/` or `data/interviews.json`. Say exactly what it shows; if it's absent, don't mention counts.

## Files
- `src/requests.js`: every API request (shared with `scripts/snapshot.mjs`). The flip definitions live here, along with `ADVANCED` request bodies (adjust them once `/api/advanced/*` schemas are final).
- `src/api.ts`: the live → snapshot fallback and the status indicator.
- `src/deck.ts`: fade navigation, reveal steps, Cartesian chrome (dots, arrows, counter), timer, notes channel and appendix mode.
- `src/styles.css` (tokens, components, chrome) and `src/chapters.css` (per-chapter layouts): the Cartesian system.
- `src/facts.ts`: the `facts.json` accessors `F()` and `CI()`, and placeholders.
- `src/chapters/*.ts`: one file per chapter, including its speaker notes.
- `src/routemap.ts`: ink route maps (basemap streets + `/compare` trip-leg geometry, draw-on animation).
- `scripts/prep-interviews.mjs`: lists `public/interviews/*` into `src/interviews-manifest.json`.
- `scripts/prep-basemap.mjs`: turns `web/public/basemap.geojson` into compact SVG paths (`public/basemap-paths.json`).
