#!/usr/bin/env bash
# Decode the multicity GIFs (presentation/media/multicity) into 30-fps PNG frames for the seven-cities scene.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/media/scripts/.cache/seven-cities"
mkdir -p "$OUT"
echo "window.FRAMES = {" > "$OUT/frames.js"
for c in annarbor austin uiuc princeton boston nyc sf finale_all_cities; do
  rm -rf "$OUT/$c"; mkdir -p "$OUT/$c"
  ffmpeg -loglevel error -i "$ROOT/presentation/media/multicity/$c.gif" -vf fps=30,format=rgb24 "$OUT/$c/%04d.png"
  n=$(ls "$OUT/$c" | wc -l)
  echo "  \"$c\": $n," >> "$OUT/frames.js"
done
echo "};" >> "$OUT/frames.js"
cat "$OUT/frames.js"
