#!/usr/bin/env bash
# GIF preview (960 px wide, <= 8 MB) for media/videos/<name>.mp4; poster PNG is written by render.mjs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; V="$ROOT/media/videos"; n="$1"
fps=${GIF_FPS:-10}
for try in 1 2 3; do
  ffmpeg -y -loglevel error -i "$V/$n.mp4" -vf "fps=$fps,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" "$V/$n.gif"
  sz=$(stat -c %s "$V/$n.gif")
  if [ "$sz" -le 8000000 ]; then break; fi
  fps=$((fps * 2 / 3))
done
ls -la "$V/$n.mp4" "$V/$n.gif" "$V/$n.png"
