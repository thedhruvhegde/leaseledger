# Deploying Lease Ledger to Render

One Render **web service** runs one Docker container that serves both the API (`/api/*`) and the built React
app (`/` landing, `/app`). You get one public URL such as `https://lease-ledger.onrender.com`. No CLI needed.

Files: `Dockerfile` (multi-stage: node 22 builds `web/`, python 3.12 installs deps and builds the routing
artifacts from the committed GTFS feeds), `.dockerignore`, `render.yaml` (the Blueprint).

## 1. Deploy (click by click)
1. Push this repo to GitHub (the Blueprint reads `render.yaml` at the repo root).
2. Go to https://dashboard.render.com and sign in (GitHub sign-in is easiest).
3. Click **New +** (top right) → **Blueprint**.
4. Under **Connect a repository**, pick the repo (first time: **Configure account** → grant Render access to it).
5. Render shows the Blueprint name and the service it found: **lease-ledger** (Docker, Free, Ohio).
6. It asks for **GROQ_API_KEY** (marked `sync: false`). Leave it blank for the offline/rule-based mode, or paste a
   Groq key (see §3). Click **Apply** (or **Deploy Blueprint**).
7. Open the service → **Logs**. Expected build time: about **4–8 min** on the first build (npm ci + vite build ~1 min,
   pip install ~1–2 min, `python -m ledger.pipeline.build` ~20–60 s, image push), faster later thanks to layer
   caching. Measured locally: full image build 70 s on 4 cores; artifacts step 17 s.
8. When the status turns **Live**, the URL is shown at the top of the service page.

## 2. Verify
```bash
URL=https://lease-ledger.onrender.com          # your service URL
curl -s $URL/api/health                        # {"status": ..., "warmup": {"state": "running"|"done", ...}}
curl -s $URL/api/manifest | head -c 400
```
Then open `$URL/` (landing) and `$URL/app` (the app). Deep links like `$URL/app/week` also load (SPA fallback).
The first ~60–90 s after a (cold) start the server is warming caches in the background; requests already work,
the first ones are just slower. `warmup.state` in `/api/health` turns `done` when finished.

## 3. Live LLM parsing (optional)
Default is `LLM_MODE=cached`: schedule/listing text is parsed by the rule-based fallback (plus any cached LLM
answers that are committed; `data/cache/` is gitignored, so on Render that is usually none).
For live Groq parsing: service → **Environment** → set `GROQ_API_KEY` = your key (https://console.groq.com/keys)
and change `LLM_MODE` to `live` → **Save changes** (Render redeploys). The key is read from the environment and
sent as `Authorization: Bearer`; it is never logged or written to disk. If Groq fails, the app falls back to rules.

## 4. Free vs paid
| Plan | CPU / RAM | Behaviour |
|---|---|---|
| Free | 0.1 / 512 MB | sleeps after 15 min idle; next visit waits ~1 min (container start ~20 s + warm-up) |
| Starter | 0.5 / 512 MB | always on, no cold starts; ~5x faster warm-up. Keep `LOW_MEMORY=1`. |
| Standard | 1 / 2 GB | can set `LOW_MEMORY=0`, `LEDGER_NO_NUMBA=0` (full warm-up of all listings, ~690 MB) |

Upgrade: service → **Settings** → **Instance Type** → pick **Starter** → **Save**. (Or change `plan: free` to
`plan: starter` in `render.yaml` and push.) For a demo on Free, open the URL ~2 min before presenting.

Measured memory (real routing provider, LLM_MODE=cached):
- default mode, after warm-up: **688 MB RSS** (too big for 512 MB);
- `LOW_MEMORY=1 LEDGER_NO_NUMBA=1` (the Blueprint default): **~424 MB RSS** after warm-up (252 MB anonymous, the
  rest memory-mapped label pages, which the kernel can reclaim); ~530 MB peak RSS / ~350 MB anonymous after an
  evaluate + robustness over all 69 observed listings. In Docker with `--cpus=0.1 --memory=512m` (Free-tier
  proxy): 255 MiB container usage after warm-up, listening after 21 s, warm-up done after 90 s; after the
  heaviest requests 370 MiB, no OOM. At 0.1 CPU an uncached evaluate of all 69 listings takes ~44 s and
  robustness ~11 s; the demo set (pre-warmed) answers in ~0.3 s. Starter (0.5 CPU) is ~5x faster.
- Results are identical in both modes (checked on the demo profiles).

## 5. Running the scraper on Render
See `ledger/scrape/README.md` for the policy (robots.txt, 1 request / 3 s per host, denylisted aggregators).
- One-off: service → **Shell** (paid instances) → `python -m ledger.scrape --out data/listings/scraped.json --dry-run`
  (dry run prints what it would fetch/parse), then without `--dry-run`. The API reads `data/listings/scraped.json`
  if present at startup, so restart the service afterwards (Manual Deploy → Restart).
  Note the container disk is ephemeral: the file is lost on the next deploy or restart. To keep results,
  run the scraper on a laptop and commit `data/listings/scraped.json`.
- Scheduled: uncomment the `cron` block at the bottom of `render.yaml` (Cron Jobs are paid).

## 6. Local check of the same image
```bash
docker build -t lease-ledger .
docker run --rm -p 8000:8000 lease-ledger        # http://localhost:8000/  and /api/health
# Free-tier imitation:
docker run --rm --cpus=0.1 --memory=512m -p 8000:8000 lease-ledger
```
Without Docker: `cd web && VITE_API_BASE=/api npm run build && cd .. && WEB_DIST=web/dist LOW_MEMORY=1 LLM_MODE=cached python3 -m uvicorn ledger.api.app:app --port 8000`.

## Environment variables
| Var | Default (image) | Meaning |
|---|---|---|
| `PORT` | set by Render | port uvicorn listens on |
| `WEB_DIST` | `/app/web/dist` | built web app to serve; unset = API only |
| `LLM_MODE` | `cached` | `live` / `cached` / `off` |
| `GROQ_API_KEY` | unset | Groq key for `LLM_MODE=live` |
| `LOW_MEMORY` | `1` | mmap label tables, smaller caches, skip warming every listing |
| `LEDGER_NO_NUMBA` | `1` | do not import numba in the server |
| `LEDGER_CORS_ORIGINS` | localhost dev ports | extra allowed origins (comma-separated); `RENDER_EXTERNAL_URL` is added automatically. Same-origin requests need none. |
| `LEDGER_ENV` | `prod` | disables `POST /api/reload` |
