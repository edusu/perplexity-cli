# perplexity-cli

Unofficial CLI and Python client for [Perplexity.ai](https://www.perplexity.ai). Use your existing Perplexity subscription directly from the terminal — no API keys needed.

## Why?

Perplexity has an official API (Sonar), but it requires separate API keys and payment. If you already have a Pro subscription, **perplexity-cli** lets you use it from the command line by authenticating through your browser session.

## Features

- **Interactive REPL** — `perplexity chat` for a conversational session with auto follow-ups
- **Chat** — Ask questions and get answers with source citations
- **Follow-ups** — Continue conversations with named threads
- **Deep Research** — Run multi-step research queries (1-3 min)
- **76+ Models** — Use any model available in Perplexity (GPT-5.4, Claude Opus 4.6, Gemini 3.1, etc.)
- **Pipe support** — Read questions from stdin for shell pipelines
- **History** — List recent threads from your account
- **Python API** — Use as a library in your own projects

## Installation

Requires Python 3.10+.

```bash
# Install with uv (recommended)
uv pip install -e ".[browser]"

# Or with pip
pip install -e ".[browser]"

# Install Chromium for the login command
playwright install chromium
```

The `[browser]` extra includes Playwright, needed only for the `login` command. If you manage cookies manually, the base install (`pip install -e .`) is sufficient.

## Authentication

perplexity-cli authenticates by capturing your browser session cookies. This is a one-time setup that typically lasts several weeks before needing to be refreshed.

```bash
perplexity login
```

This opens a Chromium browser window. You need to:

1. Solve the Cloudflare CAPTCHA (if it appears)
2. Log in to your Perplexity account
3. Wait for the homepage to load
4. Press **ENTER** in the terminal to save cookies

Cookies are stored in `~/.perplexity/storage_state.json` with restricted file permissions (600).

### Verify authentication

```bash
perplexity status
```

```
Logged in — 17 cookies loaded

  ✓ __Secure-next-auth.session-token
  ✓ cf_clearance
  ✓ pplx.session-id
```

### Alternative: environment variable

For CI/CD or headless environments, export cookies as inline JSON:

```bash
export PERPLEXITY_AUTH_JSON='{"cookies": [...]}'
```

### Custom config directory

```bash
export PERPLEXITY_HOME=/path/to/config   # default: ~/.perplexity
```

## Usage

### Ask a question

```bash
perplexity ask "What is Rust?"
```

Output includes a formatted answer with numbered source citations:

```
Rust is a modern systems programming language focused on safety, speed,
and concurrency without a garbage collector. [1][2]

Sources:
  [1] Rust (programming language) - Wikipedia
      https://en.wikipedia.org/wiki/Rust_(programming_language)
  [2] The Rust Programming Language
      https://doc.rust-lang.org/book/

Model: pplx_pro | perplexity.ai/search/what-is-rust-abc123
```

### Choose a model

```bash
# Use Claude Opus 4.6 instead of the default
perplexity ask "Explain monads" --model claude46opus

# Use GPT-5.4 with thinking
perplexity ask "Solve this math problem" --model gpt54_thinking
```

### Output formats

```bash
# Raw text (no Rich formatting, no sources, no metadata)
perplexity ask "What is 2+2?" --raw

# Hide sources but keep formatting
perplexity ask "Explain quantum computing" --no-sources
```

### Conversations with follow-ups

Start a conversation and continue it with follow-up questions. The server maintains full context.

```bash
# Start a named thread
perplexity ask "What is the tallest building in the world?" --thread buildings

# Follow up (knows you're talking about Burj Khalifa)
perplexity followup "How tall is it exactly?" --thread buildings

# Another follow-up
perplexity followup "When was it built?" --thread buildings
```

Without `--thread`, follow-ups continue the most recent conversation:

```bash
perplexity ask "Who wrote Don Quixote?"
perplexity followup "In what city was he born?"
perplexity followup "What other writers were born there?"
```

### Deep Research

Run thorough, multi-step research queries. Takes 1-3 minutes but produces detailed reports with extensive sources.

```bash
perplexity research "Compare the economic models of Nordic countries vs the USA"
perplexity research "How does Bluetooth work?" -t bluetooth
```

### Pipe support

Read questions from stdin for use in shell pipelines:

```bash
echo "What is Python?" | perplexity ask --raw
cat error.log | perplexity ask "Explain this error" --raw
git diff | perplexity ask "Review these changes" --raw
```

### Interactive chat (REPL)

Start a conversational session. Follow-ups are automatic — each question continues the same thread until you type `/new`.

```bash
perplexity chat
```

```
Perplexity Chat — interactive mode
Model: pplx_pro | Type /help for commands

pplx_pro> What is Rust?

Rust is a modern systems programming language focused on safety, speed,
and concurrency without a garbage collector. [1][2]

Sources:
  [1] Rust - Wikipedia
  [2] The Rust Programming Language

pplx_pro> Is it faster than C++?

In many benchmarks Rust performs comparably to C++...

pplx_pro> /new
New conversation started.

pplx_pro> What is Go?

Go is a statically typed, compiled language designed at Google...

pplx_pro> /model claude46opus
Model set to: claude46opus

claude46opus> Explain monads in simple terms

...

pplx_pro> /quit
Goodbye.
```

**REPL commands:**

| Command | Description |
|---------|-------------|
| `/new` | Start a new conversation |
| `/model NAME` | Switch model (e.g. `/model claude46opus`) |
| `/research` | Toggle deep research mode on/off |
| `/sources` | Toggle source display on/off |
| `/help` | Show available commands |
| `/quit` | Exit (also Ctrl+D or Ctrl+C) |

### List models

```bash
# All models
perplexity models

# Filter by mode
perplexity models --mode search       # Chat models (63+)
perplexity models --mode research     # Deep research models
```

### View history

```bash
# Recent threads from the server (includes web UI threads)
perplexity history

# Local named threads only
perplexity threads
```

### Finance

`perplexity finance` wraps the `/finance` surface: real-time quotes,
market data, prediction markets, watchlist, and autosuggest. All
commands default to `country=US` (override with `--country XX`) and
accept `--json` for pipeable output.

```bash
# Quotes, profile, news
perplexity finance quote NVDA              # price, change, volume, PE, 52w
perplexity finance quote BTCUSD            # crypto works (USD-suffixed)
perplexity finance quote NVDA --history    # include intraday history
perplexity finance profile AAPL
perplexity finance why NVDA                # AI-generated move explanation
perplexity finance news NVDA --limit 10
perplexity finance timeline NVDA

# Market overview
perplexity finance market                  # summary + indices + movers
perplexity finance movers
perplexity finance indices                 # stocks by default
perplexity finance indices --market crypto
perplexity finance sectors
perplexity finance fixed-income

# Prediction markets (Polymarket-backed)
perplexity finance predictions                 # tag=finance
perplexity finance predictions --tag politics
perplexity finance predictions --tag crypto --limit 20

# Personal
perplexity finance watchlist
perplexity finance watchlist --with-quotes
perplexity finance portfolio                   # Plaid-linked only
perplexity finance search apple                # autosuggest tickers

# Finance-focused chat
perplexity ask --finance "What's moving tech stocks today?"
```

Pipe JSON into `jq`:

```bash
perplexity finance quote NVDA --json | jq '.price'
perplexity finance movers --json | jq '.[:3] | .[] | {symbol, change_percent}'
```

## Python API

Use perplexity-cli as a library in your own projects:

```python
import asyncio
from perplexity import PerplexityClient

async def main():
    async with await PerplexityClient.from_storage() as client:
        # Simple question
        result = await client.chat.ask("What is Python?")
        print(result.answer)
        for source in result.sources:
            print(f"  - {source.name}: {source.url}")

        # Follow-up
        followup = await client.chat.ask_followup(
            "Show me an example", previous=result
        )
        print(followup.answer)

        # Deep research
        report = await client.chat.research("How does TCP/IP work?")
        print(report.answer)

        # List models
        models = await client.models.list(mode="search")
        for m in models:
            print(f"{m.name}: {m.label} ({m.provider})")

        # Recent threads
        threads = await client.threads.list_recent()
        for t in threads:
            print(f"{t.title} — {t.status}")

asyncio.run(main())
```

## Command Reference

| Command | Description |
|---------|-------------|
| `perplexity login` | Authenticate via browser |
| `perplexity status` | Show authentication status |
| `perplexity chat` | Interactive REPL with auto follow-ups |
| `perplexity ask [QUESTION]` | Ask a question (new thread) |
| `perplexity followup [QUESTION]` | Continue a conversation |
| `perplexity research [QUESTION]` | Deep research query |
| `perplexity models` | List available models |
| `perplexity history` | Recent threads from server |
| `perplexity threads` | Local saved threads |
| `perplexity finance quote TICKER` | Price quote (stock, crypto, index, ETF) |
| `perplexity finance profile TICKER` | Company profile |
| `perplexity finance why TICKER` | AI explanation of today's move |
| `perplexity finance news TICKER` | Publisher news for ticker |
| `perplexity finance timeline TICKER` | Narrative news timeline |
| `perplexity finance market` | Market overview (summary + indices + movers) |
| `perplexity finance movers` | Top market movers |
| `perplexity finance indices` | Major indices (stocks or crypto) |
| `perplexity finance sectors` | Sector ETFs |
| `perplexity finance fixed-income` | Bonds / yield instruments |
| `perplexity finance predictions` | Prediction markets (Polymarket) |
| `perplexity finance watchlist` | User's saved watchlist |
| `perplexity finance portfolio` | Plaid-linked portfolio overview |
| `perplexity finance search QUERY` | Autosuggest tickers |

### Global options

| Option | Description |
|--------|-------------|
| `--version` | Show version |
| `--storage PATH` | Override storage_state.json path |

### Common options (ask, followup, research)

| Option | Description |
|--------|-------------|
| `-t, --thread NAME` | Name the thread for later follow-ups |
| `--model TEXT` | Model to use (default: `pplx_pro`) |
| `--no-sources` | Hide source citations |
| `--raw` | Plain text output (no Rich formatting) |
| `--finance` | (ask only) Bias the search toward finance sources |

### Common options (finance)

| Option | Description |
|--------|-------------|
| `--country XX` | ISO country code (default: `US`) |
| `--json` | JSON output for piping into jq |

## How it works

perplexity-cli reverse-engineers Perplexity's internal web API — the same API that the browser frontend uses. It authenticates using your browser session cookies (captured via Playwright) and communicates via standard REST + Server-Sent Events (SSE).

**Architecture:**

```
CLI (Click) → PerplexityClient → ChatAPI → ClientCore (httpx + SSE)
```

**Protocol:**
- Endpoint: `POST /rest/sse/perplexity_ask`
- Auth: Cookie-based (NextAuth.js session + Cloudflare clearance)
- Streaming: SSE with JSON payloads per event
- Follow-ups: `backend_uuid` + `read_write_token` from previous response

## Disclaimer

This is an **unofficial** tool that uses Perplexity's internal web API. It is not affiliated with or endorsed by Perplexity AI. The API can change without notice, which may break this tool. Use at your own risk and in accordance with Perplexity's terms of service.

## License

MIT
