"""The cost-carrying kernels must reproduce ledger.pipeline.csa time labels exactly (random scans on the Ann Arbor
artifacts if present)."""
import numpy as np
import pytest

from ledger.pipeline import config as C


@pytest.mark.skipif(not (C.ARTIFACT_DIR / "transit.npz").is_file(), reason="routing artifacts not built")
def test_labels_match_pipeline_csa():
    import json
    from ledger.multicity.csa_cost import NEG, CostScanner
    from ledger.pipeline.csa import Timetable
    from ledger.pipeline.gtfs import TransitNetwork
    man = json.loads((C.ARTIFACT_DIR / "manifest.json").read_text())
    z = np.load(C.ARTIFACT_DIR / "transit.npz")
    meta = man.get("daytypes") or man.get("transit", {}).get("daytypes")
    if not meta:
        pytest.skip("manifest layout unknown")
    net = TransitNetwork.from_arrays(z, meta, {d: i for i, m in enumerate(meta) for d in m["days"]})
    tt = Timetable(net, net.daytypes[0])
    sc = CostScanner(tt)
    rng = np.random.default_rng(1)
    for _ in range(30):
        s = rng.choice(tt.n_stops, 3, replace=False)
        w = rng.uniform(0, 600, 3)
        T = int(rng.integers(7 * 3600, 23 * 3600))
        LV, CV = sc.backward(s, w, T)
        assert np.array_equal(LV, tt.backward([(int(a), int(round(b))) for a, b in zip(s, w)], T))
        assert np.all(CV[LV > NEG] >= 0)
        EV, _ = sc.forward(s, w, T)
        assert np.array_equal(EV, tt.forward([(int(a), int(round(b))) for a, b in zip(s, w)], T))
