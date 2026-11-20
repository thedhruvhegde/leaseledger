"""Curated /api/methods equations: required set present, shape, and KaTeX-safe syntax (balanced braces,
known environments). Full KaTeX rendering is checked when node + web/node_modules/katex exist."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ledger.api.methods_content import EQUATIONS, LIMITATIONS

REQUIRED = {"generalized_trip_cost", "value_of_time", "day_tour", "monthly_ledger", "utilities_heating", "breakeven",
            "monte_carlo", "envy_free_lp", "csa_backward", "weather_factor"}
KATEX = Path(__file__).resolve().parents[2] / "web" / "node_modules" / "katex"


def _balanced(s: str) -> bool:
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        depth += {"{": 1, "}": -1}.get(c, 0)
        if depth < 0:
            return False
        i += 1
    return depth == 0


def test_equations_shape():
    ids = [e["id"] for e in EQUATIONS]
    assert REQUIRED <= set(ids) and len(ids) == len(set(ids))
    for e in EQUATIONS:
        assert {"id", "title", "latex", "meaning"} <= set(e)
        assert _balanced(e["latex"]), e["id"]
        assert e["latex"].count(r"\begin{") == e["latex"].count(r"\end{")
        assert "$$" not in e["latex"]
    assert len(LIMITATIONS) >= 9 and all(isinstance(x, str) and x for x in LIMITATIONS)


def test_methods_endpoint_serves_equations(client):
    j = client.get("/api/methods").json()
    assert [e["id"] for e in j["equations"]] == [e["id"] for e in EQUATIONS]
    assert all(e["name"] == e["title"] and e["explanation"] == e["meaning"] for e in j["equations"])
    assert j["limitations"] == LIMITATIONS


@pytest.mark.skipif(not (shutil.which("node") and KATEX.is_dir()), reason="node/katex not installed")
def test_katex_renders(tmp_path):
    f = tmp_path / "eq.json"
    f.write_text(json.dumps([e["latex"] for e in EQUATIONS]))
    js = ("const k=require(%s);const eqs=require(%s);let bad=[];eqs.forEach((e,i)=>{try{k.renderToString(e,"
          "{throwOnError:true,displayMode:true,strict:'error'})}catch(x){bad.push(i+': '+x.message)}});"
          "console.log(JSON.stringify(bad))") % (json.dumps(str(KATEX)), json.dumps(str(f)))
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout.strip().splitlines()[-1]) == []
