"""Tests that finance dataclasses accept their declared fields."""

from __future__ import annotations

from perplexity.types import (
    AutosuggestHit,
    CompanyProfile,
    HistoryPoint,
    Index,
    MovementSummary,
    Mover,
    PredictionMarket,
    PredictionOption,
    Quote,
    Source,
    SummaryItem,
    Watchlist,
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
    assert q.history is not None
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
        question="Up",
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
    assert pm.markets[0].question == "Up"


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
        description="Apple designs...",
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
