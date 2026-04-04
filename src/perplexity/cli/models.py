"""CLI command for listing available models."""

from __future__ import annotations

import click
from rich.table import Table

from perplexity.cli.helpers import authenticated_client, console, get_storage_from_ctx, run_async


@click.command()
@click.option(
    "--mode", default=None, help="Filter by mode (search, research, agentic_research, etc.)."
)
@click.pass_context
@run_async
async def models(ctx: click.Context, mode: str | None) -> None:
    """List available models.

    Shows all models you can use with --model in ask/followup commands.

    Examples:

        perplexity models

        perplexity models --mode search

        perplexity models --mode research
    """
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        model_list = await client.models.list(mode=mode)

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
