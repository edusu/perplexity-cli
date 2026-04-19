# Perplexity Finance Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `FinanceAPI` Python namespace and a `perplexity finance` CLI subgroup that wrap the ~30 REST JSON endpoints under `/rest/finance/`, plus an `ask --finance` flag, following the architecture and typing defined in `docs/superpowers/specs/2026-04-19-finance-integration-design.md`.

**Architecture:** New `_finance.py` (FinanceAPI) and `cli/finance.py` layered on top of the existing `ClientCore.get_json()` (already present in `_core.py:139`). New dataclasses added to `types.py`. `FinanceAPI` exposed as `client.finance` on `PerplexityClient`. The Click CLI group registers alongside existing commands in `cli/__init__.py`.

**Tech Stack:** Python 3.10+, httpx (already used), Click, Rich (tables + colors), pytest + pytest-asyncio (already dev-deps). No new runtime dependencies.

---

## File Structure

**New files:**
- `src/perplexity/_finance.py` — `FinanceAPI` class with one async method per endpoint family.
- `src/perplexity/cli/finance.py` — Click sub-group with one command per user-facing vertical.
- `tests/__init__.py`, `tests/conftest.py` — test scaffolding (pytest-asyncio config, fake client fixture).
- `tests/fixtures/finance/*.json` — recorded JSON samples from the recon session, used to avoid live-hitting the API in unit tests.
- `tests/test_finance_api.py` — unit tests for `FinanceAPI`.
- `tests/test_cli_finance.py` — CLI smoke tests using `click.testing.CliRunner` with a mocked client.

**Modified files:**
- `src/perplexity/types.py` — add finance dataclasses (~15 new types).
- `src/perplexity/exceptions.py` — add `FinanceError`.
- `src/perplexity/client.py` — wire `FinanceAPI` as `self.finance`.
- `src/perplexity/cli/__init__.py` — register the new `finance` group.
- `src/perplexity/cli/chat.py` — add `--finance` flag to `ask`.

---

## Task 1: Test scaffolding + FinanceError exception

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_exceptions.py`
- Modify: `src/perplexity/exceptions.py`

- [ ] **Step 1: Create empty test package marker**

Create `tests/__init__.py` with content:

```python
```

(empty file — just the package marker)

- [ ] **Step 2: Create `tests/conftest.py`**

```python
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
```

- [ ] **Step 3: Write failing test for `FinanceError`**

Create `tests/test_exceptions.py`:

```python
"""Tests for the exception hierarchy."""

from __future__ import annotations

from perplexity.exceptions import FinanceError, PerplexityError


def test_finance_error_is_perplexity_error() -> None:
    """FinanceError must inherit from PerplexityError for uniform handling."""
    assert issubclass(FinanceError, PerplexityError)


def test_finance_error_carries_message() -> None:
    exc = FinanceError("Unknown ticker: XYZ")
    assert str(exc) == "Unknown ticker: XYZ"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_exceptions.py -v`
Expected: FAIL with `ImportError: cannot import name 'FinanceError' from 'perplexity.exceptions'`.

- [ ] **Step 5: Add `FinanceError` to `exceptions.py`**

Append to `src/perplexity/exceptions.py`:

```python
class FinanceError(PerplexityError):
    """Raised when a finance API request returns an error or unknown ticker."""
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_exceptions.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Commit**

```bash
git add tests/__init__.py tests/conftest.py tests/test_exceptions.py src/perplexity/exceptions.py
git commit -m "test: add test scaffolding and FinanceError exception"
```

---

## Task 2: Finance dataclasses in `types.py`

**Files:**
- Modify: `src/perplexity/types.py`
- Create: `tests/test_finance_types.py`

- [ ] **Step 1: Write failing test for dataclass shapes**

Create `tests/test_finance_types.py`:

```python
"""Tests that finance dataclasses accept their declared fields."""

from __future__ import annotations

from perplexity.types import (
    AutosuggestHit,
    CompanyProfile,
    FixedIncomeItem,
    HistoryPoint,
    Index,
    MovementSummary,
    Mover,
    NewsEntry,
    PortfolioOverview,
    PredictionMarket,
    PredictionOption,
    Quote,
    Sector,
    Sentiment,
    Source,
    SummaryItem,
    TimelineEntry,
    Watchlist,
    WatchlistSummary,
)


def test_quote_minimal_fields() -> None:
    q = Quote(
        symbol="NVDA",
        name="NVIDIA Corporation",
        price=201.68,
        change=3.33,
        change_percent=1.6789,
        currency="USD",
        exchange="NASDAQ",
        is_crypto=False,
        is_market_open=False,
    )
    assert q.symbol == "NVDA"
    assert q.history is None
    assert q.market_cap is None


def test_quote_with_history() -> None:
    q = Quote(
        symbol="NVDA",
        name="NVIDIA",
        price=1.0,
        change=0.0,
        change_percent=0.0,
        currency="USD",
        exchange="NASDAQ",
        is_crypto=False,
        is_market_open=True,
        history=[HistoryPoint(date="2026-04-17T00:00:00-04:00", close=7078.5)],
    )
    assert len(q.history) == 1
    assert q.history[0].close == 7078.5


def test_mover_fields() -> None:
    m = Mover(
        symbol="NVDA",
        name="NVIDIA",
        price=201.68,
        change=3.33,
        change_percent=1.67,
        currency="USD",
        sector="Technology",
        industry="Semiconductors",
    )
    assert m.sector == "Technology"


def test_index_optional_history() -> None:
    i = Index(
        symbol="ESUSD",
        name="S&P Futures",
        price=7161.5,
        change=84.5,
        change_percent=1.194,
        currency="USD",
        exchange="COMMODITY",
    )
    assert i.history is None


def test_prediction_market_with_options() -> None:
    opt = PredictionOption(
        id="1",
        question="↑ $110",
        probability=0.5,
        outcomes=["Yes", "No"],
        outcome_prices=[0.5, 0.5],
        volume=1000.0,
    )
    pm = PredictionMarket(
        id="305510",
        title="What will WTI Crude Oil hit in April 2026?",
        provider="polymarket",
        slug="what-price-will-wti-hit-in-april-2026",
        volume=42_122_308.12,
        currency="USD",
        start_date="2026-03-25T04:01:18.598000Z",
        end_date="2026-04-30T00:00:00Z",
        markets=[opt],
    )
    assert pm.markets[0].question == "↑ $110"


def test_movement_summary_reuses_source() -> None:
    ms = MovementSummary(
        explanation="NVDA rose on AI demand.",
        sources=[Source(name="AOL", url="https://aol.com/x", snippet="...")],
    )
    assert ms.sources[0].url == "https://aol.com/x"


def test_company_profile_optional_fields() -> None:
    cp = CompanyProfile(
        symbol="AAPL",
        company_name="Apple Inc.",
        description="Apple designs…",
        industry="Consumer Electronics",
        exchange="NASDAQ",
    )
    assert cp.website is None


def test_watchlist_is_list_of_symbols() -> None:
    wl = Watchlist(symbols=["AMZN", "NVDA"])
    assert wl.symbols == ["AMZN", "NVDA"]


def test_summary_item_has_header_and_detail() -> None:
    s = SummaryItem(header="Oil plunges", detail="Oil fell 12%.")
    assert s.header == "Oil plunges"


def test_autosuggest_hit_has_kind() -> None:
    a = AutosuggestHit(symbol="AAPL", name="Apple Inc.", kind="stock")
    assert a.kind == "stock"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_finance_types.py -v`
Expected: FAIL (ImportError for the new types).

- [ ] **Step 3: Add dataclasses to `types.py`**

Append to `src/perplexity/types.py` (after existing types):

```python
@dataclass
class HistoryPoint:
    """A single intraday price point.

    Attributes:
        date: ISO-8601 timestamp (with exchange timezone offset).
        close: Closing price at that moment.
    """

    date: str
    close: float


@dataclass
class Quote:
    """Price quote for a stock, crypto, index, or ETF.

    Populated from `/rest/finance/quote/{TICKER}`.
    """

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    currency: str
    exchange: str
    is_crypto: bool
    is_market_open: bool
    market_cap: float | None = None
    volume: float | None = None
    avg_volume: float | None = None
    day_low: float | None = None
    day_high: float | None = None
    year_low: float | None = None
    year_high: float | None = None
    pe: float | None = None
    eps: float | None = None
    open_price: float | None = None
    previous_close: float | None = None
    after_hours_price: float | None = None
    after_hours_change: float | None = None
    after_hours_percent_change: float | None = None
    history: list[HistoryPoint] | None = None


@dataclass
class Mover:
    """A symbol in a movers / top-z-scores list."""

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    currency: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None


@dataclass
class Index:
    """A market index (S&P Futures, crypto indices, etc.)."""

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    currency: str
    exchange: str
    history: list[HistoryPoint] | None = None


@dataclass
class Sector:
    """A sector ETF entry."""

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    currency: str
    market_cap: float | None = None


@dataclass
class FixedIncomeItem:
    """A fixed-income instrument (bond, yield curve point, etc.)."""

    symbol: str
    name: str
    price: float
    change: float
    change_percent: float


@dataclass
class SummaryItem:
    """A bullet in the market summary feed."""

    header: str
    detail: str


@dataclass
class CompanyProfile:
    """Company profile from `/rest/finance/profile/{TICKER}`."""

    symbol: str
    company_name: str
    description: str
    industry: str
    exchange: str
    website: str | None = None
    cik: str | None = None
    isin: str | None = None


@dataclass
class TimelineEntry:
    """Narrative news timeline entry for a ticker."""

    ticker: str
    description: str
    last_modified: str
    source_urls: list[str]


@dataclass
class NewsEntry:
    """A news article (publisher news or market news)."""

    title: str
    url: str
    published_at: str | None = None
    publisher: str | None = None


@dataclass
class MovementSummary:
    """AI-generated explanation of a ticker's move, with sources."""

    explanation: str
    sources: list[Source]


@dataclass
class Sentiment:
    """Market sentiment snapshot."""

    score: float
    label: str


@dataclass
class PredictionOption:
    """A single outcome within a prediction market."""

    id: str
    question: str
    probability: float
    outcomes: list[str]
    outcome_prices: list[float]
    volume: float


@dataclass
class PredictionMarket:
    """A Polymarket-backed prediction market."""

    id: str
    title: str
    provider: str
    slug: str
    volume: float
    currency: str
    start_date: str
    end_date: str
    markets: list[PredictionOption] = field(default_factory=list)
    icon: str | None = None


@dataclass
class Watchlist:
    """The user's watchlist — just the symbols (logos and quotes fetched separately)."""

    symbols: list[str]


@dataclass
class WatchlistSummary:
    """Aggregate summary of the watchlist (headline movers, etc.)."""

    items: list[SummaryItem] = field(default_factory=list)


@dataclass
class PortfolioOverview:
    """User's Plaid-linked portfolio overview. None means no linked account."""

    total_value: float
    day_change: float
    day_change_percent: float
    accounts: list[dict] = field(default_factory=list)


@dataclass
class AutosuggestHit:
    """An autosuggest search result for tickers."""

    symbol: str
    name: str
    kind: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_finance_types.py -v`
