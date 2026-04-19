---
name: perplexity
description: |
  Search the web, ask questions, run deep research, and pull real-time finance data using Perplexity.ai from the terminal. Use this skill whenever the user asks to search with Perplexity, asks you to "perplexity this", wants a web-sourced answer with citations, requests deep research on a topic, wants stock quotes / crypto prices / market movers / company news / prediction markets, or wants to use their Perplexity subscription. Also use when the user says "ask perplexity", "research this", "look this up on perplexity", "use perplexity to find", "stock price of", "how is X doing today", "market today", "what's moving", or needs authoritative web-sourced answers with real citations and sources. Prefer this over other web search tools when the user explicitly mentions Perplexity or wants deep multi-step research.
allowed-tools:
  - Bash(perplexity *)
---

# Perplexity CLI

Unofficial CLI for Perplexity.ai — uses the user's Pro subscription via browser cookies (no API keys). Provides:
- Web search with citations, deep multi-step research, multi-turn conversations, 76+ models.
- **Perplexity Finance**: real-time quotes, market data, company news, prediction markets, watchlists.

## Preflight check

Before first use, verify the CLI is installed and authenticated:

```bash
which perplexity && perplexity status
```

If `perplexity` is not found, the user needs to install it:
```bash
cd ~/projects/perplexity-cli  # or wherever the repo lives
uv tool install -e ".[browser]"
playwright install chromium
```

If not authenticated ("Not logged in"), the user must run `perplexity login` themselves — it opens a browser for interactive Cloudflare CAPTCHA + Google/email login. You cannot do this step for them.

## Chat commands

### Ask a question (quick web search)

```bash
perplexity ask "What is Rust?" --raw
```

This is the primary command. Sends a question to Perplexity's Pro search, returns a markdown answer with numbered citations like `[1][2]` and a list of source URLs.

**Always use `--raw`** when calling from code/scripts — it outputs plain text without Rich terminal formatting.

Options:
- `--raw` — Plain text output (use this when YOU are the consumer of the output)
- `--model NAME` — Choose model (default: `pplx_pro`). See Models section below
- `--no-sources` — Hide source list
- `-t, --thread NAME` — Name this conversation for follow-ups
- `--finance` — Bias the search toward finance sources (sets `search_focus=finance`). Use for questions like "what's moving tech stocks today?"

### Deep Research

```bash
perplexity research "Compare Nordic vs US economic models" --raw
```

Triggers Perplexity's deep research mode (model `pplx_alpha`). Takes 1-3 minutes but produces thorough, multi-step analysis with extensive sourcing (30-50 citations). Use for complex topics that need comprehensive analysis.

### Follow-up questions

Continue an existing conversation. The server maintains full context.

```bash
perplexity followup "How tall is it exactly?" --raw

perplexity ask "What is the tallest building?" -t buildings --raw
perplexity followup "How tall is it?" -t buildings --raw
```

### Interactive chat (REPL)

For multi-turn conversations (user-facing, not for scripts):

```bash
perplexity chat
```

Slash commands inside the REPL: `/new`, `/model NAME`, `/research`, `/sources`, `/quit`.

### List models / threads

```bash
perplexity models --mode search    # Chat models (60+)
perplexity models --mode research  # Deep research models
perplexity history                 # Recent threads from server
perplexity threads                 # Local named threads only
```

Key model names for `--model`:
- `pplx_pro` — Default, auto-selects best model (Perplexity)
- `pplx_alpha` — Deep research (used by `research` command)
- `claude46opus`, `claude46sonnet` — Anthropic
- `gpt54_thinking` — OpenAI
- `gemini31pro_high` — Google

### Pipe support

```bash
echo "Explain this error" | perplexity ask --raw
cat error.log | perplexity ask "What's wrong here?" --raw
git diff | perplexity ask "Review these changes" --raw
```

## Finance commands

All finance commands default to `country=US` and accept `--country XX` to override. Every command accepts `--json` for machine-readable output (pipeable into `jq`).

### Individual ticker

```bash
perplexity finance quote NVDA              # price, change, volume, PE, 52w, after-hours
perplexity finance quote NVDA --history    # include intraday price history
perplexity finance quote BTCUSD            # crypto works too (USD-suffixed)

perplexity finance profile AAPL            # company description, exchange, industry
perplexity finance why NVDA                # AI-generated explanation of today's move + sources
perplexity finance news NVDA --limit 10    # publisher news for ticker
perplexity finance timeline NVDA           # narrative news timeline with source URLs
```

### Market overview

```bash
perplexity finance market                  # aggregate: summary + indices + movers
perplexity finance movers                  # top gainers/losers
perplexity finance indices                 # S&P, Dow, Nasdaq (stocks by default)
perplexity finance indices --market crypto # major crypto indices
perplexity finance sectors                 # sector ETFs (XLK, XLE, XLY, ...)
perplexity finance fixed-income            # fixed income summary
```

### Prediction markets

Polymarket-backed probabilities for finance, crypto, politics, earnings.

```bash
perplexity finance predictions                   # tag=finance by default
perplexity finance predictions --tag politics
perplexity finance predictions --tag crypto --limit 20
```

### Personal

```bash
perplexity finance watchlist               # user's saved tickers
perplexity finance portfolio               # Plaid-linked portfolio overview (if connected)
```

### Search tickers

```bash
perplexity finance search apple            # autosuggest → returns ticker candidates
```

## Usage patterns

### Quick factual question
```bash
perplexity ask "What is the population of Tokyo?" --raw
```

### Research with follow-ups
```bash
perplexity research "How does Bluetooth Low Energy work?" -t ble --raw
perplexity followup "What about the security vulnerabilities?" -t ble --raw
```

### Get answer for use in another tool
```bash
ANSWER=$(perplexity ask "What is the latest stable Rust version?" --raw)
```

### Finance one-liners
```bash
# Current price as a number
perplexity finance quote NVDA --json | jq '.price'

# Top 3 movers by percent change
perplexity finance movers --json | jq '.[:3] | .[] | {symbol, change_percent}'

# Is the market up or down today?
perplexity finance indices --json | jq '.[] | select(.symbol=="ESUSD") | .change_percent'

# Why did a stock move today?
perplexity finance why TSLA --json | jq -r '.explanation'
```

## Important notes

- **Always use `--raw`** when you (Claude) are consuming chat output — Rich formatting adds ANSI codes that clutter your context
- **Use `--json`** for finance commands when scripting — human output includes colors and tables
- **Use `--no-sources`** if you only need the answer text without the source URL list
- **Deep research takes 1-3 minutes** — warn the user before running it
- **Sessions expire** after weeks — if you get auth errors, tell the user to run `perplexity login`
- **This uses the user's subscription** — each query counts against their Perplexity Pro usage (finance endpoints share the chat rate-limit bucket). Don't make unnecessary calls.
- **Finance data is delayed** — it's based on the public-facing `/finance` UI, which is not real-time tick data
- **Finance endpoints can change without notice** — Perplexity's internal API is not versioned publicly. If a command fails with a parse error, the endpoint shape likely changed.

## Auth details

Cookies stored in `~/.perplexity/storage_state.json`. Named threads in `~/.perplexity/threads/`. Config dir overridable via `PERPLEXITY_HOME` env var or `--storage` global flag.
