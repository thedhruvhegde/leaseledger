#!/usr/bin/env python3
"""Tiny LLM endpoint probe for Hack the Lease (stdlib only).

Usage: python3 llm_probe.py
Sends NO personal data. Uses a dummy key; the container proxy injects real credentials.
Probes: model listing (Groq, OpenRouter), one tiny chat completion each, and a
JSON-schema structured-output request on Groq.
"""
import json, os, time, urllib.request, urllib.error

DUMMY = "sk-dummy"
ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def call(method, url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {DUMMY}",
        "Content-Type": "application/json",
        "User-Agent": "hackathon-probe/0.1",
    })
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode())
            status = r.status
    except urllib.error.HTTPError as e:
        payload = {"error": e.read().decode()[:600]}
        status = e.code
    except Exception as e:  # network / proxy failure
        payload = {"error": repr(e)}
        status = None
    return status, round((time.perf_counter() - t0) * 1000), payload


SCHEMA = {
    "name": "schedule_block",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "blocks": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "days": {"type": "array", "items": {"type": "string",
                             "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}},
                    "start": {"type": "string"},
                    "place": {"type": "string"},
                    "source_span": {"type": "string"},
                },
                "required": ["days", "start", "place", "source_span"]}},
        },
        "required": ["blocks"],
    },
}
SCHED_TEXT = "MWF 9am EECS on North, TTh 2pm Ross, gym 7pm CCRB"


def main():
    results = {}
    for name, base in ENDPOINTS.items():
        s, ms, p = call("GET", f"{base}/models")
        ids = [m.get("id") for m in p.get("data", [])] if isinstance(p, dict) else []
        results[f"{name}_models"] = {"status": s, "ms": ms, "count": len(ids), "ids": ids}
        print(f"[{name}] GET /models -> {s} in {ms} ms, {len(ids)} models")

    # NOTE: Groq's edge (Cloudflare) returns 403 "error code: 1010" if no User-Agent is set.
    # OpenRouter account has NO credits: only ":free" models work, and they are often 429 upstream.
    chat_targets = [
        ("groq", "openai/gpt-oss-20b"),
        ("groq", "openai/gpt-oss-120b"),
        ("groq", "qwen/qwen3.8-27b"),
        ("openrouter", os.environ.get("OR_MODEL", "nvidia/nemotron-3.5-lightning:free")),
    ]
    for name, model in chat_targets:
        body = {"model": model, "temperature": 0, "max_tokens": 300,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}
        s, ms, p = call("POST", f"{ENDPOINTS[name]}/chat/completions", body)
        txt = p.get("choices", [{}])[0].get("message", {}).get("content") if "choices" in p else p
        results[f"{name}_chat"] = {"status": s, "ms": ms, "model": model, "out": txt,
                                   "usage": p.get("usage")}
        print(f"[{name}] chat {model} -> {s} in {ms} ms: {str(txt)[:120]}")

    # Structured output (json_schema) test on Groq
    for model in os.environ.get("GROQ_SO_MODELS", "openai/gpt-oss-20b,openai/gpt-oss-120b").split(","):
        body = {"model": model, "temperature": 0,
                "response_format": {"type": "json_schema", "json_schema": SCHEMA},
                "messages": [
                    {"role": "system", "content": "Extract weekly schedule blocks. source_span must be copied verbatim from the input."},
                    {"role": "user", "content": SCHED_TEXT}]}
        s, ms, p = call("POST", f"{ENDPOINTS['groq']}/chat/completions", body)
        txt = p.get("choices", [{}])[0].get("message", {}).get("content") if "choices" in p else p
        results[f"groq_so_{model}"] = {"status": s, "ms": ms, "out": txt}
        print(f"[groq json_schema] {model} -> {s} in {ms} ms: {str(txt)[:300]}")
        if s == 200:
            try:
                blocks = json.loads(txt)["blocks"]
                ok = all(b["source_span"] in SCHED_TEXT for b in blocks)
                print(f"   parsed {len(blocks)} blocks; all source_spans verbatim: {ok}")
            except Exception as e:
                print("   parse failed:", e)

    lease_extraction_test(results)
    narration_grounding_test(results)

    out = os.path.join(os.path.dirname(__file__), "llm_probe_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print("saved", out)


LISTING = ("Spacious 2BR near Central Campus. Rent $1,850/mo. Water and trash included; tenant pays DTE electric and gas. "
           "12-month lease starting Sept 1. One-time admin fee $150, security deposit equal to 1.5 months rent. "
           "Cats allowed with $300 non-refundable pet fee; no dogs. Street parking only, permits available from city.")
LEASE_SCHEMA = {"name": "lease_facts", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["facts"],
    "properties": {"facts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["field", "value", "quote"],
        "properties": {
            "field": {"type": "string", "enum": ["rent_monthly", "utilities_included", "utilities_tenant_pays",
                                                 "lease_term_months", "fee", "deposit", "pet_policy", "parking"]},
            "value": {"type": "string"}, "quote": {"type": "string"}}}}}}}