Expected: PASS (all 10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/types.py tests/test_finance_types.py
git commit -m "feat(types): add finance dataclasses (Quote, Mover, Index, etc.)"
```

---

## Task 3: Capture real-response fixtures

**Files:**
- Create: `tests/fixtures/finance/quote_nvda.json`
- Create: `tests/fixtures/finance/market_movers.json`
- Create: `tests/fixtures/finance/top_indices_market.json`
- Create: `tests/fixtures/finance/market_summary.json`
- Create: `tests/fixtures/finance/profile_aapl.json`
- Create: `tests/fixtures/finance/timeline_aapl.json`
- Create: `tests/fixtures/finance/movement_summary_nvda.json`
- Create: `tests/fixtures/finance/predictions_finance.json`
- Create: `tests/fixtures/finance/watchlist.json`
- Create: `tests/fixtures/finance/equity_sectors.json`

These are trimmed, anonymized real responses used to drive unit tests without hitting the network.

- [ ] **Step 1: Create the fixtures directory and write trimmed JSON samples**

Write `tests/fixtures/finance/quote_nvda.json`:

```json
{
  "isCrypto": false,
  "symbol": "NVDA",
  "name": "NVIDIA Corporation",
  "price": 201.68,
  "change": 3.33,
  "changesPercentage": 1.6789,
  "currency": "USD",
  "exchange": "NASDAQ",
  "exchangeName": "NASDAQ",
  "exchangeCountry": "US",
  "isMarketOpen": false,
  "marketCap": 4901832394151.0,
  "volume": 153662565.0,
  "avgVolume": 177373700.0,
  "dayLow": 199.27,
  "dayHigh": 201.7,
  "yearLow": 95.04,
  "yearHigh": 212.19,
  "pe": 41.16,
  "eps": 4.9,
  "open": 199.9,
  "previousClose": 198.35,
  "afterHoursPrice": 200.96,
  "afterHoursChange": -0.72,
  "afterHoursPercentChange": -0.357,
  "history": [
    {"date": "2026-04-17T09:30:00-04:00", "close": 199.5},
    {"date": "2026-04-17T09:35:00-04:00", "close": 200.1}
  ]
}
```

Write `tests/fixtures/finance/market_movers.json`:

```json
{
  "movers": [
    {
      "symbol": "NVDA",
      "name": "NVIDIA Corporation",
      "price": 201.68,
      "change": 3.33,
      "changesPercentage": 1.67885,
      "currency": "USD",
      "marketCap": 4901832394151.0,
      "sector": "Technology",
      "industry": "Semiconductors"
    },
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "price": 270.23,
      "change": 6.83,
      "changesPercentage": 2.59301,
      "currency": "USD",
      "marketCap": 3971820706468.99,
      "sector": "Technology",
      "industry": "Consumer Electronics"
    }
  ]
}
```

Write `tests/fixtures/finance/top_indices_market.json`:

```json
[
  {
    "symbol": "ESUSD",
    "name": "S&P Futures",
    "price": 7161.5,
    "change": 84.5,
    "changesPercentage": 1.194,
    "currency": "USD",
    "exchange": "COMMODITY",
    "history": [
      {"date": "2026-04-17T00:00:00-04:00", "close": 7078.5},
      {"date": "2026-04-17T00:05:00-04:00", "close": 7080.5}
    ]
  },
  {
    "symbol": "DJI",
    "name": "Dow Jones",
    "price": 45000.0,
    "change": 200.0,
    "changesPercentage": 0.44,
    "currency": "USD",
    "exchange": "INDEX"
  }
]
```

Write `tests/fixtures/finance/market_summary.json`:

```json
{
  "data": {
    "summary": [
      {"header": "Crude Oil Plunges 12.78%", "detail": "Oil prices cratered after Iran briefly reopened the Strait of Hormuz."},
      {"header": "U.S.-Iran Talks Show Progress", "detail": "Both sides cited advancement in negotiations."}
    ]
  }
}
```

Write `tests/fixtures/finance/profile_aapl.json`:

```json
{
  "symbol": "AAPL",
  "companyName": "Apple Inc.",
  "description": "Apple Inc. designs, manufactures, and markets smartphones...",
  "industry": "Consumer Electronics",
  "exchange": "NASDAQ",
  "website": "https://www.apple.com",
  "cik": "0000320193",
  "isin": "US0378331005"
}
```

Write `tests/fixtures/finance/timeline_aapl.json`:

```json
[
  {
    "ticker": "AAPL",
    "last_modified": "2026-04-17T21:56:50.837727-04:00",
    "description": "Apple closed up nearly 2.6%, riding a broad market surge.",
    "source_urls": [
      "https://www.cnbc.com/2026/04/17/oil-strait-hormuz-iran",
      "https://seekingalpha.com/news/4574778-apple-bofa"
    ]
  }
]
```

Write `tests/fixtures/finance/movement_summary_nvda.json`:

```json
{
  "explanation": "NVDA rose on continued bullish momentum driven by strong AI demand signals.",
  "sources": [
    {
      "url": "https://www.aol.com/prediction-ai-stock.html",
      "title": "Prediction: AI Stock Will Become First $20T Company",
      "snippet": "Nvidia currently trades for about $201 per share..."
    }
  ]
}
```

Write `tests/fixtures/finance/predictions_finance.json`:

```json
[
  {
    "provider": "polymarket",
    "title": "What will WTI Crude Oil hit in April 2026?",
    "slug": "what-price-will-wti-hit-in-april-2026",
    "id": "305510",
    "icon": "https://polymarket-upload.s3.us-east-2.amazonaws.com/crude-oil.png",
    "volume": 42122308.12,
    "currency": "USD",
    "startDate": "2026-03-25T04:01:18.598000Z",
    "endDate": "2026-04-30T00:00:00Z",
    "markets": [
      {
        "id": "1712298",
        "question": "↑ $110",
        "probability": 1.0,
        "outcomes": ["Yes", "No"],
        "outcomePrices": [1.0, 0.0],
        "volume": 898046.95,
        "startDate": "2026-03-25T04:07:18.777000Z"
      }
    ]
  }
]
```

Write `tests/fixtures/finance/watchlist.json`:

```json
[
  {"symbol": "AMZN", "image": "https://finance-logo.perplexity.ai/ticker/AMZN.png", "image_dark": "https://finance-logo.perplexity.ai/ticker/AMZN.png?theme=dark"},
  {"symbol": "NVDA", "image": "https://finance-logo.perplexity.ai/ticker/NVDA.png", "image_dark": "https://finance-logo.perplexity.ai/ticker/NVDA.png?theme=dark"}
]
```

Write `tests/fixtures/finance/equity_sectors.json`:

```json
[
  {
    "symbol": "XLK",
    "name": "Technology",
    "price": 154.35,
    "change": 2.33,
    "changesPercentage": 1.53269,
    "currency": "USD",
    "exchange": "AMEX",
    "marketCap": 83983684422.0
  },
  {
    "symbol": "XLE",
    "name": "Energy",
    "price": 55.02,
    "change": -1.56,
    "changesPercentage": -2.75716,
    "currency": "USD",
    "exchange": "AMEX",
    "marketCap": 37353505505.0
  }
]
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/
git commit -m "test: add recorded JSON fixtures for finance endpoints"
```

---

## Task 4: `FinanceAPI` skeleton + individual-ticker methods

**Files:**
- Create: `src/perplexity/_finance.py`
- Modify: `src/perplexity/client.py`
- Create: `tests/test_finance_api.py`

Implements: `quote`, `profile`, `why_moving`, `timeline`, `ticker_news`.

- [ ] **Step 1: Write failing tests for ticker methods**

Create `tests/test_finance_api.py`:

```python
"""Unit tests for FinanceAPI — uses mocked ClientCore, no network."""

from __future__ import annotations

import pytest

