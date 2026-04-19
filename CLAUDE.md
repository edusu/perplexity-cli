# CLAUDE.md

## Project Overview

`perplexity-cli` is an unofficial CLI and Python client for Perplexity.ai that uses the reverse-engineered web API. It enables programmatic access to Perplexity chat **and** Perplexity Finance using your existing subscription (no API keys needed).

**Critical constraint**: This uses Perplexity's internal REST+SSE API which can change without notice.

## Development Commands

```bash
# Setup
uv venv .venv
uv pip install -e ".[all]"
playwright install chromium

# Run CLI
perplexity --help
perplexity login
perplexity ask "question"
perplexity finance quote NVDA

# Pre-commit checks
ruff format src/ tests/
ruff check src/ tests/
mypy src/perplexity --ignore-missing-imports
pytest
```

## Architecture

```
CLI Layer (cli/)           Click commands (chat, models, session, finance)
    ↓
Client Layer (client.py)   PerplexityClient async context manager
    ↓
API Layer                  ChatAPI (SSE), FinanceAPI (JSON), ModelsAPI, ThreadsAPI
    ↓
Core Layer (_core.py)      httpx client, SSE streaming, JSON GETs, cookie auth
```

## Key Files

| File | Purpose |
|------|---------|
| `client.py` | Main `PerplexityClient` class — exposes `.chat`, `.finance`, `.models`, `.threads` |
| `_core.py` | HTTP client, SSE streaming (`sse_request`), JSON GETs (`get_json`) |
| `_chat.py` | Chat API (ask / research / follow-up over SSE) |
| `_finance.py` | Finance API (quotes, market data, news, predictions, watchlist) |
| `_models.py` | Models listing |
| `_threads.py` | Thread history |
| `auth.py` | Cookie extraction from Playwright storage |
| `paths.py` | `~/.perplexity/` path resolution |
| `types.py` | `AskResult`, `Source`, `Quote`, `Mover`, `Index`, `CompanyProfile`, `TimelineEntry`, `NewsEntry`, `MovementSummary`, `PredictionMarket`, `Watchlist`, ... |
| `cli/` | CLI command implementations (chat, models, session, finance) |

## API Protocols

### Chat — SSE

- **Endpoint**: `POST https://www.perplexity.ai/rest/sse/perplexity_ask`
- **Auth**: Cookie-based (NextAuth session + Cloudflare `cf_clearance`)
- **Request**: JSON with `query_str` + `params` object
- **Response**: SSE stream with `event: message\ndata: {JSON}` events
- **Answer text**: `markdown_block.answer` or `chunks[]` in `ask_text_0_markdown` blocks
- **Sources**: `web_result_block.web_results[]` with name, url, snippet
- **End signal**: `status: "COMPLETED"` + `final_sse_message: true`
- **Finance bias**: `perplexity ask --finance` sets `search_focus="finance"` in the params

### Finance — REST JSON

All endpoints are `GET`, cookie-auth, no SSE — plain JSON responses. Defaults assume `country=US`.

**Ticker-scoped**
- `GET /rest/finance/quote/{TICKER}` — price, change, volume, marketCap, PE, 52w, after-hours, optional `history[]`
- `GET /rest/finance/profile/{TICKER}` — company profile (description, CIK, ISIN, industry, website)
- `GET /rest/finance/significant-movement-summary/{TICKER}` — narrative explanation + sources
- `GET /rest/finance/timeline/{TICKER}/entries?limit=N` — news timeline
- `GET /rest/finance/publisher-news/{TICKER}?limit=N` — publisher news

**Market overview**
- `GET /rest/finance/market-summary/market?country=US` — headline bullets
- `GET /rest/finance/top-indices/market?country=US` (+ `/crypto`) — major indices
- `GET /rest/finance/market-movers?country=US` — top movers
- `GET /rest/finance/top-z-scores/market?country=US` (+ `/crypto`) — statistical outliers
- `GET /rest/finance/equity-sectors` — sector ETFs
- `GET /rest/finance/fixed-income` — fixed income summary
- `GET /rest/finance/general-news/market?country=US`
- `GET /rest/finance/market-sentiment/market?country=US`

**Prediction markets (Polymarket-backed)**
- `GET /rest/finance/prediction-markets/tag/{finance|crypto|politics|earnings}?limit=N`
- `GET /rest/finance/prediction-markets/{TICKER}/trending-ticker`

**Personal**
- `GET /rest/finance/watchlist?country=US` (+ `/quotes`, `/summary`, `/news`)
- `GET /rest/finance/personal/portfolio/overview`

**Helpers**
- `GET /rest/autosuggest/finance/list-autosuggest?query=<q>&country=US`

The full design lives at `docs/superpowers/specs/2026-04-19-finance-integration-design.md`.