def lease_extraction_test(results):
    import re
    for model in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
        body = {"model": model, "temperature": 0,
                "response_format": {"type": "json_schema", "json_schema": LEASE_SCHEMA},
                "messages": [{"role": "system", "content": "Extract lease facts. 'quote' MUST be an exact verbatim substring of the listing. Omit anything not stated."},
                             {"role": "user", "content": LISTING}]}
        s, ms, p = call("POST", f"{ENDPOINTS['groq']}/chat/completions", body)
        if s != 200:
            print(f"[extract] {model} -> {s}"); continue
        facts = json.loads(p["choices"][0]["message"]["content"])["facts"]
        verbatim = sum(f["quote"] in LISTING for f in facts)
        uniq = len({(f["field"], f["value"]) for f in facts})
        # numeric check: every number in value must occur in its quote
        num_ok = all(set(re.findall(r"\d+(?:[,.]\d+)*", f["value"])) <= set(re.findall(r"\d+(?:[,.]\d+)*", f["quote"])) for f in facts)
        results[f"extract_{model}"] = {"ms": ms, "n": len(facts), "unique": uniq, "verbatim": verbatim,
                                       "numbers_in_quote": num_ok, "facts": facts}
        print(f"[extract] {model} {ms} ms facts={len(facts)} unique={uniq} verbatim={verbatim} numbers_in_quote={num_ok}")


def narration_grounding_test(results):
    import re
    facts = {"A": {"name": "Maple Apts", "rent_per_person": 925, "commute_min_weekly": 142, "late_walk_after_11pm_min": 18},
             "B": {"name": "Oak House", "rent_per_person": 1010, "commute_min_weekly": 96, "late_walk_after_11pm_min": 7},
             "diff": {"rent_per_person": 85, "commute_min_weekly": 46}}
    body = {"model": "openai/gpt-oss-120b", "temperature": 0, "messages": [
        {"role": "system", "content": "Write 2 sentences comparing the options using ONLY numbers present in FACTS. No other numbers."},
        {"role": "user", "content": "FACTS=" + json.dumps(facts)}]}
    s, ms, p = call("POST", f"{ENDPOINTS['groq']}/chat/completions", body)
    if s != 200:
        print("[narrate] failed", s); return
    txt = p["choices"][0]["message"]["content"]
    allowed = set()
    def walk(o):
        if isinstance(o, dict): [walk(v) for v in o.values()]
        elif isinstance(o, (int, float)): allowed.add(float(o))
    walk(facts)
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", txt)]
    bad = [n for n in nums if n not in allowed]
    results["narration"] = {"ms": ms, "text": txt, "numbers": nums, "unsupported": bad}
    print(f"[narrate] {ms} ms unsupported_numbers={bad}\n  {txt}")


if __name__ == "__main__":
    main()
