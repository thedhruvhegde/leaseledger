"""Measure schedule-parser and listing-extractor accuracy on the labeled SYNTHETIC set; write ledger/ai/EVAL.md.

  python3 -m tests.ai.run_eval            # rules only (offline, deterministic)
  python3 -m tests.ai.run_eval --live     # also the LLM path (needs network; uses/creates in-memory cache only)
  python3 -m tests.ai.run_eval --cached   # LLM path from data/cache/llm only
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

from ledger.ai.client import LLMClient
from ledger.ai.listing_extractor import extract_listing
from ledger.ai.places import PlaceIndex
from ledger.ai.schedule_parser import parse_schedule
from ledger.schemas import Building
from tests.ai.eval_data import LISTINGS, LISTINGS_HELDOUT, SCHEDULES, SCHEDULES_HELDOUT

REPO = Path(__file__).resolve().parents[2]
EVAL_MD = REPO / "ledger" / "ai" / "EVAL.md"
PACE_S = 0.0   # seconds between LLM calls (Groq free tier rate limit); set by --live


def places() -> PlaceIndex:
    return PlaceIndex([Building(**b) for b in json.loads((REPO / "data/campus/buildings.json").read_text())])


def _pr(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 1.0
    r = tp / n_gold if n_gold else 1.0
    return p, r


# ------------------------------------------------------------------ schedules
def eval_schedules(client: LLMClient, use_llm: bool, data=None) -> dict:
    data = SCHEDULES if data is None else data
    P = places()
    c = {k: {"tp": 0, "pred": 0, "gold": 0} for k in ("event", "days", "start", "end")}
    lat, modes, errors, llm_err = [], [], [], []
    quote_ok = quote_n = 0
    for text, gold in data:
        t0 = time.perf_counter()
        res, meta = parse_schedule(text, P, client=client, use_llm=use_llm)
        lat.append((time.perf_counter() - t0) * 1000)
        if use_llm and meta.get("llm_error"):
            llm_err.append(meta["llm_error"][:160])
        if use_llm and PACE_S:
            time.sleep(PACE_S)
        modes.append(res.mode)
        preds = [(e.building_id, "".join(d.value for d in e.days), e.start_min, e.end_min) for e in res.events]
        for e in res.events:
            quote_n += 1
            quote_ok += bool(e.source_quote and e.source_quote in text)
        # greedy match on building + overlapping days
        used = set()
        pairs = []
        for gi, g in enumerate(gold):
            best = None
            for pi, p in enumerate(preds):
                if pi in used or p[0] != g[0]:
                    continue
                ov = len(set(p[1]) & set(g[1]))
                if ov and (best is None or ov > best[1]):
                    best = (pi, ov)
            if best:
                used.add(best[0])
                pairs.append((g, preds[best[0]]))
        c["event"]["tp"] += len(pairs); c["event"]["pred"] += len(preds); c["event"]["gold"] += len(gold)
        unmatched_preds = len(preds) - len(pairs)
        for key, idx in (("days", 1), ("start", 2), ("end", 3)):
            gold_stated = [g for g in gold if g[idx] is not None]
            c[key]["gold"] += len(gold_stated)
            matched_stated = [(g, p) for g, p in pairs if g[idx] is not None]
            c[key]["tp"] += sum(1 for g, p in matched_stated if (set(p[1]) == set(g[1]) if idx == 1 else p[idx] == g[idx]))
            c[key]["pred"] += len(matched_stated) + unmatched_preds
        for g, p in pairs:
            if p != (g[0], p[1], p[2], p[3]) or set(p[1]) != set(g[1]) or (g[2] is not None and p[2] != g[2]) or (g[3] is not None and p[3] != g[3]):
                errors.append({"text": text, "gold": g, "pred": p})
        for g in gold:
            if not any(g is x for x, _ in pairs):
                errors.append({"text": text, "gold": g, "pred": None})
    out = {k: dict(zip(("precision", "recall"), _pr(v["tp"], v["pred"], v["gold"])), **v) for k, v in c.items()}
    out["_meta"] = {"n_texts": len(data), "n_gold_events": c["event"]["gold"],
                    "latency_ms_median": round(statistics.median(lat), 1), "latency_ms_max": round(max(lat), 1),
                    "modes": {m: modes.count(m) for m in set(modes)},
                    "quote_verbatim_rate": quote_ok / quote_n if quote_n else 1.0, "errors": errors,
                    "llm_errors": llm_err}
    return out


# ------------------------------------------------------------------ listings
SCALAR = ["rent", "rent_basis", "bedrooms", "baths", "sqft", "deposit", "lease_term_months", "pets_allowed",
          "furnished", "in_unit_laundry", "joint_and_several", "parking"]


def _parking_val(fact) -> object:
    if fact is None:
        return None
    d = fact.detail
    if "parking_monthly" in d:
        return d["parking_monthly"]
    v = str(fact.value).lower()
    return "street" if "street" in v else ("none" if v in ("none", "no", "no parking") else v)


def eval_listings(client: LLMClient, use_llm: bool, data=None) -> dict:
    data = LISTINGS if data is None else data
    fields = SCALAR + ["utilities_included", "fees", "flags"]
    c = {k: {"tp": 0, "pred": 0, "gold": 0} for k in fields}
    lat, modes, errors, llm_err = [], [], [], []
    quote_ok = quote_n = 0
    for text, gold in data:
        t0 = time.perf_counter()
        res = extract_listing(text, client=client, use_llm=use_llm)
        lat.append((time.perf_counter() - t0) * 1000)
        if use_llm and res.llm_error:
            llm_err.append(res.llm_error[:160])
        if use_llm and PACE_S:
            time.sleep(PACE_S)
        modes.append(res.mode)
        for f in res.facts:
            quote_n += 1
            quote_ok += text[f.start:f.end] == f.quote
        by = {}
        for f in res.facts:
            by.setdefault(f.field, f)
        for k in SCALAR:
            if k not in gold:
                continue
            g = gold[k]
            f = by.get(k)
            pv = _parking_val(f) if k == "parking" else (f.value if f is not None else None)
            if f is not None:
                c[k]["pred"] += 1
            if g is not None:
                c[k]["gold"] += 1
                ok = pv is not None and (abs(float(pv) - float(g)) < 0.51 if isinstance(g, (int, float)) and not isinstance(g, bool)
                                         and isinstance(pv, (int, float)) else pv == g)
                c[k]["tp"] += ok
                if not ok:
                    errors.append({"text": text[:60], "field": k, "gold": g, "pred": pv})
            elif f is not None:
                errors.append({"text": text[:60], "field": k, "gold": None, "pred": pv})
        if "utilities_included" in gold:
            g = gold["utilities_included"]
            p = {f.value for f in res.facts if f.field == "utilities_included"}
            c["utilities_included"]["tp"] += len(p & g); c["utilities_included"]["pred"] += len(p)
            c["utilities_included"]["gold"] += len(g)
            if p != g:
                errors.append({"text": text[:60], "field": "utilities_included", "gold": sorted(g), "pred": sorted(p)})
        if "fees" in gold:
            g = gold["fees"]
            p = {round(float(f.value)) for f in res.facts if f.field.startswith("fee:")}
            c["fees"]["tp"] += len(p & g); c["fees"]["pred"] += len(p); c["fees"]["gold"] += len(g)
            if p != g:
                errors.append({"text": text[:60], "field": "fees", "gold": sorted(g), "pred": sorted(p)})
        if "flags" in gold:
            g = gold["flags"]
            p = {fl["rule"] for fl in res.flags}
            c["flags"]["tp"] += len(p & g); c["flags"]["pred"] += len(p); c["flags"]["gold"] += len(g)
            if p != g:
                errors.append({"text": text[:60], "field": "flags", "gold": sorted(g), "pred": sorted(p)})
    out = {k: dict(zip(("precision", "recall"), _pr(v["tp"], v["pred"], v["gold"])), **v) for k, v in c.items()}
    tp = sum(v["tp"] for v in c.values()); pr = sum(v["pred"] for v in c.values()); go = sum(v["gold"] for v in c.values())
    out["_meta"] = {"n_texts": len(data), "micro_precision": tp / pr if pr else 1, "micro_recall": tp / go if go else 1,
                    "latency_ms_median": round(statistics.median(lat), 1), "latency_ms_max": round(max(lat), 1),
                    "modes": {m: modes.count(m) for m in set(modes)},
                    "quote_verbatim_rate": quote_ok / quote_n if quote_n else 1.0, "errors": errors,
                    "llm_errors": llm_err}
    return out


def _table(res: dict) -> str:
    lines = ["| field | precision | recall | TP | predicted | gold |", "|---|---|---|---|---|---|"]
    for k, v in res.items():
        if k.startswith("_"):
            continue
        lines.append(f"| {k} | {v['precision']:.2f} | {v['recall']:.2f} | {v['tp']} | {v['pred']} | {v['gold']} |")
    return "\n".join(lines)


def _errors(res: dict, n: int = 12) -> str:
    errs = res["_meta"]["errors"][:n]
    return "\n".join(f"- `{json.dumps(e, default=str)[:220]}`" for e in errs) or "- none"


def write_md(results: dict) -> None:
    parts = [f"# AI parsing evaluation (measured {date.today().isoformat()})", "",
             "Generated by `python3 -m tests.ai.run_eval [--live]`. Labeled set: `tests/ai/eval_data.py` — "
             f"{len(SCHEDULES)} schedule strings ({sum(len(g) for _, g in SCHEDULES)} gold events) and {len(LISTINGS)} "
             "fictional listing texts, all **synthetic test data written by us** (not real listings or people).", "",
             f"**Caveat:** the rule parsers were developed against the main set, so its rule scores are optimistic. "
             f"The HELD-OUT set ({len(SCHEDULES_HELDOUT)} schedules, {len(LISTINGS_HELDOUT)} listings) was written after "
             "tuning and the parsers were not changed in response to it; treat those numbers as the honest estimate. "
             "Both sets are small, so one error moves a score by several points.", "",
             "Matching: a predicted event matches a gold event with the same building and overlapping days. Field "
             "precision = correct / predicted (unmatched predictions count against every field); recall = correct / "
             "gold-stated. Fields the text does not state are not scored, except listing fields labeled `None` "
             "(must not be extracted). Quotes are verified in code, so a fabricated quote cannot reach the output.", ""]
    for name, r in results.items():
        m = r["_meta"]
        parts += [f"## {name}", "",
                  f"Texts: {m['n_texts']} · modes: {m['modes']} · latency median {m['latency_ms_median']} ms, max "
                  f"{m['latency_ms_max']} ms · verbatim-quote rate {m['quote_verbatim_rate']:.2f}"
                  + (f" · micro P/R {m['micro_precision']:.2f}/{m['micro_recall']:.2f}" if "micro_precision" in m else ""),
                  "", _table(r), "", "Errors (first 12):", "", _errors(r), ""]
    from ledger.ai.client import CACHE_DIR
    lat: dict = {}
    for f in CACHE_DIR.glob("*.json"):
        if f.name == "INDEX.json":
            continue
        r = json.loads(f.read_text())
        lat.setdefault((r.get("task"), r.get("model")), []).append(r.get("latency_ms") or 0)
    if lat:
        parts += ["## Live Groq latency (recorded responses in data/cache/llm)", "",
                  "Every cache file is a real API response from `python3 -m ledger.ai.seed_cache --eval` "
                  "(temperature 0, strict json_schema, reasoning_effort low, 4 s timeout, 6 s pacing). When gpt-oss-20b "
                  "was rate limited (HTTP 429) the chain fell through to gpt-oss-120b, which is why both appear.", "",
                  "| task | model | n | median ms | max ms |", "|---|---|---|---|---|"]
        for (task, model), v in sorted(lat.items()):
            parts.append(f"| {task} | {model} | {len(v)} | {statistics.median(v):.0f} | {max(v):.0f} |")
        parts.append("")
    EVAL_MD.write_text("\n".join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--cached", action="store_true")
    ap.add_argument("--pace", type=float, default=3.0)
    a = ap.parse_args()
    global PACE_S
    PACE_S = a.pace if a.live else 0.0
    results = {}
    off = LLMClient(mode="off")
    results["Schedule parser — rules only (LLM off)"] = eval_schedules(off, False)
    results["Listing extractor — rules only (LLM off)"] = eval_listings(off, False)
    results["HELD-OUT schedule parser — rules only"] = eval_schedules(off, False, SCHEDULES_HELDOUT)
    results["HELD-OUT listing extractor — rules only"] = eval_listings(off, False, LISTINGS_HELDOUT)
    if a.live or a.cached:
        llm = LLMClient(mode="live" if a.live else "cached", write_disk=False)
        tag = "live Groq" if a.live else "cache"
        results[f"Schedule parser — LLM ({tag}) + validation + rule cross-check"] = eval_schedules(llm, True)
        results[f"Listing extractor — LLM ({tag}) + validation + rule fill-in"] = eval_listings(llm, True)
        results[f"HELD-OUT schedule parser — LLM ({tag})"] = eval_schedules(llm, True, SCHEDULES_HELDOUT)
        results[f"HELD-OUT listing extractor — LLM ({tag})"] = eval_listings(llm, True, LISTINGS_HELDOUT)
        results["_llm_status"] = {"_meta": llm.status()}
    status = results.pop("_llm_status", None)
    write_md(results)
    for k, v in results.items():
        print(k, {f: (round(x["precision"], 2), round(x["recall"], 2)) for f, x in v.items() if not f.startswith("_")})
        print("   ", {x: v["_meta"][x] for x in v["_meta"] if x not in ("errors", "llm_errors")})
        if v["_meta"].get("llm_errors"):
            print("    llm_errors:", v["_meta"]["llm_errors"][:3])
    if status:
        print("llm", status["_meta"])


if __name__ == "__main__":
    main()
