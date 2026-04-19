# Perplexity Finance Integration — Design

**Date:** 2026-04-19
**Status:** Approved for implementation planning
**Scope:** Add Perplexity Finance (`/finance`) as a first-class API and CLI surface.

## Problem

Perplexity's web UI exposes a dedicated `/finance` section with market data, stock quotes, crypto, news, prediction markets (Polymarket), watchlists and an AI-powered movement explainer. None of this is available through `perplexity-cli`, which today only wraps the generic chat endpoint.

## Reconnaissance summary

Recon via Playwright CDP (logged in with the user's existing `storage_state.json`) revealed that `/finance` is backed by **30+ dedicated REST JSON endpoints** under `/rest/finance/`, all GET, cookie-authenticated with the same credentials as chat. None of them use SSE — responses are flat JSON.

Q&A submitted from `/finance` goes to the **same** `POST /rest/sse/perplexity_ask` endpoint as regular chat; the URL after submission is `/search/<slug>`, identical to any other chat thread. The finance frontend likely passes a `search_focus` or `source` hint in the payload, but no new endpoint is involved.

### Confirmed endpoints (with sample payload shapes)

**Market data (public)**
- `GET /rest/finance/quote/{TICKER}?with_history&history_period&history_offset&history_after_hours&with_ui_hints&history_redirect` — price, change, %, marketCap, volume, 52w high/low, PE/EPS, after-hours, optional intraday `history[]` of `{date, close}`.
- `GET /rest/finance/significant-movement-summary/{TICKER}` — narrative `explanation` + `sources[]`.
- `GET /rest/finance/profile/{TICKER}` — company profile (CIK, ISIN, industry, website, description).
- `GET /rest/finance/profile/{TICKER}/description` — long description only.
- `GET /rest/finance/timeline/{TICKER}/entries?limit=N` — news timeline with `description` + `source_urls[]`.
- `GET /rest/finance/publisher-news/{TICKER}?limit=N` — publisher-sourced news list.

**Market overview (parametrized by `country`)**
- `GET /rest/finance/market-summary/market?country=US` — headline bullets (`header`, `detail`).
- `GET /rest/finance/top-indices/market?with_history&history_period&country=US` — S&P, Dow, Nasdaq, etc.
- `GET /rest/finance/top-indices/crypto?country=US` (+ `crypto_sidebar` variant) — major crypto indices.
- `GET /rest/finance/market-movers?country=US` — movers with sector + industry tags.
- `GET /rest/finance/top-movers/market?country=US`
- `GET /rest/finance/top-z-scores/market?country=US` (+ `/crypto`) — statistical outliers.
- `GET /rest/finance/equity-sectors` — sector ETFs (XLK, XLE, XLY, XLP, ...).
- `GET /rest/finance/fixed-income` — fixed-income summary.
- `GET /rest/finance/general-news/market?country=US`
- `GET /rest/finance/market-sentiment/market?country=US`

**Prediction markets (Polymarket-backed)**
- `GET /rest/finance/prediction-markets/tag/{finance|crypto|politics|earnings}?with_commentary&page&limit`
- `GET /rest/finance/prediction-markets/{TICKER}/trending-ticker?with_commentary`

**Personal (user-scoped)**
- `GET /rest/finance/watchlist?country=US` — symbols with logo images.
- `GET /rest/finance/watchlist/quotes?country=US` — quotes for watchlist members.
- `GET /rest/finance/watchlist/summary?country=US`
- `GET /rest/finance/watchlist/news`
- `GET /rest/finance/personal/portfolio/overview`
- `GET /rest/finance/personal/plaid/connections` (optional, skip unless user has Plaid linked)

**Autosuggest / settings (helpers)**
- `GET /rest/autosuggest/finance/list-autosuggest?query=<q>&country=US`
- `GET /rest/finance/settings?market_type=market|crypto&country=US`

## Goals

1. Expose the full finance REST surface through a new `FinanceAPI` Python namespace on `PerplexityClient`.
2. Ship a `perplexity finance` CLI subgroup with one command per major vertical.
3. Add an `--finance` flag to `perplexity ask` that biases the chat endpoint toward finance sources (best-effort — the exact param is inferred but not fully captured in recon; `search_focus="finance"` is the hypothesis, fallback is adding `"sources": ["web", "finance"]` or similar).
4. Default `country=US` everywhere; allow override via `--country`.
5. Preserve existing architecture: CLI → Client → APIs → Core. No breaking changes.

## Non-goals

- Realtime streaming / websockets (endpoints are polling-friendly; a `--watch` refresh loop is a phase-2 add-on, not MVP).
- Writing to watchlist / portfolio (all endpoints observed are GET; POST/PATCH behavior is unknown and out of scope).
- Plaid connection management.

## Architecture

```
CLI Layer                 cli/finance.py  (new, Click sub-group)
    ↓
Client Layer              client.py       (adds client.finance)
    ↓
API Layer                 _finance.py     (new, FinanceAPI class)
    ↓
Core Layer                _core.py        (adds get_json helper)
```

### Core change — `ClientCore.get_json`

Today `ClientCore` only exposes `sse_request`. Finance needs a plain JSON GET. Add:

```python
async def get_json(
    self,
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """GET {BASE_URL}{path} and return parsed JSON. Raises on non-2xx."""
```

This is ~10 lines: reuses `self._http` (already configured with cookies and user-agent), adds headers if needed, parses `.json()`. No SSE, no streaming. This same helper becomes available to any future flat-JSON endpoint.

### New module — `_finance.py` (`FinanceAPI`)

One class with async methods, each returning typed dataclasses. Rough signature:

```python
class FinanceAPI:
    def __init__(self, core: ClientCore): ...

    # Individual ticker data
    async def quote(self, ticker: str, *, with_history: bool = False, period: str = "1d") -> Quote
    async def profile(self, ticker: str) -> CompanyProfile
    async def why_moving(self, ticker: str) -> MovementSummary
    async def timeline(self, ticker: str, *, limit: int = 20) -> list[TimelineEntry]
    async def ticker_news(self, ticker: str, *, limit: int = 10) -> list[NewsEntry]

    # Market overview (country-scoped)
    async def market_summary(self, country: str = "US") -> list[SummaryItem]
    async def indices(self, market: str = "stocks", country: str = "US", *, with_history: bool = False) -> list[Index]
    async def movers(self, country: str = "US") -> list[Mover]
    async def top_z_scores(self, market: str = "stocks", country: str = "US") -> list[Mover]
    async def sectors(self) -> list[Sector]
    async def fixed_income(self) -> list[FixedIncomeItem]
    async def market_news(self, country: str = "US") -> list[NewsEntry]
    async def market_sentiment(self, country: str = "US") -> Sentiment

    # Prediction markets
    async def predictions(self, tag: str = "finance", *, limit: int = 10, commentary: bool = False) -> list[PredictionMarket]
    async def ticker_predictions(self, ticker: str, *, commentary: bool = False) -> list[PredictionMarket]

    # Personal
    async def watchlist(self, country: str = "US") -> Watchlist
    async def watchlist_quotes(self, country: str = "US") -> list[Quote]
    async def watchlist_summary(self, country: str = "US") -> WatchlistSummary
    async def portfolio_overview(self) -> PortfolioOverview | None  # None if no Plaid

    # Search / helpers
    async def autosuggest(self, query: str, country: str = "US") -> list[AutosuggestHit]
```

`market` parameter accepts `"stocks"` (maps to `market` in the URL) or `"crypto"` — keeps user-facing vocabulary simple while the URL uses internal names.

### New types — add to `types.py` (or `types/finance.py` if it grows)

```python
@dataclass
class Quote:
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    currency: str
    exchange: str
    market_cap: float | None
    volume: float | None
    day_low: float | None
    day_high: float | None
    year_low: float | None
    year_high: float | None
    pe: float | None
    eps: float | None
    after_hours_price: float | None
    after_hours_change: float | None
    is_crypto: bool
    is_market_open: bool
    history: list[HistoryPoint] | None
    # ... (full field list in implementation plan)

@dataclass
class HistoryPoint:
    date: str  # ISO timestamp
    close: float

@dataclass
class Mover:
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    sector: str | None
    industry: str | None

@dataclass
class Index:
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    history: list[HistoryPoint] | None

@dataclass
class SummaryItem:
    header: str
    detail: str

@dataclass
class CompanyProfile:
    symbol: str
    company_name: str
    description: str
    industry: str
    exchange: str
    website: str | None
    cik: str | None
    isin: str | None

@dataclass
class TimelineEntry:
    ticker: str
    description: str
    last_modified: str
    source_urls: list[str]

@dataclass
class NewsEntry:
    title: str
    url: str
    published_at: str | None
    publisher: str | None

@dataclass
class MovementSummary:
    explanation: str
    sources: list[Source]  # reuse existing Source

@dataclass
class Sector:
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    market_cap: float | None

@dataclass
class PredictionMarket:
    id: str
    title: str
    provider: str  # "polymarket" | others
    slug: str
    volume: float
    currency: str
    start_date: str
    end_date: str
    icon: str | None
    markets: list[PredictionOption]

@dataclass
class PredictionOption:
    id: str
    question: str
    probability: float
    outcomes: list[str]
    outcome_prices: list[float]
    volume: float

@dataclass
class Watchlist:
    symbols: list[str]

@dataclass
class AutosuggestHit:
    symbol: str
    name: str
    kind: str  # "stock" | "crypto" | "index" | ...
```

### Client wiring — `client.py`

```python
from perplexity._finance import FinanceAPI

class PerplexityClient:
    def __init__(self, auth: AuthTokens):
        self._core = ClientCore(auth)
        self.chat = ChatAPI(self._core)
        self.models = ModelsAPI(self._core)
        self.threads = ThreadsAPI(self._core)
        self.finance = FinanceAPI(self._core)  # NEW
```

### CLI — `cli/finance.py`

```
perplexity finance quote TICKER      [--history] [--json]
perplexity finance profile TICKER    [--json]
perplexity finance why TICKER        [--json]
perplexity finance news TICKER       [--limit N] [--json]
perplexity finance timeline TICKER   [--limit N] [--json]

perplexity finance market            [--country US] [--json]   # aggregate: summary + indices + movers
perplexity finance movers            [--country US] [--json]
perplexity finance indices           [--market stocks|crypto] [--country US] [--json]
perplexity finance sectors           [--json]
perplexity finance fixed-income      [--json]

perplexity finance watchlist         [--country US] [--json]
perplexity finance portfolio         [--json]

perplexity finance predictions       [--tag finance|crypto|politics|earnings] [--limit N] [--json]

perplexity finance search QUERY      [--country US]            # autosuggest
```

Human-friendly output: colored table (green/red by `change_percent`), compact layout using `rich`. With `--json`, dump dataclasses via `dataclasses.asdict()` for piping.

### `perplexity ask --finance`

Add a `--finance` flag to the existing `ask` command. Implementation: set `search_focus="finance"` in the ask payload (hypothesis based on the `/finance` UI source attribution; if the backend ignores it, we lose nothing). If later recon captures a different param, we adjust — this flag gives us the forward-compat hook.

## Error handling

- Cookie expiry / 401 → surface via existing `AuthError` (already defined in `exceptions.py`).
- 404 on `/rest/finance/quote/XYZ` → raise a new `FinanceError("Unknown ticker: XYZ")`.
- 404 on `personal/portfolio/overview` → return `None` (user has no Plaid linked); don't raise.
- 403/CF challenge → raise existing auth/network error with hint to re-login.
- Unexpected 5xx → propagate httpx `HTTPStatusError`, same as chat today.

## Testing

- Unit tests for `_finance.py`: mock `ClientCore.get_json` and verify each method builds correct URL + params and parses payloads into dataclasses. Use recorded fixture JSON from the recon session (trimmed to essentials).
- Integration tests guarded by `@pytest.mark.integration` (only run when `PERPLEXITY_INTEGRATION=1` is set and a valid `storage_state.json` exists) that hit real endpoints for `quote("NVDA")`, `market_summary()`, `movers()`.
- CLI smoke tests via `CliRunner` that mock the client.

## Risks & mitigations

- **Endpoint drift**: Perplexity can change the internal API without notice. Mitigation: version-lock via `API_VERSION` header already sent by `_core.py`; write tests against fixture JSON so drift shows up as parse failures, not silent wrong answers.
- **Country coverage unknown**: we only verified `country=US`. Mitigation: document US as the only tested value; accept arbitrary strings for forward-compat.
- **`ask --finance` is speculative**: we didn't confirm the exact param. Mitigation: ship it as best-effort, add a note in `--help`. If users find it's no different from plain ask, we remove it.
- **Rate limits shared with chat subscription**: finance endpoints likely share the same rate-limit bucket. Mitigation: document this in SKILL.md; don't add aggressive polling/refresh in MVP.

## Out of scope (deferred)

- Real-time refresh / `--watch` flag on `quote` and `movers`.
- Writing to watchlist.
- Plaid / portfolio management.
- Charts (rendering `history[]` as ASCII sparklines would be a nice add-on).
- Non-US markets beyond accepting the `--country` override.
```
