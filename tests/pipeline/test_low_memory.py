"""LOW_MEMORY=1: label tables are memory-mapped from uncompressed .npy copies; values are identical."""
import numpy as np

from ledger.pipeline import transit


def test_labels_mmap_roundtrip(tmp_path, monkeypatch):
    rng = np.random.default_rng(0)
    arrays = {"bwd": rng.integers(0, 60000, (2, 3, 4, 5), dtype=np.uint16), "building_ids": np.array(["a", "b"])}
    np.savez_compressed(tmp_path / "labels.npz", **arrays)
    monkeypatch.setenv("LOW_MEMORY", "0")
    heap = transit._load_labels(tmp_path)
    monkeypatch.setenv("LOW_MEMORY", "1")
    mm = transit._load_labels(tmp_path)
    assert isinstance(mm["bwd"], np.memmap)
    for k, v in arrays.items():
        assert np.array_equal(heap[k], v) and np.array_equal(mm[k], v)
    # idempotent: a second export reuses the files
    assert transit.export_labels_mmap(tmp_path) == tmp_path / transit.LABELS_MMAP_DIR
