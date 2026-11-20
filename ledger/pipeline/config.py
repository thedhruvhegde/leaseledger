"""Constants shared by the artifact build and the runtime provider (recorded in manifest.json)."""
from __future__ import annotations

import os
from pathlib import Path

from ledger.pipeline.feeds import REPO

ARTIFACT_DIR = Path(os.environ.get("LEDGER_ARTIFACT_DIR", REPO / "data" / "artifacts"))
BUILDINGS_JSON = REPO / "data" / "campus" / "buildings.json"
SEGMENTS_PARQUET = REPO / "data" / "raw" / "overture_a2" / "segment.parquet"

WALK_MPS = float(os.environ.get("LEDGER_WALK_MPS", 1.34))
BIKE_MPS = float(os.environ.get("LEDGER_BIKE_MPS", 4.2))
BIKE_OVERHEAD_MIN = 2.0               # lock + unlock

STOP_RADIUS_M = 900.0                 # max walk to/from a stop
STOP_K = 20                           # nearest stops considered at each end
BUILDING_SNAP_MAX_M = 60.0

SLOT_START_MIN = 6 * 60               # precomputed label grid: 06:00 .. 26:30 (02:30 next day), every 5 min
SLOT_END_MIN = 26 * 60 + 30
SLOT_STEP_MIN = 5
N_SLOTS = (SLOT_END_MIN - SLOT_START_MIN) // SLOT_STEP_MIN + 1
LABEL_NONE = 65535                    # uint16 sentinel: stop cannot reach / be reached

TRANSFER_TIEBREAK_S = 120             # among bus journeys, each transfer must save >= 2 min to be preferred
NIGHT_START_MIN = 22 * 60             # outdoor exposure window 22:00 .. 06:00
NIGHT_END_MIN = 30 * 60
LAST_DEPARTURE_NOTE_MIN = 60          # note "last X departs ..." when within this many minutes after boarding
