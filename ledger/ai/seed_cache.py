"""Record REAL Groq responses for the demo inputs into data/cache/llm/ so LLM_MODE=cached works offline.

  python3 -m ledger.ai.seed_cache            # demo schedules + sample listings
  python3 -m ledger.ai.seed_cache --eval     # also the labeled eval set (tests/ai/eval_data.py)

Every cache file is the parsed JSON of an actual API response (model, latency and token usage recorded). Nothing
is fabricated: if a call fails, nothing is written for that input. Cache keys include the prompt, so editing
data/campus/buildings.json (the place list in the prompt) or the prompt text requires re-seeding.
"""
from __future__ import annotations

import argparse
import json
import time

from ledger.ai.client import CACHE_DIR, LLMClient
from ledger.ai.demo_inputs import DEMO_LISTINGS, DEMO_SCHEDULES
from ledger.ai.listing_extractor import extract_listing
from ledger.ai.places import PlaceIndex
from ledger.ai.schedule_parser import parse_schedule
from ledger.api.data import DataStore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--pace", type=float, default=3.0)
    a = ap.parse_args()
    places = PlaceIndex(DataStore().buildings())
    client = LLMClient(mode="live", write_disk=True)
    sched = dict(DEMO_SCHEDULES)
    lists = dict(DEMO_LISTINGS)
    if a.eval:
        from tests.ai.eval_data import LISTINGS, LISTINGS_HELDOUT, SCHEDULES, SCHEDULES_HELDOUT
        sched.update({f"eval-s{i}": t for i, (t, _) in enumerate(SCHEDULES + SCHEDULES_HELDOUT)})
        lists.update({f"eval-l{i}": t for i, (t, _) in enumerate(LISTINGS + LISTINGS_HELDOUT)})
    index_path = CACHE_DIR / "INDEX.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    for name, text in sched.items():
        res, meta = parse_schedule(text, places, client=client)
        print(f"schedule {name}: mode={res.mode} model={meta.get('model')} events={len(res.events)} "
              f"llm_ms={meta.get('llm_latency_ms')} err={meta.get('llm_error')}")
        if res.mode in ("live", "cached"):
            index[name] = {"task": "parse_schedule", "model": meta.get("model"), "source": res.mode,
                           "events": len(res.events), "recorded": time.strftime("%Y-%m-%d")}
        time.sleep(a.pace if res.mode == "live" else 0)
    for name, text in lists.items():
        res = extract_listing(text, client=client)
        print(f"listing {name}: mode={res.mode} model={res.model} facts={len(res.facts)} flags={len(res.flags)} "
              f"err={res.llm_error}")
        if res.mode in ("live", "cached"):
            index[name] = {"task": "extract_listing", "model": res.model, "source": res.mode,
                           "facts": len(res.facts), "recorded": time.strftime("%Y-%m-%d")}
        time.sleep(a.pace if res.mode == "live" else 0)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=1, sort_keys=True))
    print("cache entries:", client.status()["disk_cache_entries"])


if __name__ == "__main__":
    main()