from perplexity._finance import FinanceAPI
from perplexity.exceptions import FinanceError
from perplexity.types import (
    CompanyProfile,
    MovementSummary,
    NewsEntry,
    Quote,
    TimelineEntry,
)

from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_quote_parses_core_fields(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/quote_nvda.json")
    api = FinanceAPI(mock_core)
    q = await api.quote("NVDA")
    assert isinstance(q, Quote)
    assert q.symbol == "NVDA"
    assert q.name == "NVIDIA Corporation"
    assert q.price == pytest.approx(201.68)
    assert q.change_percent == pytest.approx(1.6789)
    assert q.currency == "USD"
    assert q.market_cap == pytest.approx(4901832394151.0)
    assert q.is_crypto is False
    assert q.is_market_open is False
    # URL must include the TICKER and default query params
    called_url = mock_core.get_json.call_args.args[0]
    assert "/rest/finance/quote/NVDA" in called_url
    assert "with_history=false" in called_url


@pytest.mark.asyncio
async def test_quote_with_history(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/quote_nvda.json")
    api = FinanceAPI(mock_core)
    q = await api.quote("NVDA", with_history=True)
    assert q.history is not None
    assert len(q.history) == 2
    assert q.history[0].close == pytest.approx(199.5)
    called_url = mock_core.get_json.call_args.args[0]
    assert "with_history=true" in called_url


@pytest.mark.asyncio
async def test_quote_uppercases_ticker(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/quote_nvda.json")
    api = FinanceAPI(mock_core)
    await api.quote("nvda")
    called_url = mock_core.get_json.call_args.args[0]
    assert "/rest/finance/quote/NVDA" in called_url


@pytest.mark.asyncio
async def test_profile(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/profile_aapl.json")
    api = FinanceAPI(mock_core)
    p = await api.profile("AAPL")
    assert isinstance(p, CompanyProfile)
    assert p.company_name == "Apple Inc."
    assert p.industry == "Consumer Electronics"
    assert p.website == "https://www.apple.com"


@pytest.mark.asyncio
async def test_why_moving(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/movement_summary_nvda.json")
    api = FinanceAPI(mock_core)
    m = await api.why_moving("NVDA")
    assert isinstance(m, MovementSummary)
    assert "AI demand" in m.explanation
    assert len(m.sources) == 1
    assert m.sources[0].url.startswith("https://")


@pytest.mark.asyncio
async def test_timeline(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/timeline_aapl.json")
    api = FinanceAPI(mock_core)
    entries = await api.timeline("AAPL", limit=5)
    assert len(entries) == 1
    assert isinstance(entries[0], TimelineEntry)
    assert entries[0].ticker == "AAPL"
    assert len(entries[0].source_urls) == 2
    called_url = mock_core.get_json.call_args.args[0]
    assert "limit=5" in called_url


@pytest.mark.asyncio
async def test_ticker_news_empty_returns_empty_list(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    news = await api.ticker_news("AAPL")
    assert news == []


@pytest.mark.asyncio
async def test_quote_raises_finance_error_on_none(mock_core) -> None:
    """Some tickers 404 → get_json raises; but when payload is missing symbol, raise FinanceError."""
    mock_core.get_json.return_value = {}
    api = FinanceAPI(mock_core)
    with pytest.raises(FinanceError):
        await api.quote("BOGUS")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_finance_api.py -v`
Expected: FAIL (ImportError for `perplexity._finance`).

- [ ] **Step 3: Create `_finance.py` with ticker methods**

Create `src/perplexity/_finance.py`:

```python
"""Finance API for Perplexity.

Wraps the REST JSON endpoints under `/rest/finance/` exposed by the
Perplexity `/finance` web UI. All endpoints are plain JSON GETs with
cookie auth — no SSE.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from perplexity._core import PERPLEXITY_BASE_URL, ClientCore
from perplexity.exceptions import FinanceError
from perplexity.types import (
    AutosuggestHit,
    CompanyProfile,
    FixedIncomeItem,
    HistoryPoint,
    Index,
    MovementSummary,
    Mover,
    NewsEntry,
    PortfolioOverview,
    PredictionMarket,
    PredictionOption,
    Quote,
    Sector,
    Sentiment,
    Source,
    SummaryItem,
    TimelineEntry,
    Watchlist,
    WatchlistSummary,
)

logger = logging.getLogger(__name__)

FINANCE_BASE = f"{PERPLEXITY_BASE_URL}/rest/finance"


def _build_url(path: str, params: dict[str, Any] | None = None) -> str:
    """Join the finance base with a path and URL-encoded params."""
    url = f"{FINANCE_BASE}{path}"
    if params:
        encoded = urlencode({k: _fmt(v) for k, v in params.items() if v is not None})
        if encoded:
            url = f"{url}?{encoded}"
    return url


def _fmt(v: Any) -> str:
    """Format a param value for URL encoding (booleans as lowercase)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _parse_quote(data: dict[str, Any]) -> Quote:
    """Parse a quote JSON payload into a Quote dataclass."""
    if not data or not data.get("symbol"):
        raise FinanceError("Quote response missing 'symbol' — unknown ticker?")
    history = None
    raw_history = data.get("history")
    if raw_history:
        history = [HistoryPoint(date=p["date"], close=float(p["close"])) for p in raw_history]
    return Quote(
        symbol=data["symbol"],
        name=data.get("name", ""),
        price=float(data.get("price", 0.0)),
        change=float(data.get("change", 0.0)),
        change_percent=float(data.get("changesPercentage", 0.0)),
        currency=data.get("currency", "USD"),
        exchange=data.get("exchange", ""),
        is_crypto=bool(data.get("isCrypto", False)),
        is_market_open=bool(data.get("isMarketOpen", False)),
        market_cap=_opt_float(data.get("marketCap")),
        volume=_opt_float(data.get("volume")),
        avg_volume=_opt_float(data.get("avgVolume")),
        day_low=_opt_float(data.get("dayLow")),
        day_high=_opt_float(data.get("dayHigh")),
        year_low=_opt_float(data.get("yearLow")),
        year_high=_opt_float(data.get("yearHigh")),
        pe=_opt_float(data.get("pe")),
        eps=_opt_float(data.get("eps")),
        open_price=_opt_float(data.get("open")),
        previous_close=_opt_float(data.get("previousClose")),
        after_hours_price=_opt_float(data.get("afterHoursPrice")),
        after_hours_change=_opt_float(data.get("afterHoursChange")),
        after_hours_percent_change=_opt_float(data.get("afterHoursPercentChange")),
        history=history,
    )


def _opt_float(v: Any) -> float | None:
    """Coerce to float if not None/empty."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class FinanceAPI:
    """Async client for Perplexity Finance REST endpoints.

    Attributes:
        _core: Underlying ClientCore with authenticated httpx session.
    """

    def __init__(self, core: ClientCore):
        """Initialize the Finance API.

        Args:
            core: ClientCore instance with authenticated cookies.
        """
        self._core = core

    async def quote(
        self,
        ticker: str,
        *,
        with_history: bool = False,
        period: str = "1d",
    ) -> Quote:
        """Fetch the current quote for a ticker (stock, crypto, index, ETF).

        Args:
            ticker: Ticker symbol (e.g. "NVDA", "AAPL", "BTCUSD"). Case-insensitive.
            with_history: If True, include intraday `history[]` points.
            period: Time window for history (e.g. "1d", "5d"). Default "1d".

        Returns:
            Quote dataclass.

        Raises:
            FinanceError: If the response is empty or lacks a symbol.
        """
        url = _build_url(
            f"/quote/{ticker.upper()}",
            {
                "with_history": with_history,
                "history_period": period,
                "history_offset": 0,
                "history_after_hours": True,
                "with_ui_hints": True,
                "history_redirect": False,
            },
        )
        data = await self._core.get_json(url)
        return _parse_quote(data)

    async def profile(self, ticker: str) -> CompanyProfile:
        """Fetch the company profile for a ticker.

        Args:
            ticker: Ticker symbol. Case-insensitive.

        Returns:
            CompanyProfile dataclass.
        """
        url = _build_url(f"/profile/{ticker.upper()}")
        data = await self._core.get_json(url)
        return CompanyProfile(
            symbol=data.get("symbol", ticker.upper()),
            company_name=data.get("companyName", ""),
            description=data.get("description", ""),
            industry=data.get("industry", ""),
            exchange=data.get("exchange", ""),
            website=data.get("website"),
            cik=data.get("cik"),
            isin=data.get("isin"),
        )

    async def why_moving(self, ticker: str) -> MovementSummary:
        """Fetch the AI-generated explanation of a ticker's recent movement.

        Args:
            ticker: Ticker symbol. Case-insensitive.

        Returns:
            MovementSummary with `explanation` and source citations.
        """
        url = _build_url(f"/significant-movement-summary/{ticker.upper()}")
        data = await self._core.get_json(url)
        sources = [
            Source(name=s.get("title", ""), url=s.get("url", ""), snippet=s.get("snippet", ""))
            for s in data.get("sources", [])
        ]
        return MovementSummary(explanation=data.get("explanation", ""), sources=sources)

    async def timeline(self, ticker: str, *, limit: int = 20) -> list[TimelineEntry]:
        """Fetch the narrative news timeline for a ticker.

        Args:
            ticker: Ticker symbol. Case-insensitive.
            limit: Max entries to return.

        Returns:
            List of TimelineEntry, newest first.
        """
        url = _build_url(f"/timeline/{ticker.upper()}/entries", {"limit": limit})
        data = await self._core.get_json(url)
        return [
            TimelineEntry(
                ticker=e.get("ticker", ticker.upper()),
                description=e.get("description", ""),
                last_modified=e.get("last_modified", ""),
                source_urls=list(e.get("source_urls", [])),
            )
            for e in data
        ]

    async def ticker_news(self, ticker: str, *, limit: int = 10) -> list[NewsEntry]:
        """Fetch publisher news for a ticker.

        Args:
            ticker: Ticker symbol. Case-insensitive.
            limit: Max articles to return.

        Returns:
            List of NewsEntry (may be empty).
        """
        url = _build_url(f"/publisher-news/{ticker.upper()}", {"limit": limit})
        data = await self._core.get_json(url)
        return [_parse_news_entry(n) for n in data]


def _parse_news_entry(data: dict[str, Any]) -> NewsEntry:
    """Parse a news-entry dict into a NewsEntry dataclass."""
    return NewsEntry(
        title=data.get("title", ""),
        url=data.get("url", ""),
        published_at=data.get("published_at") or data.get("publishedAt"),
        publisher=data.get("publisher") or data.get("source"),
    )
```

- [ ] **Step 4: Wire `FinanceAPI` into `PerplexityClient`**

Modify `src/perplexity/client.py`:

Replace the import block (top of file) with:

```python
from __future__ import annotations

from pathlib import Path

from perplexity._chat import ChatAPI
from perplexity._core import ClientCore
from perplexity._finance import FinanceAPI
from perplexity._models import ModelsAPI
from perplexity._threads import ThreadsAPI
from perplexity.auth import AuthTokens
```

Replace the `__init__` body with:

```python
    def __init__(self, auth: AuthTokens):
        """Initialize the client with authentication tokens.

        Args:
            auth: Authentication tokens from browser login.
        """
        self._core = ClientCore(auth)
        self.chat = ChatAPI(self._core)
        self.models = ModelsAPI(self._core)
        self.threads = ThreadsAPI(self._core)
        self.finance = FinanceAPI(self._core)
```

Update the class docstring's `Attributes:` block to add:

```
        finance: Finance API for quotes, market data, and predictions.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_finance_api.py -v`
Expected: PASS (all 8 tests in this task).

- [ ] **Step 6: Commit**

```bash
git add src/perplexity/_finance.py src/perplexity/client.py tests/test_finance_api.py
git commit -m "feat(finance): add FinanceAPI with quote/profile/why/timeline/news"
```

---

## Task 5: Market overview methods

**Files:**
- Modify: `src/perplexity/_finance.py`
- Modify: `tests/test_finance_api.py`

Implements: `market_summary`, `indices`, `movers`, `top_z_scores`, `sectors`, `fixed_income`, `market_news`, `market_sentiment`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_finance_api.py`:

```python
from perplexity.types import Index, Mover, Sector, SummaryItem


@pytest.mark.asyncio
async def test_market_summary(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/market_summary.json")
    api = FinanceAPI(mock_core)
    items = await api.market_summary()
    assert len(items) == 2
    assert isinstance(items[0], SummaryItem)
    assert items[0].header.startswith("Crude Oil")
    called_url = mock_core.get_json.call_args.args[0]
    assert "country=US" in called_url


@pytest.mark.asyncio
async def test_market_summary_country_override(mock_core) -> None:
    mock_core.get_json.return_value = {"data": {"summary": []}}
    api = FinanceAPI(mock_core)
    await api.market_summary(country="UK")
    called_url = mock_core.get_json.call_args.args[0]
    assert "country=UK" in called_url


@pytest.mark.asyncio
async def test_indices_stocks(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/top_indices_market.json")
    api = FinanceAPI(mock_core)
    idx = await api.indices()
    assert len(idx) == 2
    assert isinstance(idx[0], Index)
    assert idx[0].symbol == "ESUSD"
    assert idx[0].history is not None
    called_url = mock_core.get_json.call_args.args[0]
    assert "/top-indices/market" in called_url


@pytest.mark.asyncio
async def test_indices_crypto(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    await api.indices(market="crypto")
    called_url = mock_core.get_json.call_args.args[0]
    assert "/top-indices/crypto" in called_url


@pytest.mark.asyncio
async def test_movers(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/market_movers.json")
    api = FinanceAPI(mock_core)
    mvs = await api.movers()
    assert len(mvs) == 2
    assert isinstance(mvs[0], Mover)
    assert mvs[0].sector == "Technology"


@pytest.mark.asyncio
async def test_sectors(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/equity_sectors.json")
    api = FinanceAPI(mock_core)
    s = await api.sectors()
    assert len(s) == 2
    assert isinstance(s[0], Sector)
    assert s[0].symbol == "XLK"
    # equity-sectors has no country param
    called_url = mock_core.get_json.call_args.args[0]
    assert "/equity-sectors" in called_url


@pytest.mark.asyncio
async def test_top_z_scores_crypto(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    await api.top_z_scores(market="crypto")
    called_url = mock_core.get_json.call_args.args[0]
    assert "/top-z-scores/crypto" in called_url


@pytest.mark.asyncio
async def test_fixed_income_empty(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    items = await api.fixed_income()
    assert items == []


@pytest.mark.asyncio
async def test_market_news_empty(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    news = await api.market_news()
    assert news == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_finance_api.py -v -k "market or indices or movers or sectors or z_scores or fixed_income"`
Expected: FAIL (methods not defined yet).

- [ ] **Step 3: Add methods to `FinanceAPI`**

Append inside `class FinanceAPI` in `src/perplexity/_finance.py`:

```python
    # -------- Market overview --------

    async def market_summary(self, country: str = "US") -> list[SummaryItem]:
        """Fetch headline bullets for the market.

        Args:
            country: ISO country code (e.g. "US").

        Returns:
            List of SummaryItem (header + detail).
        """
        url = _build_url("/market-summary/market", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("data", {}).get("summary", []) if isinstance(data, dict) else []
        return [SummaryItem(header=s.get("header", ""), detail=s.get("detail", "")) for s in raw]

    async def indices(
        self,
        *,
        market: str = "stocks",
        country: str = "US",
        with_history: bool = False,
        period: str = "1d",
    ) -> list[Index]:
        """Fetch top indices for a market.

        Args:
            market: "stocks" → `/top-indices/market`, "crypto" → `/top-indices/crypto`.
            country: ISO country code.
            with_history: Include intraday history points.
            period: History window (e.g. "1d").

        Returns:
            List of Index dataclasses.
        """
        segment = "market" if market == "stocks" else market
        url = _build_url(
            f"/top-indices/{segment}",
            {
                "with_history": with_history,
                "history_period": period,
                "country": country,
            },
        )
        data = await self._core.get_json(url)
        return [_parse_index(i) for i in data]

    async def movers(self, country: str = "US") -> list[Mover]:
        """Fetch today's top market movers (by price change).

        Args:
            country: ISO country code.

        Returns:
            List of Mover.
        """
        url = _build_url("/market-movers", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("movers", []) if isinstance(data, dict) else data
        return [_parse_mover(m) for m in raw]

    async def top_z_scores(self, *, market: str = "stocks", country: str = "US") -> list[Mover]:
        """Fetch statistical outliers (high-z-score movers).

        Args:
            market: "stocks" or "crypto".
            country: ISO country code.

        Returns:
            List of Mover.
        """
        segment = "market" if market == "stocks" else market
        url = _build_url(f"/top-z-scores/{segment}", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("movers", []) if isinstance(data, dict) else data
        return [_parse_mover(m) for m in raw]

    async def sectors(self) -> list[Sector]:
        """Fetch sector ETFs (XLK, XLE, XLY, ...).

        Returns:
            List of Sector.
        """
        url = _build_url("/equity-sectors")
        data = await self._core.get_json(url)
        return [
            Sector(
                symbol=s.get("symbol", ""),
                name=s.get("name", ""),
                price=float(s.get("price", 0.0)),
                change=float(s.get("change", 0.0)),
                change_percent=float(s.get("changesPercentage", 0.0)),
                currency=s.get("currency", "USD"),
                market_cap=_opt_float(s.get("marketCap")),
            )
            for s in data
        ]

    async def fixed_income(self) -> list[FixedIncomeItem]:
        """Fetch fixed-income summary (bonds, yield curve).

        Returns:
            List of FixedIncomeItem.
        """
        url = _build_url("/fixed-income")
        data = await self._core.get_json(url)
        return [
            FixedIncomeItem(
                symbol=i.get("symbol", ""),
                name=i.get("name", ""),
                price=float(i.get("price", 0.0)),
                change=float(i.get("change", 0.0)),
                change_percent=float(i.get("changesPercentage", 0.0)),
            )
            for i in data
        ]

    async def market_news(self, country: str = "US") -> list[NewsEntry]:
        """Fetch general market news.

        Args:
            country: ISO country code.

        Returns:
            List of NewsEntry.
        """
        url = _build_url("/general-news/market", {"country": country})
        data = await self._core.get_json(url)
        items = data if isinstance(data, list) else data.get("news", [])
        return [_parse_news_entry(n) for n in items]

    async def market_sentiment(self, country: str = "US") -> Sentiment:
        """Fetch market sentiment score.

        Args:
            country: ISO country code.

        Returns:
            Sentiment dataclass.
        """
        url = _build_url("/market-sentiment/market", {"country": country})
        data = await self._core.get_json(url)
        return Sentiment(
            score=float(data.get("score", 0.0)),
            label=data.get("label", ""),
        )
```

Also add these module-level helpers near `_parse_quote`:

```python
def _parse_mover(data: dict[str, Any]) -> Mover:
    """Parse a mover JSON entry into a Mover dataclass."""
    return Mover(
        symbol=data.get("symbol", ""),
        name=data.get("name", ""),
        price=float(data.get("price", 0.0)),
        change=float(data.get("change", 0.0)),
        change_percent=float(data.get("changesPercentage", 0.0)),
        currency=data.get("currency", "USD"),
        sector=data.get("sector"),
        industry=data.get("industry"),
        market_cap=_opt_float(data.get("marketCap")),
    )


def _parse_index(data: dict[str, Any]) -> Index:
    """Parse an index JSON entry into an Index dataclass."""
    history = None
    raw_history = data.get("history")
    if raw_history:
        history = [HistoryPoint(date=p["date"], close=float(p["close"])) for p in raw_history]
    return Index(
        symbol=data.get("symbol", ""),
        name=data.get("name", ""),
        price=float(data.get("price", 0.0)),
        change=float(data.get("change", 0.0)),
        change_percent=float(data.get("changesPercentage", 0.0)),
        currency=data.get("currency", "USD"),
        exchange=data.get("exchange", ""),
        history=history,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_finance_api.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/_finance.py tests/test_finance_api.py
git commit -m "feat(finance): add market overview methods (summary, indices, movers, sectors)"
```

---

## Task 6: Prediction markets

**Files:**
- Modify: `src/perplexity/_finance.py`
- Modify: `tests/test_finance_api.py`

Implements: `predictions`, `ticker_predictions`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_finance_api.py`:

```python
from perplexity.types import PredictionMarket


@pytest.mark.asyncio
async def test_predictions_finance_tag(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/predictions_finance.json")
    api = FinanceAPI(mock_core)
    preds = await api.predictions()
    assert len(preds) == 1
    assert isinstance(preds[0], PredictionMarket)
    assert preds[0].provider == "polymarket"
    assert preds[0].title.startswith("What will WTI")
    assert len(preds[0].markets) == 1
    assert preds[0].markets[0].question == "↑ $110"
    called_url = mock_core.get_json.call_args.args[0]
    assert "/prediction-markets/tag/finance" in called_url
    assert "limit=10" in called_url


@pytest.mark.asyncio
async def test_predictions_custom_tag(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    await api.predictions(tag="politics", limit=5, commentary=True)
    called_url = mock_core.get_json.call_args.args[0]
    assert "/prediction-markets/tag/politics" in called_url
    assert "limit=5" in called_url
    assert "with_commentary=true" in called_url


@pytest.mark.asyncio
async def test_ticker_predictions(mock_core) -> None:
    mock_core.get_json.return_value = []
    api = FinanceAPI(mock_core)
    await api.ticker_predictions("AAPL")
    called_url = mock_core.get_json.call_args.args[0]
    assert "/prediction-markets/AAPL/trending-ticker" in called_url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_finance_api.py -v -k "predictions"`
Expected: FAIL.

- [ ] **Step 3: Add methods to `FinanceAPI`**

Append inside `class FinanceAPI`:

```python
    # -------- Prediction markets --------

    async def predictions(
        self,
        *,
        tag: str = "finance",
        limit: int = 10,
        page: int = 0,
        commentary: bool = False,
    ) -> list[PredictionMarket]:
        """Fetch prediction markets grouped by tag (Polymarket-backed).

        Args:
            tag: One of "finance", "crypto", "politics", "earnings".
            limit: Max markets to return.
            page: Pagination offset.
            commentary: Include AI-generated commentary on each market.

        Returns:
            List of PredictionMarket.
        """
        url = _build_url(
            f"/prediction-markets/tag/{tag}",
            {"with_commentary": commentary, "page": page, "limit": limit},
        )
        data = await self._core.get_json(url)
        return [_parse_prediction_market(p) for p in data]

    async def ticker_predictions(
        self,
        ticker: str,
        *,
        commentary: bool = False,
    ) -> list[PredictionMarket]:
        """Fetch prediction markets related to a specific ticker.

        Args:
            ticker: Ticker symbol. Case-insensitive.
            commentary: Include AI-generated commentary.

        Returns:
            List of PredictionMarket (may be empty).
        """
        url = _build_url(
            f"/prediction-markets/{ticker.upper()}/trending-ticker",
            {"with_commentary": commentary},
        )
        data = await self._core.get_json(url)
        # Response can be a list or a dict with a markets array — defensive parse.
        items = data if isinstance(data, list) else data.get("markets", [])
        return [_parse_prediction_market(p) for p in items]
```

Add module-level helper:

```python
def _parse_prediction_market(data: dict[str, Any]) -> PredictionMarket:
    """Parse a prediction market JSON payload."""
    options = [
        PredictionOption(
            id=str(m.get("id", "")),
            question=m.get("question", ""),
            probability=float(m.get("probability", 0.0)),
            outcomes=list(m.get("outcomes", [])),
            outcome_prices=[float(p) for p in m.get("outcomePrices", [])],
            volume=float(m.get("volume", 0.0)),
        )
        for m in data.get("markets", [])
    ]
    return PredictionMarket(
        id=str(data.get("id", "")),
        title=data.get("title", ""),
        provider=data.get("provider", "polymarket"),
        slug=data.get("slug", ""),
        volume=float(data.get("volume", 0.0)),
        currency=data.get("currency", "USD"),
        start_date=data.get("startDate", ""),
        end_date=data.get("endDate", ""),
        markets=options,
        icon=data.get("icon"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_finance_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/_finance.py tests/test_finance_api.py
git commit -m "feat(finance): add prediction markets endpoints"
```

---

## Task 7: Personal endpoints + autosuggest

**Files:**
- Modify: `src/perplexity/_finance.py`
- Modify: `tests/test_finance_api.py`

Implements: `watchlist`, `watchlist_quotes`, `watchlist_summary`, `portfolio_overview`, `autosuggest`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_finance_api.py`:

```python
import httpx

from perplexity.exceptions import AuthenticationError
from perplexity.types import AutosuggestHit, PortfolioOverview, Watchlist


@pytest.mark.asyncio
async def test_watchlist(mock_core) -> None:
    mock_core.get_json.return_value = load_fixture("finance/watchlist.json")
    api = FinanceAPI(mock_core)
    wl = await api.watchlist()
    assert isinstance(wl, Watchlist)
    assert wl.symbols == ["AMZN", "NVDA"]


@pytest.mark.asyncio
async def test_watchlist_quotes_uses_quotes_endpoint(mock_core) -> None:
    mock_core.get_json.return_value = [load_fixture("finance/quote_nvda.json")]
    api = FinanceAPI(mock_core)
    quotes = await api.watchlist_quotes()
    assert len(quotes) == 1
    assert quotes[0].symbol == "NVDA"
    called_url = mock_core.get_json.call_args.args[0]
    assert "/watchlist/quotes" in called_url


@pytest.mark.asyncio
async def test_portfolio_overview_returns_none_on_404(mock_core) -> None:
    """Users without Plaid linked get a 404 — return None, not raise."""
    request = httpx.Request("GET", "https://example/portfolio")
    response = httpx.Response(404, request=request)
    mock_core.get_json.side_effect = httpx.HTTPStatusError(
        "Not found", request=request, response=response
    )
    api = FinanceAPI(mock_core)
    result = await api.portfolio_overview()
    assert result is None


@pytest.mark.asyncio
async def test_portfolio_overview_reraises_auth(mock_core) -> None:
    """Auth errors must propagate, not be swallowed."""
    mock_core.get_json.side_effect = AuthenticationError("expired")
    api = FinanceAPI(mock_core)
    with pytest.raises(AuthenticationError):
        await api.portfolio_overview()


@pytest.mark.asyncio
async def test_autosuggest(mock_core) -> None:
    mock_core.get_json.return_value = [
        {"symbol": "AAPL", "name": "Apple Inc.", "kind": "stock"},
        {"symbol": "AAPLW", "name": "Apple Warrants", "kind": "stock"},
    ]
    api = FinanceAPI(mock_core)
    hits = await api.autosuggest("appl")
    assert len(hits) == 2
    assert isinstance(hits[0], AutosuggestHit)
    assert hits[0].symbol == "AAPL"
    called_url = mock_core.get_json.call_args.args[0]
    # Note: autosuggest lives under /rest/autosuggest/finance/... not /rest/finance/autosuggest/...
    assert "/rest/autosuggest/finance/list-autosuggest" in called_url
    assert "query=appl" in called_url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_finance_api.py -v -k "watchlist or portfolio or autosuggest"`
Expected: FAIL.

- [ ] **Step 3: Add methods**

Append inside `class FinanceAPI`:

```python
    # -------- Personal --------

    async def watchlist(self, country: str = "US") -> Watchlist:
        """Fetch the user's saved watchlist (symbols only).

        Args:
            country: ISO country code.

        Returns:
            Watchlist with list of symbols.
        """
        url = _build_url("/watchlist", {"country": country})
        data = await self._core.get_json(url)
        symbols = [item.get("symbol", "") for item in data if item.get("symbol")]
        return Watchlist(symbols=symbols)

    async def watchlist_quotes(self, country: str = "US") -> list[Quote]:
        """Fetch live quotes for every symbol in the watchlist.

        Args:
            country: ISO country code.

        Returns:
            List of Quote, one per watchlist symbol.
        """
        url = _build_url("/watchlist/quotes", {"country": country})
        data = await self._core.get_json(url)
        return [_parse_quote(q) for q in data if q.get("symbol")]

    async def watchlist_summary(self, country: str = "US") -> WatchlistSummary:
        """Fetch an aggregate summary of the watchlist.

        Args:
            country: ISO country code.

        Returns:
            WatchlistSummary with headline bullets.
        """
        url = _build_url("/watchlist/summary", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("summary", []) if isinstance(data, dict) else []
        items = [SummaryItem(header=s.get("header", ""), detail=s.get("detail", "")) for s in raw]
        return WatchlistSummary(items=items)

    async def portfolio_overview(self) -> PortfolioOverview | None:
        """Fetch Plaid-linked portfolio overview.

        Returns None if the user has no Plaid connection (404). Other errors
        (401/403/5xx) propagate.

        Returns:
            PortfolioOverview or None.
        """
        url = _build_url("/personal/portfolio/overview")
        try:
            data = await self._core.get_json(url)
        except Exception as e:  # narrow below
            # Treat 404 as "no portfolio linked"; propagate everything else.
            import httpx

            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                return None
            raise
        return PortfolioOverview(
            total_value=float(data.get("totalValue", 0.0)),
            day_change=float(data.get("dayChange", 0.0)),
            day_change_percent=float(data.get("dayChangePercent", 0.0)),
            accounts=list(data.get("accounts", [])),
        )

    # -------- Helpers --------

    async def autosuggest(self, query: str, *, country: str = "US") -> list[AutosuggestHit]:
        """Search tickers by free-text query.

        NOTE: This endpoint is mounted at `/rest/autosuggest/finance/...`, NOT
        under `/rest/finance/autosuggest/...`. Constructs an absolute URL directly.

        Args:
            query: Free-text search ("apple", "nvda", "btc").
            country: ISO country code.

        Returns:
            List of AutosuggestHit.
        """
        url = (
            f"{PERPLEXITY_BASE_URL}/rest/autosuggest/finance/list-autosuggest"
            f"?{urlencode({'query': query, 'country': country})}"
        )
        data = await self._core.get_json(url)
        return [
            AutosuggestHit(
                symbol=h.get("symbol", ""),
                name=h.get("name", ""),
                kind=h.get("kind", ""),
            )
            for h in data
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_finance_api.py -v`
Expected: PASS (all tests, including everything from earlier tasks).

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/_finance.py tests/test_finance_api.py
git commit -m "feat(finance): add watchlist, portfolio, and autosuggest endpoints"
```

---

## Task 8: CLI skeleton + ticker commands

**Files:**
- Create: `src/perplexity/cli/finance.py`
- Modify: `src/perplexity/cli/__init__.py`
- Create: `tests/test_cli_finance.py`

Implements: `perplexity finance quote/profile/why/news/timeline`.

- [ ] **Step 1: Write failing CLI test**

Create `tests/test_cli_finance.py`:

```python
"""CLI tests for the `perplexity finance` sub-group — uses a mocked client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from perplexity.cli import cli
from perplexity.types import CompanyProfile, Quote


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_client():
    """A MagicMock client with async `finance` methods."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.finance = MagicMock()
    client.finance.quote = AsyncMock()
    client.finance.profile = AsyncMock()
    client.finance.why_moving = AsyncMock()
    client.finance.timeline = AsyncMock()
    client.finance.ticker_news = AsyncMock()
    return client


def _nvda_quote() -> Quote:
    return Quote(
        symbol="NVDA",
        name="NVIDIA Corporation",
        price=201.68,
        change=3.33,
        change_percent=1.6789,
        currency="USD",
        exchange="NASDAQ",
        is_crypto=False,
        is_market_open=False,
    )


def test_finance_quote_human(runner, fake_client) -> None:
    fake_client.finance.quote.return_value = _nvda_quote()
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "quote", "NVDA"])
    assert result.exit_code == 0, result.output
    assert "NVDA" in result.output
    assert "201.68" in result.output
    assert "1.68" in result.output or "1.6789" in result.output


def test_finance_quote_json(runner, fake_client) -> None:
    fake_client.finance.quote.return_value = _nvda_quote()
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "quote", "NVDA", "--json"])
    assert result.exit_code == 0
    assert '"symbol": "NVDA"' in result.output
    assert '"price": 201.68' in result.output


def test_finance_profile(runner, fake_client) -> None:
    fake_client.finance.profile.return_value = CompanyProfile(
        symbol="AAPL",
        company_name="Apple Inc.",
        description="Apple designs phones.",
        industry="Consumer Electronics",
        exchange="NASDAQ",
        website="https://www.apple.com",
    )
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "profile", "AAPL"])
    assert result.exit_code == 0
    assert "Apple Inc." in result.output
    assert "Consumer Electronics" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_finance.py -v`
Expected: FAIL — `cli` has no `finance` group.

- [ ] **Step 3: Create `cli/finance.py` with ticker commands**

Create `src/perplexity/cli/finance.py`:

```python
"""CLI commands for Perplexity Finance."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import click
from rich.table import Table

from perplexity.cli.helpers import authenticated_client, console, get_storage_from_ctx, run_async


def _color_pct(pct: float) -> str:
    """Format a percent with green/red color tag based on sign."""
    sign = "+" if pct >= 0 else ""
    color = "green" if pct >= 0 else "red"
    return f"[{color}]{sign}{pct:.2f}%[/{color}]"


def _color_change(change: float, currency: str = "USD") -> str:
    """Format an absolute change with green/red color tag."""
    sign = "+" if change >= 0 else ""
    color = "green" if change >= 0 else "red"
    return f"[{color}]{sign}{change:.2f} {currency}[/{color}]"


def _dump_json(obj: Any) -> None:
    """Print any dataclass (or list of dataclasses) as indented JSON."""
    if isinstance(obj, list):
        data = [asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in obj]
    elif hasattr(obj, "__dataclass_fields__"):
        data = asdict(obj)
    else:
        data = obj
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


@click.group()
def finance() -> None:
    """Perplexity Finance — quotes, market data, news, predictions."""


@finance.command()
@click.argument("ticker")
@click.option("--history", is_flag=True, help="Include intraday price history.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def quote(ctx: click.Context, ticker: str, history: bool, as_json: bool) -> None:
    """Get the current price quote for a ticker (stock, crypto, index, ETF)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        q = await client.finance.quote(ticker, with_history=history)

    if as_json:
        _dump_json(q)
        return

    console.print(f"[bold cyan]{q.symbol}[/bold cyan] — {q.name}  [dim]({q.exchange})[/dim]")
    console.print(
        f"  Price: [bold]{q.price:.2f} {q.currency}[/bold]   "
        f"Change: {_color_change(q.change, q.currency)}   "
        f"Pct: {_color_pct(q.change_percent)}"
    )
    if q.market_cap:
        console.print(f"  Market cap: {q.market_cap:,.0f} {q.currency}")
    if q.day_low and q.day_high:
        console.print(f"  Day range: {q.day_low:.2f}–{q.day_high:.2f}")
    if q.year_low and q.year_high:
        console.print(f"  52-week range: {q.year_low:.2f}–{q.year_high:.2f}")
    if q.pe is not None:
        console.print(f"  PE: {q.pe:.2f}   EPS: {q.eps or 0:.2f}")
    if q.after_hours_price is not None:
        console.print(
            f"  After-hours: {q.after_hours_price:.2f} "
            f"({_color_pct(q.after_hours_percent_change or 0)})"
        )
    if history and q.history:
        console.print(f"  History points: {len(q.history)}")


@finance.command()
@click.argument("ticker")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def profile(ctx: click.Context, ticker: str, as_json: bool) -> None:
    """Show the company profile for a ticker."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        p = await client.finance.profile(ticker)

    if as_json:
        _dump_json(p)
        return

    console.print(f"[bold cyan]{p.symbol}[/bold cyan] — {p.company_name}")
    console.print(f"  Exchange: {p.exchange}   Industry: {p.industry}")
    if p.website:
        console.print(f"  Website: {p.website}")
    console.print()
    console.print(p.description)


@finance.command()
@click.argument("ticker")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def why(ctx: click.Context, ticker: str, as_json: bool) -> None:
    """Explain why a ticker moved today (AI-generated with sources)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        m = await client.finance.why_moving(ticker)

    if as_json:
        _dump_json(m)
        return

    console.print(f"[bold cyan]{ticker.upper()}[/bold cyan]: {m.explanation}")
    if m.sources:
        console.print("\n[bold]Sources:[/bold]")
        for i, s in enumerate(m.sources, 1):
            console.print(f"  [{i}] {s.name} — {s.url}")


@finance.command()
@click.argument("ticker")
@click.option("--limit", default=10, show_default=True, help="Max articles to return.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def news(ctx: click.Context, ticker: str, limit: int, as_json: bool) -> None:
    """Show publisher news for a ticker."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.ticker_news(ticker, limit=limit)

    if as_json:
        _dump_json(items)
        return

    if not items:
        console.print(f"[yellow]No news for {ticker.upper()}.[/yellow]")
        return
    for n in items:
        console.print(f"[bold]{n.title}[/bold]")
        if n.publisher:
            console.print(f"  [dim]{n.publisher}[/dim]")
        console.print(f"  {n.url}\n")


@finance.command()
@click.argument("ticker")
@click.option("--limit", default=20, show_default=True, help="Max timeline entries.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def timeline(ctx: click.Context, ticker: str, limit: int, as_json: bool) -> None:
    """Show the narrative news timeline for a ticker."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        entries = await client.finance.timeline(ticker, limit=limit)

    if as_json:
        _dump_json(entries)
        return

    if not entries:
        console.print(f"[yellow]No timeline entries for {ticker.upper()}.[/yellow]")
        return
    for e in entries:
        console.print(f"[bold]{e.last_modified}[/bold] — {e.ticker}")
        console.print(f"  {e.description}")
        if e.source_urls:
            console.print(f"  [dim]Sources: {len(e.source_urls)}[/dim]")
        console.print()
```

- [ ] **Step 4: Register the `finance` group in `cli/__init__.py`**

Modify `src/perplexity/cli/__init__.py` — add import and registration:

Add to imports:

```python
from perplexity.cli.finance import finance
```

Add after the other `cli.add_command(...)` lines:

```python
cli.add_command(finance)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli_finance.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/perplexity/cli/finance.py src/perplexity/cli/__init__.py tests/test_cli_finance.py
git commit -m "feat(cli): add finance sub-group with quote/profile/why/news/timeline"
```

---

## Task 9: CLI market overview commands

**Files:**
- Modify: `src/perplexity/cli/finance.py`
- Modify: `tests/test_cli_finance.py`

Implements: `perplexity finance market/movers/indices/sectors/fixed-income`.

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli_finance.py`:

```python
from perplexity.types import Index, Mover, Sector, SummaryItem


def test_finance_movers_human(runner, fake_client) -> None:
    fake_client.finance.movers = AsyncMock(
        return_value=[
            Mover(
                symbol="NVDA",
                name="NVIDIA",
                price=201.68,
                change=3.33,
                change_percent=1.67,
                currency="USD",
                sector="Technology",
            )
        ]
    )
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "movers"])
    assert result.exit_code == 0
    assert "NVDA" in result.output


def test_finance_indices_crypto(runner, fake_client) -> None:
    fake_client.finance.indices = AsyncMock(
        return_value=[
            Index(
                symbol="BTCUSD",
                name="Bitcoin",
                price=75000.0,
                change=500.0,
                change_percent=0.67,
                currency="USD",
                exchange="CRYPTO",
            )
        ]
    )
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "indices", "--market", "crypto"])
    assert result.exit_code == 0
    assert "BTCUSD" in result.output


def test_finance_sectors(runner, fake_client) -> None:
    fake_client.finance.sectors = AsyncMock(
        return_value=[
            Sector(
                symbol="XLK",
                name="Technology",
                price=154.35,
                change=2.33,
                change_percent=1.53,
                currency="USD",
            )
        ]
    )
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "sectors"])
    assert result.exit_code == 0
    assert "XLK" in result.output
    assert "Technology" in result.output


def test_finance_market_aggregates(runner, fake_client) -> None:
    """`finance market` calls summary + indices + movers in one go."""
    fake_client.finance.market_summary = AsyncMock(
        return_value=[SummaryItem(header="Market up", detail="Strong day.")]
    )
    fake_client.finance.indices = AsyncMock(return_value=[])
    fake_client.finance.movers = AsyncMock(return_value=[])
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "market"])
    assert result.exit_code == 0
    assert "Market up" in result.output
    fake_client.finance.market_summary.assert_awaited_once()
    fake_client.finance.indices.assert_awaited_once()
    fake_client.finance.movers.assert_awaited_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_finance.py -v -k "movers or indices or sectors or market_agg"`
Expected: FAIL.

- [ ] **Step 3: Add commands to `cli/finance.py`**

Append to `src/perplexity/cli/finance.py`:

```python
def _render_movers_table(title: str, items: list) -> Table:
    """Build a Rich Table for a list of Mover/Index/Sector dataclasses."""
    table = Table(title=title, show_header=True)
    table.add_column("Symbol", style="bold cyan")
    table.add_column("Name")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("%", justify="right")
    for m in items:
        pct_str = _color_pct(m.change_percent)
        ch_str = _color_change(m.change, m.currency)
        table.add_row(m.symbol, m.name, f"{m.price:.2f}", ch_str, pct_str)
    return table


@finance.command()
@click.option("--country", default="US", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def market(ctx: click.Context, country: str, as_json: bool) -> None:
    """Show a combined market overview (summary + indices + movers)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        summary_items = await client.finance.market_summary(country=country)
        idx = await client.finance.indices(country=country)
        mvs = await client.finance.movers(country=country)

    if as_json:
        _dump_json(
            {
                "summary": [asdict(s) for s in summary_items],
                "indices": [asdict(i) for i in idx],
                "movers": [asdict(m) for m in mvs],
            }
        )
        return

    if summary_items:
        console.print("[bold underline]Market headlines[/bold underline]")
        for s in summary_items:
            console.print(f"• [bold]{s.header}[/bold]")
            console.print(f"  {s.detail}")
        console.print()
    if idx:
        console.print(_render_movers_table("Indices", idx))
    if mvs:
        console.print(_render_movers_table("Top movers", mvs))


@finance.command()
@click.option("--country", default="US", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def movers(ctx: click.Context, country: str, as_json: bool) -> None:
    """Show today's top market movers."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.movers(country=country)

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print("[yellow]No movers found.[/yellow]")
        return
    console.print(_render_movers_table("Top movers", items))


@finance.command()
@click.option(
    "--market",
    "market_kind",
    type=click.Choice(["stocks", "crypto"]),
    default="stocks",
    show_default=True,
)
@click.option("--country", default="US", show_default=True)
@click.option("--history", is_flag=True, help="Include intraday history.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def indices(
    ctx: click.Context,
    market_kind: str,
    country: str,
    history: bool,
    as_json: bool,
) -> None:
    """Show major indices (stocks or crypto)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.indices(
            market=market_kind, country=country, with_history=history
        )

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print("[yellow]No indices returned.[/yellow]")
        return
    console.print(_render_movers_table(f"Indices ({market_kind})", items))


@finance.command()
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def sectors(ctx: click.Context, as_json: bool) -> None:
    """Show sector ETFs."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.sectors()

    if as_json:
        _dump_json(items)
        return
    console.print(_render_movers_table("Sectors", items))


@finance.command(name="fixed-income")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def fixed_income(ctx: click.Context, as_json: bool) -> None:
    """Show fixed-income instruments (bonds, yields)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.fixed_income()

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print("[yellow]No fixed income data.[/yellow]")
        return
    for fi in items:
        console.print(
            f"[bold cyan]{fi.symbol}[/bold cyan] {fi.name}  "
            f"{fi.price:.2f}  {_color_pct(fi.change_percent)}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_finance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/cli/finance.py tests/test_cli_finance.py
git commit -m "feat(cli): add finance market/movers/indices/sectors/fixed-income commands"
```

---

## Task 10: CLI predictions, watchlist, portfolio, search commands

**Files:**
- Modify: `src/perplexity/cli/finance.py`
- Modify: `tests/test_cli_finance.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli_finance.py`:

```python
from perplexity.types import (
    AutosuggestHit,
    PredictionMarket,
    PredictionOption,
    Watchlist,
)


def test_finance_predictions(runner, fake_client) -> None:
    fake_client.finance.predictions = AsyncMock(
        return_value=[
            PredictionMarket(
                id="1",
                title="Will BTC hit $100k in 2026?",
                provider="polymarket",
                slug="btc-100k",
                volume=1000000.0,
                currency="USD",
                start_date="2026-01-01",
                end_date="2026-12-31",
                markets=[
                    PredictionOption(
                        id="1a",
                        question="Yes",
                        probability=0.42,
                        outcomes=["Yes", "No"],
                        outcome_prices=[0.42, 0.58],
                        volume=500000.0,
                    )
                ],
            )
        ]
    )
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "predictions"])
    assert result.exit_code == 0
    assert "BTC hit" in result.output
    assert "42" in result.output  # 42% probability


def test_finance_watchlist(runner, fake_client) -> None:
    fake_client.finance.watchlist = AsyncMock(return_value=Watchlist(symbols=["NVDA", "AAPL"]))
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "watchlist"])
    assert result.exit_code == 0
    assert "NVDA" in result.output
    assert "AAPL" in result.output


def test_finance_portfolio_empty(runner, fake_client) -> None:
    fake_client.finance.portfolio_overview = AsyncMock(return_value=None)
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "portfolio"])
    assert result.exit_code == 0
    assert "no portfolio" in result.output.lower() or "not connected" in result.output.lower()


def test_finance_search(runner, fake_client) -> None:
    fake_client.finance.autosuggest = AsyncMock(
        return_value=[
            AutosuggestHit(symbol="AAPL", name="Apple Inc.", kind="stock"),
        ]
    )
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["finance", "search", "apple"])
    assert result.exit_code == 0
    assert "AAPL" in result.output
    assert "Apple Inc." in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_finance.py -v -k "predictions or watchlist or portfolio or search"`
Expected: FAIL.

- [ ] **Step 3: Add commands to `cli/finance.py`**

Append to `src/perplexity/cli/finance.py`:

```python
@finance.command()
@click.option(
    "--tag",
    type=click.Choice(["finance", "crypto", "politics", "earnings"]),
    default="finance",
    show_default=True,
)
@click.option("--limit", default=10, show_default=True)
@click.option("--commentary", is_flag=True, help="Include AI commentary.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def predictions(
    ctx: click.Context, tag: str, limit: int, commentary: bool, as_json: bool
) -> None:
    """Show prediction markets (Polymarket-backed) by tag."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.predictions(tag=tag, limit=limit, commentary=commentary)

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print(f"[yellow]No prediction markets for tag '{tag}'.[/yellow]")
        return
    for pm in items:
        console.print(f"[bold]{pm.title}[/bold]  [dim]({pm.provider}, vol={pm.volume:,.0f})[/dim]")
        for opt in pm.markets[:5]:  # cap nested output
            pct = opt.probability * 100
            console.print(f"  • {opt.question}: [bold]{pct:.1f}%[/bold]")
        console.print()


@finance.command()
@click.option("--country", default="US", show_default=True)
@click.option("--with-quotes", is_flag=True, help="Also fetch live quotes.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def watchlist(
    ctx: click.Context, country: str, with_quotes: bool, as_json: bool
) -> None:
    """Show the user's saved watchlist."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        wl = await client.finance.watchlist(country=country)
        quotes = None
        if with_quotes:
            quotes = await client.finance.watchlist_quotes(country=country)

    if as_json:
        payload: Any = {"symbols": wl.symbols}
        if quotes:
            payload["quotes"] = [asdict(q) for q in quotes]
        _dump_json(payload)
        return

    if not wl.symbols:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return
    if quotes:
        console.print(_render_movers_table("Watchlist", quotes))
    else:
        console.print("[bold]Watchlist:[/bold] " + ", ".join(wl.symbols))


@finance.command()
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def portfolio(ctx: click.Context, as_json: bool) -> None:
    """Show the Plaid-linked portfolio overview."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        overview = await client.finance.portfolio_overview()

    if as_json:
        _dump_json(overview if overview else {})
        return

    if overview is None:
        console.print("[yellow]No portfolio linked. Connect via the Perplexity web UI.[/yellow]")
        return
    console.print(f"[bold]Total value:[/bold] {overview.total_value:,.2f}")
    console.print(
        f"[bold]Day change:[/bold] "
        f"{_color_change(overview.day_change)} "
        f"({_color_pct(overview.day_change_percent)})"
    )
    console.print(f"[bold]Accounts:[/bold] {len(overview.accounts)}")


@finance.command()
@click.argument("query")
@click.option("--country", default="US", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def search(ctx: click.Context, query: str, country: str, as_json: bool) -> None:
    """Search for tickers by name (autosuggest)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        hits = await client.finance.autosuggest(query, country=country)

    if as_json:
        _dump_json(hits)
        return
    if not hits:
        console.print(f"[yellow]No matches for '{query}'.[/yellow]")
        return
    for h in hits:
        console.print(f"[bold cyan]{h.symbol}[/bold cyan]  {h.name}  [dim]({h.kind})[/dim]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_finance.py -v`
Expected: PASS (all CLI tests).

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/cli/finance.py tests/test_cli_finance.py
git commit -m "feat(cli): add finance predictions/watchlist/portfolio/search commands"
```

---

## Task 11: `ask --finance` flag

**Files:**
- Modify: `src/perplexity/_chat.py`
- Modify: `src/perplexity/cli/chat.py`
- Create: `tests/test_chat_finance_flag.py`

Biases the chat search toward finance sources by setting `search_focus="finance"` in the ask payload.

- [ ] **Step 1: Write failing test for the API layer**

Create `tests/test_chat_finance_flag.py`:

```python
"""Tests for the --finance search_focus override on ask."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from perplexity._chat import _build_ask_payload
from perplexity.cli import cli
from perplexity.types import AskResult


def test_build_payload_default_search_focus() -> None:
    payload = _build_ask_payload("hi", "pplx_pro", "copilot", "internet", "en-US")
    assert payload["params"]["search_focus"] == "internet"


def test_build_payload_finance_focus_passthrough() -> None:
    """Caller can pass search_focus='finance' and the payload reflects it."""
    payload = _build_ask_payload("oil today", "pplx_pro", "copilot", "finance", "en-US")
    assert payload["params"]["search_focus"] == "finance"


def test_ask_cli_finance_flag_routes_to_chat_with_finance_focus() -> None:
    """`perplexity ask --finance "q"` must call ChatAPI.ask with search_focus="finance"."""
    runner = CliRunner()
    fake_client = MagicMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    fake_client.chat = MagicMock()
    fake_client.chat.ask = AsyncMock(return_value=AskResult(answer="ok", sources=[]))
    with patch("perplexity.cli.helpers.authenticated_client", return_value=fake_client):
        result = runner.invoke(cli, ["ask", "--finance", "--raw", "oil?"])
    assert result.exit_code == 0, result.output
    call = fake_client.chat.ask.await_args
    assert call.kwargs.get("search_focus") == "finance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_finance_flag.py -v`
Expected: FAIL on the CLI test (no `--finance` flag yet). The payload tests should already pass because `_build_ask_payload` takes `search_focus` as a parameter today.

- [ ] **Step 3: Add `--finance` flag to the `ask` command**

In `src/perplexity/cli/chat.py`, locate the `ask` command decorator block and its function signature. Add a new click option:

```python
@click.option(
    "--finance",
    is_flag=True,
    help="Bias the search toward finance sources (sets search_focus=finance).",
)
```

Add `finance: bool` to the function parameters (keep it alongside other flags).

Inside the command body, when calling `client.chat.ask(...)`, pass `search_focus="finance"` when the flag is set. Concretely, before the `client.chat.ask(...)` call, derive:

```python
search_focus = "finance" if finance else "internet"
```

And pass `search_focus=search_focus` to `client.chat.ask(...)`. If the current implementation does not pass `search_focus` explicitly, add that keyword argument.

- [ ] **Step 4: Run all tests**

Run: `pytest -v`
Expected: PASS (all existing + new).

- [ ] **Step 5: Commit**

```bash
git add src/perplexity/cli/chat.py tests/test_chat_finance_flag.py
git commit -m "feat(cli): add --finance flag to ask to bias search toward finance"
```

---

## Task 12: README + final verification

**Files:**
- Modify: `README.md` (if present)

- [ ] **Step 1: Check for README**

Run: `ls /Users/edusu/projects/perplexity-cli/README.md` — if present, proceed; otherwise skip to Step 3.

- [ ] **Step 2: Update README with finance usage**

Append a new `## Perplexity Finance` section to `README.md` (below the main Usage section). Content:

````markdown
## Perplexity Finance

The CLI exposes the `/finance` surface through a `perplexity finance` sub-group. All commands default to `country=US` and accept `--country XX`. Every command accepts `--json` for pipeable output.

### Quotes, profile, news

```bash
perplexity finance quote NVDA              # price, change, volume, PE, 52w range
perplexity finance quote BTCUSD            # crypto works (USD-suffixed)
perplexity finance quote NVDA --history    # include intraday history
perplexity finance profile AAPL
perplexity finance why NVDA                # AI-generated move explanation
perplexity finance news NVDA --limit 10
perplexity finance timeline NVDA
```

### Market overview

```bash
perplexity finance market                  # summary + indices + movers combined
perplexity finance movers
perplexity finance indices                 # stocks by default
perplexity finance indices --market crypto
perplexity finance sectors
perplexity finance fixed-income
```

### Prediction markets (Polymarket-backed)

```bash
perplexity finance predictions                 # tag=finance
perplexity finance predictions --tag politics
perplexity finance predictions --tag crypto --limit 20
```

### Personal

```bash
perplexity finance watchlist
perplexity finance watchlist --with-quotes
perplexity finance portfolio                   # Plaid-linked only
perplexity finance search apple                # autosuggest tickers
```

### Finance-focused chat

```bash
perplexity ask --finance "What's moving tech stocks today?"
```

Use `--json` with any finance command and pipe into `jq`:

```bash
perplexity finance quote NVDA --json | jq '.price'
perplexity finance movers --json | jq '.[:3] | .[] | {symbol, change_percent}'
```
````

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 4: Run ruff + mypy**

Run:
```bash
ruff format src/ tests/
ruff check src/ tests/
mypy src/perplexity --ignore-missing-imports
```

Expected: no formatting diffs remaining, `ruff check` PASS, mypy PASS (or only pre-existing warnings).

- [ ] **Step 5: Smoke-test the CLI end-to-end (manual)**

Run (requires valid `perplexity login`):
```bash
perplexity finance quote NVDA
perplexity finance market
perplexity finance predictions --tag finance
perplexity ask --finance "How is Nvidia doing today?" --raw
```

Expected: human-friendly output with colored changes; no tracebacks.

- [ ] **Step 6: Commit docs**

```bash
git add README.md
git commit -m "docs: document perplexity finance commands in README"
```

---

## Spec Coverage Check

| Spec requirement | Task(s) |
|---|---|
| `FinanceAPI` class + `client.finance` | Task 4 |
| `quote`, `profile`, `why_moving`, `timeline`, `ticker_news` | Task 4 |
| `market_summary`, `indices`, `movers`, `top_z_scores`, `sectors`, `fixed_income`, `market_news`, `market_sentiment` | Task 5 |
| `predictions`, `ticker_predictions` | Task 6 |
| `watchlist`, `watchlist_quotes`, `watchlist_summary`, `portfolio_overview`, `autosuggest` | Task 7 |
| All finance dataclasses | Task 2 |
| `FinanceError` exception | Task 1 |
| CLI sub-group + ticker commands | Task 8 |
| CLI market commands | Task 9 |
| CLI predictions/watchlist/portfolio/search | Task 10 |
| `ask --finance` flag | Task 11 |
| 404 on portfolio → None | Task 7 |
| `country` override everywhere | Tasks 5, 8, 9, 10 |
| README docs | Task 12 |
| Unit tests with fixtures | Tasks 1–10 |
| Full verification (ruff + mypy + pytest) | Task 12 |

Deferred per spec (out of scope — NOT planned here): watchlist writes, Plaid management, `--watch` refresh loops, ASCII charts, non-US country verification.
