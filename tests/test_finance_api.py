"""Unit tests for FinanceAPI — uses mocked ClientCore, no network."""

from __future__ import annotations

import httpx
import pytest

from perplexity._finance import FinanceAPI
from perplexity.exceptions import AuthenticationError, FinanceError
from perplexity.types import (
    AutosuggestHit,
    CompanyProfile,
    Index,
    MovementSummary,
    Mover,
    PortfolioOverview,
    PredictionMarket,
    Quote,
    Sector,
    SummaryItem,
    TimelineEntry,
    Watchlist,
)
from tests.conftest import load_fixture


# ---------- Ticker-scoped ----------


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
async def test_quote_raises_finance_error_on_empty(mock_core) -> None:
    """Empty payload (unknown ticker stub) → FinanceError, not silent default."""
    mock_core.get_json.return_value = {}
    api = FinanceAPI(mock_core)
    with pytest.raises(FinanceError):
        await api.quote("BOGUS")


# ---------- Market overview ----------


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


# ---------- Prediction markets ----------


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


# ---------- Personal + autosuggest ----------


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
async def test_portfolio_overview_success(mock_core) -> None:
    mock_core.get_json.return_value = {
        "totalValue": 50000.0,
        "dayChange": 250.0,
        "dayChangePercent": 0.5,
        "accounts": [{"id": "acc1"}],
    }
    api = FinanceAPI(mock_core)
    po = await api.portfolio_overview()
    assert isinstance(po, PortfolioOverview)
    assert po.total_value == 50000.0
    assert len(po.accounts) == 1


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
    # Note: autosuggest lives under /rest/autosuggest/finance/, not /rest/finance/autosuggest/
    assert "/rest/autosuggest/finance/list-autosuggest" in called_url
    assert "query=appl" in called_url
