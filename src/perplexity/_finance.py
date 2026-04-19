"""Finance API for Perplexity.

Wraps the REST JSON endpoints under `/rest/finance/` exposed by the
Perplexity `/finance` web UI. All endpoints are plain JSON GETs with
cookie auth — no SSE.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

import httpx

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


def _fmt(v: Any) -> str:
    """Format a param value for URL encoding (booleans as lowercase)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _build_url(path: str, params: dict[str, Any] | None = None) -> str:
    """Join the finance base with a path and URL-encoded params.

    Args:
        path: Path relative to /rest/finance (must start with "/").
        params: Optional query parameters (None values are dropped).

    Returns:
        Fully-qualified URL with encoded query string.
    """
    url = f"{FINANCE_BASE}{path}"
    if params:
        encoded = urlencode({k: _fmt(v) for k, v in params.items() if v is not None})
        if encoded:
            url = f"{url}?{encoded}"
    return url


def _opt_float(v: Any) -> float | None:
    """Coerce a value to float if not None/empty, else None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_quote(data: dict[str, Any]) -> Quote:
    """Parse a quote JSON payload into a Quote dataclass.

    Raises:
        FinanceError: If the payload is empty or lacks a 'symbol' field
            (indicates an unknown ticker returned a stub response).
    """
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


def _parse_mover(data: dict[str, Any]) -> Mover:
    """Parse a mover/index-like JSON entry into a Mover dataclass."""
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


def _parse_news_entry(data: dict[str, Any]) -> NewsEntry:
    """Parse a news-entry dict into a NewsEntry dataclass."""
    return NewsEntry(
        title=data.get("title", ""),
        url=data.get("url", ""),
        published_at=data.get("published_at") or data.get("publishedAt"),
        publisher=data.get("publisher") or data.get("source"),
    )


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


class FinanceAPI:
    """Async client for Perplexity Finance REST endpoints.

    All methods accept a `country` argument (default "US") where applicable;
    endpoints with no country parameter (e.g. equity-sectors) ignore it.

    Attributes:
        _core: Underlying ClientCore with authenticated httpx session.
    """

    def __init__(self, core: ClientCore):
        """Initialize the Finance API.

        Args:
            core: ClientCore instance with authenticated cookies.
        """
        self._core = core

    # -------- Ticker-scoped --------

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
            Source(
                name=s.get("title", ""),
                url=s.get("url", ""),
                snippet=s.get("snippet", ""),
            )
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

    # -------- Market overview --------

    async def market_summary(self, country: str = "US") -> list[SummaryItem]:
        """Fetch headline bullets for the market."""
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
        """Fetch today's top market movers (by price change)."""
        url = _build_url("/market-movers", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("movers", []) if isinstance(data, dict) else data
        return [_parse_mover(m) for m in raw]

    async def top_z_scores(self, *, market: str = "stocks", country: str = "US") -> list[Mover]:
        """Fetch statistical outliers (high-z-score movers)."""
        segment = "market" if market == "stocks" else market
        url = _build_url(f"/top-z-scores/{segment}", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("movers", []) if isinstance(data, dict) else data
        return [_parse_mover(m) for m in raw]

    async def sectors(self) -> list[Sector]:
        """Fetch sector ETFs (XLK, XLE, XLY, ...)."""
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
        """Fetch fixed-income summary (bonds, yield curve)."""
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
        """Fetch general market news."""
        url = _build_url("/general-news/market", {"country": country})
        data = await self._core.get_json(url)
        items = data if isinstance(data, list) else data.get("news", [])
        return [_parse_news_entry(n) for n in items]

    async def market_sentiment(self, country: str = "US") -> Sentiment:
        """Fetch market sentiment score."""
        url = _build_url("/market-sentiment/market", {"country": country})
        data = await self._core.get_json(url)
        return Sentiment(
            score=float(data.get("score", 0.0)),
            label=data.get("label", ""),
        )

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
        """
        url = _build_url(
            f"/prediction-markets/tag/{tag}",
            {"with_commentary": commentary, "page": page, "limit": limit},
        )
        data = await self._core.get_json(url)
        return [_parse_prediction_market(p) for p in data]

    async def ticker_predictions(
        self, ticker: str, *, commentary: bool = False
    ) -> list[PredictionMarket]:
        """Fetch prediction markets related to a specific ticker."""
        url = _build_url(
            f"/prediction-markets/{ticker.upper()}/trending-ticker",
            {"with_commentary": commentary},
        )
        data = await self._core.get_json(url)
        # Response may be a list or an object with a "markets" field.
        items = data if isinstance(data, list) else data.get("markets", [])
        return [_parse_prediction_market(p) for p in items]

    # -------- Personal --------

    async def watchlist(self, country: str = "US") -> Watchlist:
        """Fetch the user's saved watchlist (symbols only)."""
        url = _build_url("/watchlist", {"country": country})
        data = await self._core.get_json(url)
        symbols = [item.get("symbol", "") for item in data if item.get("symbol")]
        return Watchlist(symbols=symbols)

    async def watchlist_quotes(self, country: str = "US") -> list[Quote]:
        """Fetch live quotes for every symbol in the watchlist."""
        url = _build_url("/watchlist/quotes", {"country": country})
        data = await self._core.get_json(url)
        return [_parse_quote(q) for q in data if q.get("symbol")]

    async def watchlist_summary(self, country: str = "US") -> WatchlistSummary:
        """Fetch an aggregate summary of the watchlist."""
        url = _build_url("/watchlist/summary", {"country": country})
        data = await self._core.get_json(url)
        raw = data.get("summary", []) if isinstance(data, dict) else []
        items = [SummaryItem(header=s.get("header", ""), detail=s.get("detail", "")) for s in raw]
        return WatchlistSummary(items=items)

    async def portfolio_overview(self) -> PortfolioOverview | None:
        """Fetch Plaid-linked portfolio overview.

        Returns None if the user has no Plaid connection (404). Other errors
        (401/403/5xx) propagate as raised by the underlying client.
        """
        url = _build_url("/personal/portfolio/overview")
        try:
            data = await self._core.get_json(url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
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
        under `/rest/finance/autosuggest/...`.

        Args:
            query: Free-text search ("apple", "nvda", "btc").
            country: ISO country code.
        """
        encoded = urlencode({"query": query, "country": country})
        url = f"{PERPLEXITY_BASE_URL}/rest/autosuggest/finance/list-autosuggest?{encoded}"
        data = await self._core.get_json(url)
        return [
            AutosuggestHit(
                symbol=h.get("symbol", ""),
                name=h.get("name", ""),
                kind=h.get("kind", ""),
            )
            for h in data
        ]
