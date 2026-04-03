"""CLI commands for chat interactions."""

from __future__ import annotations

import asyncio
import json
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from perplexity.auth import AuthTokens
from perplexity.cli.helpers import run_async
from perplexity.client import PerplexityClient
from perplexity.exceptions import AuthenticationError, PerplexityError
from perplexity.paths import get_threads_dir
from perplexity.types import AskResult

console = Console()

# Name used when --thread is not specified
_DEFAULT_THREAD = "_last"


def _thread_path(name: str):
    """Return the JSON file path for a named thread."""
    return get_threads_dir() / f"{name}.json"


def _save_thread(name: str, result: AskResult) -> None:
    """Persist thread metadata for follow-up.

    Only stores the IDs needed to continue the conversation, never the
    full answer text.

    Args:
        name: Thread name (user-chosen or _last).
        result: AskResult with metadata to save.
    """
    data = {
        "backend_uuid": result.backend_uuid,
        "context_uuid": result.context_uuid,
        "read_write_token": result.read_write_token,
        "thread_url_slug": result.thread_url_slug,
        "model": result.model,
    }
    _thread_path(name).write_text(json.dumps(data))
    # Also update _last so bare `followup` without --thread works
    if name != _DEFAULT_THREAD:
        _thread_path(_DEFAULT_THREAD).write_text(json.dumps(data))


