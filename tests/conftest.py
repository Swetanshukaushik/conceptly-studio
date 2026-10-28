"""Tests never spend money: live model calls are blocked unless the run is started with --live.
Tests that genuinely need a real model are marked @pytest.mark.live and are skipped by default."""
import os
import tempfile

import pytest


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="allow tests marked 'live' to call paid models (costs money)")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: test calls a real paid model; skipped unless --live is given")
    if not config.getoption("--live"):
        os.environ["CONCEPTLY_BLOCK_LIVE"] = "1"   # checked by every paid-call site (src/services/media/usage.py)
    os.environ.setdefault("CONCEPTLY_USAGE_LOG", os.path.join(tempfile.gettempdir(), "conceptly_test_usage_log.jsonl"))


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="calls a paid model; run with --live to include")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
