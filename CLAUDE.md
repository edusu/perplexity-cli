# CLAUDE.md

## Project Overview

`perplexity-cli` is an unofficial CLI and Python client for Perplexity.ai that uses the reverse-engineered web API. It enables programmatic access to Perplexity chat using your existing subscription (no API keys needed).

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

# Pre-commit checks
ruff format src/ tests/
ruff check src/ tests/
mypy src/perplexity --ignore-missing-imports
pytest
```

## Architecture

```
CLI Layer (cli/)           Click commands
    ↓
Client Layer (client.py)   PerplexityClient async context manager
    ↓
API Layer (_chat.py)       ChatAPI with SSE parsing
    ↓
Core Layer (_core.py)      httpx client, SSE streaming, cookie auth
```

## Key Files

| File | Purpose |
|------|---------|
| `client.py` | Main `PerplexityClient` class |
| `_core.py` | HTTP client and SSE streaming |
| `_chat.py` | Chat API (ask endpoint) |
| `auth.py` | Cookie extraction from Playwright storage |
| `paths.py` | `~/.perplexity/` path resolution |
| `types.py` | `AskResult`, `Source` dataclasses |
| `cli/` | CLI command implementations |

## API Protocol

- **Endpoint**: `POST https://www.perplexity.ai/rest/sse/perplexity_ask`
- **Auth**: Cookie-based (NextAuth session + Cloudflare cf_clearance)
- **Request**: JSON with `query_str` + `params` object
- **Response**: SSE stream with `event: message\ndata: {JSON}` events
- **Answer text**: `markdown_block.answer` or `chunks[]` in `ask_text_0_markdown` blocks
- **Sources**: `web_result_block.web_results[]` with name, url, snippet
- **End signal**: `status: "COMPLETED"` + `final_sse_message: true`
