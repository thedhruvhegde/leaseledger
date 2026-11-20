"""Shared fixtures: the real provider built from data/artifacts (run `make data` first)."""
from __future__ import annotations

import pytest

from ledger.pipeline import config as C


@pytest.fixture(scope="session")
def provider():
    if not (C.ARTIFACT_DIR / "labels.npz").is_file():
        pytest.skip("routing artifacts missing: run `make data`")
    from ledger.pipeline.transit import TransitProvider
    return TransitProvider()


@pytest.fixture(scope="session")
def weekday_tt(provider):
    return provider.tts[provider.net.day_to_type["T"]]


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: performance measurements on the real feed (deselect with -m 'not slow')")
