"""Data types for Perplexity API responses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Source:
    """A web source cited in a Perplexity answer.

    Attributes:
        name: Title of the source page.
        url: URL of the source.
        snippet: Brief excerpt from the source content.
    """

    name: str
    url: str
    snippet: str


@dataclass
class AskResult:
    """Result from a Perplexity chat query.

    Attributes:
        answer: Full markdown-formatted answer text.
        sources: Web sources cited in the answer.
        backend_uuid: Server-assigned ID for this answer entry.
        context_uuid: Thread/conversation context ID for follow-ups.
        thread_url_slug: URL slug for viewing this thread on perplexity.ai.
        model: Model used for the response (e.g. "pplx_pro").
        read_write_token: Token required for sending follow-up messages in the same thread.
    """

    answer: str
    sources: list[Source] = field(default_factory=list)
    backend_uuid: str | None = None
    context_uuid: str | None = None
    thread_url_slug: str | None = None
    model: str | None = None
    read_write_token: str | None = None


@dataclass
class Model:
    """A model available in Perplexity.

    Attributes:
        name: Internal model identifier (e.g. "pplx_pro", "claude2").
        label: User-facing display name (e.g. "Best", "Claude Sonnet 4.0").
        description: Short description of the model's capabilities.
        mode: Execution mode (e.g. "search", "research", "agentic_research").
        provider: Provider name (e.g. "OPENAI", "ANTHROPIC", "GOOGLE") or None for Perplexity models.
    """

    name: str
    label: str
    description: str
    mode: str
    provider: str | None = None


@dataclass
class Thread:
    """A conversation thread from Perplexity's server history.

    Attributes:
        uuid: Server-assigned thread ID.
        title: Auto-generated thread title from the first question.
        link: Relative URL path to view the thread on perplexity.ai.
        status: Thread status (e.g. "completed").
        context_uuid: Context ID for the thread.
        variant: Thread type (e.g. "thread").
    """

    uuid: str
    title: str
    link: str
    status: str
    context_uuid: str | None = None
    variant: str | None = None


# ---------- Finance ----------


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
    sources: list[Source] = field(default_factory=list)


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

    symbols: list[str] = field(default_factory=list)


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
