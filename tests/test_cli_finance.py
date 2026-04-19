"""CLI tests for the `perplexity finance` sub-group — uses a mocked client."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from perplexity.cli import cli
from perplexity.types import (
    AutosuggestHit,
    CompanyProfile,
    Index,
    Mover,
    PredictionMarket,
    PredictionOption,
    Quote,
    Sector,
    SummaryItem,
    Watchlist,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_client():
    """A MagicMock client with `finance` namespace; patched authenticated_client
    must return an async context manager yielding this."""
    client = MagicMock()
    client.finance = MagicMock()
    for method in [
        "quote",
        "profile",
        "why_moving",
        "timeline",
        "ticker_news",
        "market_summary",
        "indices",
        "movers",
        "sectors",
        "fixed_income",
        "predictions",
        "watchlist",
        "watchlist_quotes",
        "portfolio_overview",
        "autosuggest",
    ]:
        setattr(client.finance, method, AsyncMock())
    return client


@pytest.fixture
def patched_auth(fake_client):
    """Patch authenticated_client to yield fake_client as an async CM."""

    @asynccontextmanager
    async def _ctx(_storage):
        yield fake_client

    with patch("perplexity.cli.finance.authenticated_client", _ctx):
        yield fake_client


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


# ---------- Ticker commands ----------


def test_finance_quote_human(runner, patched_auth) -> None:
    patched_auth.finance.quote.return_value = _nvda_quote()
    result = runner.invoke(cli, ["finance", "quote", "NVDA"])
    assert result.exit_code == 0, result.output
    assert "NVDA" in result.output
    assert "201.68" in result.output


def test_finance_quote_json(runner, patched_auth) -> None:
    patched_auth.finance.quote.return_value = _nvda_quote()
    result = runner.invoke(cli, ["finance", "quote", "NVDA", "--json"])
    assert result.exit_code == 0
    assert '"symbol": "NVDA"' in result.output
    assert '"price": 201.68' in result.output


def test_finance_profile(runner, patched_auth) -> None:
    patched_auth.finance.profile.return_value = CompanyProfile(
        symbol="AAPL",
        company_name="Apple Inc.",
        description="Apple designs phones.",
        industry="Consumer Electronics",
        exchange="NASDAQ",
        website="https://www.apple.com",
    )
    result = runner.invoke(cli, ["finance", "profile", "AAPL"])
    assert result.exit_code == 0
    assert "Apple Inc." in result.output
    assert "Consumer Electronics" in result.output


# ---------- Market commands ----------


def test_finance_movers_human(runner, patched_auth) -> None:
    patched_auth.finance.movers.return_value = [
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
    result = runner.invoke(cli, ["finance", "movers"])
    assert result.exit_code == 0
    assert "NVDA" in result.output


def test_finance_indices_crypto(runner, patched_auth) -> None:
    patched_auth.finance.indices.return_value = [
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
    result = runner.invoke(cli, ["finance", "indices", "--market", "crypto"])
    assert result.exit_code == 0
    assert "BTCUSD" in result.output


def test_finance_sectors(runner, patched_auth) -> None:
    patched_auth.finance.sectors.return_value = [
        Sector(
            symbol="XLK",
            name="Technology",
            price=154.35,
            change=2.33,
            change_percent=1.53,
            currency="USD",
        )
    ]
    result = runner.invoke(cli, ["finance", "sectors"])
    assert result.exit_code == 0
    assert "XLK" in result.output
    assert "Technology" in result.output


def test_finance_market_aggregates(runner, patched_auth) -> None:
    """`finance market` calls summary + indices + movers in one go."""
    patched_auth.finance.market_summary.return_value = [
        SummaryItem(header="Market up", detail="Strong day.")
    ]
    patched_auth.finance.indices.return_value = []
    patched_auth.finance.movers.return_value = []
    result = runner.invoke(cli, ["finance", "market"])
    assert result.exit_code == 0
    assert "Market up" in result.output
    patched_auth.finance.market_summary.assert_awaited_once()
    patched_auth.finance.indices.assert_awaited_once()
    patched_auth.finance.movers.assert_awaited_once()


# ---------- Predictions / personal ----------


def test_finance_predictions(runner, patched_auth) -> None:
    patched_auth.finance.predictions.return_value = [
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
    result = runner.invoke(cli, ["finance", "predictions"])
    assert result.exit_code == 0
    assert "BTC hit" in result.output
    assert "42" in result.output


def test_finance_watchlist(runner, patched_auth) -> None:
    patched_auth.finance.watchlist.return_value = Watchlist(symbols=["NVDA", "AAPL"])
    result = runner.invoke(cli, ["finance", "watchlist"])
    assert result.exit_code == 0
    assert "NVDA" in result.output
    assert "AAPL" in result.output


def test_finance_portfolio_empty(runner, patched_auth) -> None:
    patched_auth.finance.portfolio_overview.return_value = None
    result = runner.invoke(cli, ["finance", "portfolio"])
    assert result.exit_code == 0
    assert "no portfolio" in result.output.lower() or "not connected" in result.output.lower()


def test_finance_search(runner, patched_auth) -> None:
    patched_auth.finance.autosuggest.return_value = [
        AutosuggestHit(symbol="AAPL", name="Apple Inc.", kind="stock"),
    ]
    result = runner.invoke(cli, ["finance", "search", "apple"])
    assert result.exit_code == 0
    assert "AAPL" in result.output
    assert "Apple Inc." in result.output
