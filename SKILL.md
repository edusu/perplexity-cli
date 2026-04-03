---
name: perplexity
description: |
  Search the web, ask questions, and run deep research using Perplexity.ai from the terminal. Use this skill whenever the user asks to search with Perplexity, asks you to "perplexity this", wants a web-sourced answer with citations, requests deep research on a topic, or wants to use their Perplexity subscription. Also use when the user says "ask perplexity", "research this", "look this up on perplexity", "use perplexity to find", or needs authoritative web-sourced answers with real citations and sources. Prefer this over other web search tools when the user explicitly mentions Perplexity or wants deep multi-step research.
allowed-tools:
  - Bash(perplexity *)
---

# Perplexity CLI

Unofficial CLI for Perplexity.ai — uses the user's Pro subscription via browser cookies (no API keys). Provides web search with citations, deep multi-step research, multi-turn conversations, and access to 76+ models.

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

## Commands

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

### Deep Research

```bash
perplexity research "Compare Nordic vs US economic models" --raw
```

Triggers Perplexity's deep research mode (model `pplx_alpha`). Takes 1-3 minutes but produces thorough, multi-step analysis with extensive sourcing (30-50 citations). Use for complex topics that need comprehensive analysis.

Options: same as `ask` except `--model` (fixed to `pplx_alpha`).

### Follow-up questions

Continue an existing conversation. The server maintains full context — the follow-up knows what was discussed before.

```bash
# After an ask or research:
perplexity followup "How tall is it exactly?" --raw

# Or with a named thread:
perplexity ask "What is the tallest building?" -t buildings --raw
perplexity followup "How tall is it?" -t buildings --raw
perplexity followup "When was it built?" -t buildings --raw
```

### Interactive chat (REPL)

For multi-turn conversations (user-facing, not for scripts):

```bash
perplexity chat
```

Slash commands inside the REPL: `/new` (new thread), `/model NAME` (switch model), `/research` (toggle deep research), `/sources` (toggle citations), `/quit`.

### List models

```bash
perplexity models --mode search    # Chat models (60+)
perplexity models --mode research  # Deep research models
```

Key model names for `--model`:
- `pplx_pro` — Default, auto-selects best model (Perplexity)
- `pplx_alpha` — Deep research (used automatically by `research` command)
- `claude46opus` — Claude Opus 4.6 (Anthropic)
- `claude46sonnet` — Claude Sonnet 4.6 (Anthropic)
- `gpt54_thinking` — GPT-5.4 Thinking (OpenAI)
- `gemini31pro_high` — Gemini 3.1 Pro Thinking (Google)

### List recent threads

```bash
perplexity history           # Recent threads from server (includes web UI)
perplexity threads           # Local named threads only
```

### Pipe support

Read questions from stdin — useful for sending file contents or command output:

```bash
echo "Explain this error" | perplexity ask --raw
cat error.log | perplexity ask "What's wrong here?" --raw
git diff | perplexity ask "Review these changes" --raw
```

When piping content WITH a question argument, the stdin content is prepended to the question.

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

### Use a specific model
```bash
perplexity ask "Explain monads simply" --model claude46opus --raw
```

### Get answer for use in another tool
```bash
ANSWER=$(perplexity ask "What is the latest stable Rust version?" --raw)
echo "Perplexity says: $ANSWER"
```

## Important notes

- **Always use `--raw`** when you (Claude) are consuming the output — Rich formatting adds ANSI codes that clutter your context
- **Use `--no-sources`** if you only need the answer text without the source URL list
- **Deep research takes 1-3 minutes** — warn the user before running it
- **Sessions expire** after weeks — if you get auth errors, tell the user to run `perplexity login`
- **This uses the user's subscription** — each query counts against their Perplexity Pro usage, so don't make unnecessary calls
- **Rate limits apply** — if you get rate limit errors, wait before retrying

## Auth details

Cookies stored in `~/.perplexity/storage_state.json`. Named threads in `~/.perplexity/threads/`. Config dir overridable via `PERPLEXITY_HOME` env var or `--storage` global flag.
