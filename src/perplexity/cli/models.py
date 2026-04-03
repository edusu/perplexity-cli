"""CLI command for listing available models."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from perplexity.auth import AuthTokens
from perplexity.cli.helpers import run_async
from perplexity.client import PerplexityClient
from perplexity.exceptions import AuthenticationError, PerplexityError

console = Console()


@click.command()
@click.option("--mode", default=None, help="Filter by mode (search, research, agentic_research, etc.).")
@run_async
async def models(mode: str | None) -> None:
    """List available models.

    Shows all models you can use with --model in ask/followup commands.

    Examples:

        perplexity models

        perplexity models --mode search

        perplexity models --mode research
    """
    try:
        auth = AuthTokens.from_storage()
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    try:
        async with PerplexityClient(auth) as client:
            model_list = await client.models.list(mode=mode)
    except PerplexityError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if not model_list:
        console.print("[yellow]No models found.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Label")
    table.add_column("Provider", style="dim")
    table.add_column("Mode", style="dim")

    for m in model_list:
        provider = m.provider or "Perplexity"
        table.add_row(m.name, m.label, provider, m.mode)

    console.print(table)
    console.print(f"\n[dim]{len(model_list)} models available[/dim]")
