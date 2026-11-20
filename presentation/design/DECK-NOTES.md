# Deck v3 — design notes

The feedback on the Cartesian deck was: too much text, too many small labels, and the type felt templated. The palette, hairlines, fades and rank animations stayed. This pass changed four things.

## 1. Typography: Fraunces + Inter Tight (both bundled offline, pinned)

| Role | Face | Package | Settings |
|---|---|---|---|
| Headlines | **Fraunces** (variable) | `@fontsource-variable/fraunces@5.2.8` (`full.css`, `full-italic.css`) | weight 340, `opsz 144`, `SOFT 0`, `WONK 0`. Italic uses `WONK 1` for the emphasized half of each headline |
| Body and **every number** | **Inter Tight** (variable) | `@fontsource-variable/inter-tight@5.2.7` | hero numbers use weight 300, tabular lining figures, −0.045em tracking |

Why this pair:
- **Playfair read as template-y** because it is the default "elegant serif" in a thousand themes. Fraunces at its largest optical size is a sharp, high-contrast display cut. With SOFT 0 it stays crisp rather than soft, so it keeps the editorial voice without looking like a stock theme. The `WONK` italic gives the second half of each headline its own character.
- **The numbers are the content, so they get a sans with tabular figures.** Big numerals set in a Didone-style serif look decorative, and their hairline strokes vanish at the back of a room. Inter Tight Light at 150–300px keeps even stroke weight, so `$1,634` vs `$1,166` stays legible from the back. Tabular figures stop the count-up animation from jittering.
- Inter Tight is set narrower than Inter, so the long listing names ("ICC Escher House - double room (co-op)") fit on one line at 34px.
- Both fonts ship in the build. Nothing loads from a CDN.

## 2. Text cut (~60%)

The slide rule: **one headline (≤ 8 words) + one hero (a picture or a number) + at most one supporting line.**

Removed from the slides:
- The chapter eyebrows ("I · THE DECISION").
- The plate numbering ("Plate I…IX").
- "Why it's hard".
- The uppercase micro-labels.
- The receipt line items.
- The citation paragraphs (they are now author-year chips).
- The long caveat footers.
- The agenda slide.

Each of these moved into that chapter's **speaker notes** (press `S`), which now carry the receipt lines, the CIs, the portal comparison, the ablation and the full limitations list. The caveats also went to the **Limits** slide.

Type scale at 1920×1080:
- Headlines are 84px.
- The supporting line is 28–40px.
- The minimum is **22px** for anything on a slide. The only exceptions are the live/snapshot indicator and the hover-only rail labels.

Honesty tags stay visible on their own slides, at 22px:
- `simulated · travel-only` on the seven-city slide.
- `travel cost only` on the surface maps.
- `synthetic listing` on Group Week, when that applies.
- `recorded run of the real app` vs `the real app, live` on the demo slide.

## 3. More images (honest ones only)

| Slide | Image | Source |
|---|---|---|
| Cover, Close | Full-bleed Ann Arbor streets with **one engineer's real week of trips** drawn on in ink | `public/basemap-paths.json` + `POST /compare` trip legs (`path`) |
| The decision | Two maps, one per home: the lowest-rent home's week vs the #1 home's week | `POST /compare` (`plan.routes`), same scale |
| How it works | App screenshots, a real day tour on the map, the timetable count | `public/img/*` from `execution/demo-run/`, `/compare`, `/manifest` |
| Live demo | The app itself (iframes) or the recorded run | `:5173` / `public/demo/` |
| Same city | Two cost surfaces side by side (the morph removed) | `data/surface-*.geojson` |
| Seven cities | Each simulation GIF cropped to its map, then a catalogue of seven | `media/multicity/*` |
| Group Week | The app's Group Week screen | `public/img/10-group-week.png` |
| What students told us | Collage from `public/interviews/*.jpg\|png` + keyword chips from `data/interviews.json` | the user only; the chapter is **left out of the talk** when neither exists (never shown as "pending") |

There are no stock photos and no mock product shots. The route lines are trip legs the engine routed on the real timetable. Bus legs are drawn stop-to-stop, as the feed shapes allow.

