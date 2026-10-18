import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="run tests that call the hosted models (slow, uses API quota)")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls hosted models; run with --live")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="needs --live (calls hosted models)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def reference_nutrition():
    return json.loads((FIXTURES / "reference_nutrition.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def reference_currency():
    return json.loads((FIXTURES / "reference_currency.json").read_text(encoding="utf-8"))
