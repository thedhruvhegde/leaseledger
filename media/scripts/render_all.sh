#!/usr/bin/env bash
# Regenerate every explainer video: numbers -> frames -> MP4 + GIF + poster.
#   cd <repo> && bash media/scripts/render_all.sh [names...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
PYTHONPATH=. python3 media/scripts/compute_data.py
[ -f media/scripts/.cache/seven-cities/frames.js ] || bash media/scripts/prep_seven_cities.sh
names=("$@"); [ ${#names[@]} -gt 0 ] || names=(one-week the-receipt the-flip how-sure connection-scan seven-cities)
for n in "${names[@]}"; do node media/scripts/render.mjs "$n" && bash media/scripts/encode_extras.sh "$n"; done