## 4. Numbers as heroes

There is one number per slide, set in Inter Tight Light:

| Slide | Hero number |
|---|---|
| The decision | `$1,634` vs `$1,166`, plus `$468 more` |
| A whole week | `26` trips |
| How it works | `1.75×` |
| How sure | `80 in 100`, then `$15.28/h` |
| Evidence | `60%` (with `8%` alongside) |
| Same city | `28%` |
| Seven cities | `45%` per city, then `29%–51%` across `28,000` simulated semesters |
| Group Week | `$785` each, `$0` envy |

Every number is still bound to its source with `data-src` (API, snapshot or `facts.json`). `npm run build` and the screenshot DOM check enforce this.

## v4 additions

- **The engine** and **What every home is ranked on** sit between the demo and "How sure", so the math is on screen before the statistics that rest on it. Equations are KaTeX at 34px; every constant inside them (1.75, 10, 0.5, ω, the scan count and ms per scan, the 2,000 samples) is interpolated from `GET /methods`, `/manifest` or `/robustness` at render time, never typed.
- The parameter ledger is the one deliberately denser slide: nine rows, 28px values in tabular figures, right-aligned value and range columns, and a basis column (filled dot = observed, half = estimated, hollow + italic = assumed).
- Time for the two slides (36 s) came from the demo (−5), how it works (−7), the decision (−3), the week (−2), evidence (−3), same city (−3), seven cities (−10; 1.5 s per city) and Group Week (−3). Total stays 5:00.
- Interviews are real (16 students, Nov 20; see `analysis/feedback/PROVENANCE.md`). With no photos the slide is count + findings + a keyword ledger with bars; with photos the collage takes the left side in one, two or three rows (1–3, 4–6, 7–9 images) and the ledger shortens.

## v5 additions

- **Canvas** moves from stone `#EDE8E0` to a warm near-white `#F7F5F0`; the old stone becomes `--bg2` (plate mats), hairlines lighten to `#C4BBAE`, body/accent darken a touch to keep contrast.
- **Bottom glow**: one fixed `.glow` band (130px at 1080p) along the bottom edge of every slide: three soft radial hues (blue `#8FB8FF`, violet `#D7A8F0`, peach `#FFD3A1`) at ≤0.44 alpha, blurred and masked to 0 at the top of the band, drifting ±6% over 26 s (static under reduced motion). It sits under all presenter chrome (z 5 vs 20).
- **Explainer loops** (`public/video/*.mp4`, copied from `media/videos/fast/`; 4–6 s, 10× speed, silent; posters `*.jpg`): framed like the image plates (hairline, stone mat, no shadow) via `loop()` in `src/lib.ts`, each with one digit-free caption chip on the frame's top-right corner and a top-down unveil on entry.

| Slide | Loop | Placement |
|---|---|---|
| Cover | `one-week` | plate above the title panel |
| How it works · One total | `the-receipt` | replaces the static receipt screenshot |
| Live demo | `walkthrough` | recorded mode: the laptop frame (replaces `demo/lease-ledger-demo.mp4`); live mode: stands in on the laptop if the app is unreachable |
| The engine | `connection-scan` | new reveal (→): the six-stage flow fades, the loop takes its place |
| How sure | `how-sure`, then `the-flip` | replace the 100-mark array and the breakeven number line; the hero numbers stay |
| Seven cities | `seven-cities` | replaces the per-city GIF rapid fire (runs once, ~6 s), then the catalogue |

- Playback: `syncMedia()` (called on every chapter change, reveal step and multi-city advance) plays only the loops on the visible slide and step, rewinds them on re-entry, and pauses everything else. Under `prefers-reduced-motion` nothing plays and the poster frame (85% through each loop) stands in.
- **Listing scope** now matches the app's Homes page: every `/evaluate`, `/diff` and `/robustness` request sends `listing_ids` = all observed listings in `GET /listings` order (`scopeIds()` in `src/requests.js`, same as `useScopeIds` 'all' in the web app). All three flips still flip to University Towers on that set; the hospital flip leads by about $2/mo (knife edge).