def _load_thread(name: str) -> AskResult | None:
    """Load a saved thread context by name.

    Args:
        name: Thread name to load.

    Returns:
        AskResult stub with metadata fields, or None if not found.
    """
    path = _thread_path(name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return AskResult(
            answer="",
            backend_uuid=data.get("backend_uuid"),
            context_uuid=data.get("context_uuid"),
            read_write_token=data.get("read_write_token"),
            thread_url_slug=data.get("thread_url_slug"),
            model=data.get("model"),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def _render_result(
    result: AskResult, raw: bool, no_sources: bool, thread_name: str | None = None
) -> None:
    """Render an AskResult to the terminal.

    Args:
        result: The result to display.
        raw: If True, print plain text without Rich formatting.
        no_sources: If True, hide source citations.
        thread_name: Optional thread name to show in the footer.
    """
    if not result.answer:
        console.print("[yellow]No answer received.[/yellow]")
        raise SystemExit(1)

    if raw:
        click.echo(result.answer)
        return

    console.print()
    console.print(Markdown(result.answer))
    console.print()

    if not no_sources and result.sources:
        console.print("[bold]Sources:[/bold]")
        for i, source in enumerate(result.sources, 1):
            console.print(f"  [cyan][{i}][/cyan] {source.name}")
            console.print(f"      [dim]{source.url}[/dim]")
        console.print()

    parts = []
    if thread_name and thread_name != _DEFAULT_THREAD:
        parts.append(f"Thread: {thread_name}")
    if result.model:
        parts.append(f"Model: {result.model}")
    if result.thread_url_slug:
        parts.append(f"perplexity.ai/search/{result.thread_url_slug}")
    if parts:
        console.print(f"[dim]{' | '.join(parts)}[/dim]")


def _resolve_question(question: str | None) -> str:
    """Resolve the question from argument or stdin.

    If no question argument is provided and stdin is piped (not a TTY),
    reads the question from stdin. Useful for piping content into the CLI.

    Args:
        question: The question from the CLI argument, or None if not provided.

    Returns:
        The resolved question text.
    """
    if question:
        return question
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            return stdin_text
    click.echo("Error: No question provided. Pass a question as argument or pipe via stdin.", err=True)
    raise SystemExit(1)


@click.command()
@click.argument("question", required=False, default=None)
@click.option("--thread", "-t", default=None, help="Name this thread for later follow-ups.")
@click.option("--model", default="pplx_pro", help="Model preference (e.g. pplx_pro).")
@click.option("--no-sources", is_flag=True, help="Hide source citations.")
@click.option("--raw", is_flag=True, help="Print raw answer without Rich formatting.")
@run_async
async def ask(
    question: str, thread: str | None, model: str, no_sources: bool, raw: bool
) -> None:
    """Ask Perplexity a question and display the answer.

    Starts a new conversation thread. Use 'followup' to continue.

    Examples:

        perplexity ask "What is Rust?"

        perplexity ask "What is Rust?" --thread rust

        perplexity ask "Latest news about AI" -t news --model pplx_pro
    """
    question = _resolve_question(question)
    try:
        auth = AuthTokens.from_storage()
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    try:
        async with PerplexityClient(auth) as client:
            result = await client.chat.ask(question, model=model)
    except PerplexityError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    thread_name = thread or _DEFAULT_THREAD
    _save_thread(thread_name, result)
    _render_result(result, raw, no_sources, thread_name=thread)


@click.command()
@click.argument("question", required=False, default=None)
@click.option("--thread", "-t", default=None, help="Thread name to continue (default: last used).")
@click.option("--model", default="pplx_pro", help="Model preference (e.g. pplx_pro).")
@click.option("--no-sources", is_flag=True, help="Hide source citations.")
@click.option("--raw", is_flag=True, help="Print raw answer without Rich formatting.")
@run_async
async def followup(
    question: str, thread: str | None, model: str, no_sources: bool, raw: bool
) -> None:
    """Ask a follow-up question in an existing conversation thread.

    By default continues the most recent thread. Use --thread to pick
    a specific named thread.

    Examples:

        perplexity ask "What is Rust?" --thread rust
        perplexity followup "Is it fast?" --thread rust

        perplexity ask "What is Python?"
        perplexity followup "Show me an example"
    """
    question = _resolve_question(question)
    try:
        auth = AuthTokens.from_storage()
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    thread_name = thread or _DEFAULT_THREAD
    previous = _load_thread(thread_name)

    if not previous or not previous.backend_uuid or not previous.read_write_token:
        if thread:
            console.print(f"[red]Thread '{thread}' not found.[/red]")
            console.print("Use [bold]perplexity threads[/bold] to list available threads.")
        else:
            console.print(
                "[red]No previous conversation found.[/red]\n"
                "Use [bold]perplexity ask[/bold] first to start a thread."
            )
        raise SystemExit(1)

    try:
        async with PerplexityClient(auth) as client:
            result = await client.chat.ask_followup(
                question, previous=previous, model=model
            )
    except PerplexityError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    _save_thread(thread_name, result)
    _render_result(result, raw, no_sources, thread_name=thread)


@click.command()
@click.argument("question", required=False, default=None)
@click.option("--thread", "-t", default=None, help="Name this research thread.")
@click.option("--no-sources", is_flag=True, help="Hide source citations.")
@click.option("--raw", is_flag=True, help="Print raw answer without Rich formatting.")
@run_async
async def research(
    question: str, thread: str | None, no_sources: bool, raw: bool
) -> None:
    """Run a deep research query on a topic.

    Uses Perplexity's deep research mode which performs multi-step
    analysis. Takes 1-3 minutes but produces thorough results.

    Examples:

        perplexity research "How does Bluetooth work?"

        perplexity research "Compare Rust vs Go for web servers" -t rustvsgo
    """
    question = _resolve_question(question)
    try:
        auth = AuthTokens.from_storage()
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    if not raw:
        console.print("[yellow]Starting deep research (this may take 1-3 minutes)...[/yellow]")

    try:
        async with PerplexityClient(auth) as client:
            result = await client.chat.research(question)
    except PerplexityError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    thread_name = thread or _DEFAULT_THREAD
    _save_thread(thread_name, result)
    _render_result(result, raw, no_sources, thread_name=thread)


@click.command("threads")
def list_threads() -> None:
    """List saved conversation threads."""
    threads_dir = get_threads_dir()
    thread_files = sorted(threads_dir.glob("*.json"))

    # Filter out the _last pointer
    named = [f for f in thread_files if f.stem != _DEFAULT_THREAD]

    if not named:
        console.print("[dim]No named threads. Use --thread/-t with ask to create one.[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("Thread", style="bold cyan")
    table.add_column("URL Slug", style="dim")

    for f in named:
        try:
            data = json.loads(f.read_text())
            slug = data.get("thread_url_slug", "")
            table.add_row(f.stem, slug)
        except (json.JSONDecodeError, KeyError):
            table.add_row(f.stem, "[red]corrupt[/red]")

    console.print(table)


@click.command()
@run_async
async def history() -> None:
    """List recent conversation threads from the server.

    Shows the 20 most recent threads from your Perplexity account,
    including threads created from the web UI.
    """
    try:
        auth = AuthTokens.from_storage()
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    try:
        async with PerplexityClient(auth) as client:
            threads = await client.threads.list_recent()
    except PerplexityError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if not threads:
        console.print("[dim]No recent threads found.[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold")
    table.add_column("Status", style="dim")
    table.add_column("Link", style="dim")

    for i, t in enumerate(threads, 1):
        link = f"perplexity.ai{t.link}" if t.link else ""
        table.add_row(str(i), t.title, t.status, link)

    console.print(table)


_CHAT_HELP = """
  [bold]Commands:[/bold]
    [cyan]/new[/cyan]            Start a new conversation
    [cyan]/model NAME[/cyan]    Switch model (e.g. /model claude46opus)
    [cyan]/research[/cyan]       Toggle deep research mode
    [cyan]/sources[/cyan]        Toggle source display
    [cyan]/help[/cyan]           Show this help
    [cyan]/quit[/cyan]           Exit (also Ctrl+D or Ctrl+C)
"""


@click.command("chat")
@click.option("--model", default="pplx_pro", help="Initial model preference.")
@click.option("--no-sources", is_flag=True, help="Start with sources hidden.")
def chat(model: str, no_sources: bool) -> None:
    """Interactive chat REPL with automatic follow-ups.

    Start a conversation and keep asking questions. Follow-ups are
    automatic within the same thread. Use /new to start a fresh thread.

    Examples:

        perplexity chat

        perplexity chat --model claude46opus
    """
    try:
        auth = AuthTokens.from_storage()
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    asyncio.run(_chat_loop(auth, model, no_sources))


async def _chat_loop(auth: AuthTokens, model: str, hide_sources: bool) -> None:
    """Run the interactive chat REPL.

    Args:
        auth: Authentication tokens.
        model: Initial model preference.
        hide_sources: Whether to hide source citations initially.
    """
    console.print()
    console.print("[bold]Perplexity Chat[/bold] — interactive mode")
    console.print(f"[dim]Model: {model} | Type /help for commands[/dim]")
    console.print()

    previous: AskResult | None = None
    research_mode = False

    async with PerplexityClient(auth) as client:
        while True:
            # Prompt
            try:
                prompt_model = model if not research_mode else "research"
                question = console.input(f"[bold cyan]{prompt_model}>[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye.[/dim]")
                break

            question = question.strip()
            if not question:
                continue

            # Handle slash commands
            if question.startswith("/"):
                cmd = question.lower().split()
                match cmd[0]:
                    case "/quit" | "/exit" | "/q":
                        console.print("[dim]Goodbye.[/dim]")
                        break
                    case "/new":
                        previous = None
                        console.print("[dim]New conversation started.[/dim]")
                        continue
                    case "/model":
                        if len(cmd) > 1:
                            model = cmd[1]
                            console.print(f"[dim]Model set to: {model}[/dim]")
                        else:
                            console.print(f"[dim]Current model: {model}[/dim]")
                        continue
                    case "/research":
                        research_mode = not research_mode
                        state = "on" if research_mode else "off"
                        console.print(f"[dim]Deep research mode: {state}[/dim]")
                        continue
                    case "/sources":
                        hide_sources = not hide_sources
                        state = "hidden" if hide_sources else "shown"
                        console.print(f"[dim]Sources: {state}[/dim]")
                        continue
                    case "/help":
                        console.print(_CHAT_HELP)
                        continue
                    case _:
                        console.print(f"[yellow]Unknown command: {cmd[0]}[/yellow]")
                        continue

            # Send the question
            try:
                active_model = "pplx_alpha" if research_mode else model

                if research_mode and not previous:
                    console.print("[dim]Researching (this may take 1-3 minutes)...[/dim]")

                if previous:
                    result = await client.chat.ask_followup(
                        question, previous=previous, model=active_model
                    )
                else:
                    result = await client.chat.ask(
                        question, model=active_model
                    )

                previous = result

            except PerplexityError as e:
                console.print(f"[red]Error: {e}[/red]")
                continue

            # Render
            if not result.answer:
                console.print("[yellow]No answer received.[/yellow]")
                continue

            console.print()
            console.print(Markdown(result.answer))
            console.print()

            if not hide_sources and result.sources:
                console.print("[bold]Sources:[/bold]")
                for i, source in enumerate(result.sources, 1):
                    console.print(f"  [cyan][{i}][/cyan] {source.name}")
                    console.print(f"      [dim]{source.url}[/dim]")
                console.print()
