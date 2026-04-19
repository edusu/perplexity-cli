"""Shared pytest fixtures for perplexity-cli tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(relative_path: str) -> Any:
    """Load a JSON fixture by path relative to tests/fixtures/.

    Args:
        relative_path: e.g. "finance/quote_nvda.json".

    Returns:
        Parsed JSON content.
    """
    return json.loads((FIXTURES_DIR / relative_path).read_text())


@pytest.fixture
def mock_core() -> MagicMock:
    """A MagicMock ClientCore with `get_json` as an AsyncMock.

    Tests set `mock_core.get_json.return_value = ...` or `.side_effect = ...`
    to drive FinanceAPI behavior without hitting the network.
    """
    core = MagicMock()
    core.get_json = AsyncMock()
    return core
