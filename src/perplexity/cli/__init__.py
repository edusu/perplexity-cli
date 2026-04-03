"""CLI entry point and command registration."""

from __future__ import annotations

import click

from perplexity.cli.chat import ask, chat, followup, history, list_threads, research
from perplexity.cli.models import models
from perplexity.cli.session import login, status


@click.group()
@click.version_option(version="0.1.0", prog_name="perplexity-cli")
@click.option(
    "--storage",
    type=click.Path(),
    default=None,
    envvar="PERPLEXITY_STORAGE",
    help="Override path to storage_state.json.",
)
@click.pass_context
def cli(ctx: click.Context, storage: str | None) -> None:
    """Unofficial CLI for Perplexity.ai."""
    ctx.ensure_object(dict)
    ctx.obj["storage"] = storage


cli.add_command(login)
cli.add_command(status)
cli.add_command(ask)
cli.add_command(chat)
cli.add_command(followup)
cli.add_command(research)
cli.add_command(models)
cli.add_command(list_threads)
cli.add_command(history)


def main() -> None:
    """Entry point for the perplexity CLI."""
    cli()
