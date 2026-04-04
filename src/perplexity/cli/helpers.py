"""Shared utilities for CLI commands."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import wraps
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from perplexity.auth import AuthTokens
from perplexity.client import PerplexityClient
from perplexity.exceptions import AuthenticationError, PerplexityError

# Single shared Console instance for all CLI modules
console = Console()


def get_storage_from_ctx(ctx: click.Context) -> Path | None:
    """Extract the --storage path from the Click context.

    The top-level CLI group accepts --storage and stores it in ctx.obj.
    This helper retrieves and converts it to a Path.

    Args:
        ctx: Click context from the parent group.

    Returns:
        Path to storage_state.json override, or None for default.
    """
    storage = ctx.obj.get("storage") if ctx.obj else None
    return Path(storage) if storage else None


def run_async(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that runs an async Click command handler synchronously.

    Click doesn't support async commands natively. This wraps an async
    function so it can be used as a Click command callback.

    Args:
        func: Async function to wrap.

    Returns:
        Synchronous wrapper that calls asyncio.run().
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


def require_auth(storage_path: Path | None = None) -> AuthTokens:
    """Load auth tokens or exit with a user-friendly error.

    Args:
        storage_path: Optional explicit path to storage_state.json.

    Returns:
        AuthTokens from stored browser session.
    """
    try:
        return AuthTokens.from_storage(storage_path)
    except AuthenticationError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)


@asynccontextmanager
async def authenticated_client(
    storage_path: Path | None = None,
) -> AsyncIterator[PerplexityClient]:
    """Context manager providing an authenticated PerplexityClient.

    Handles auth errors and API errors with user-friendly messages,
    exiting with code 1 on failure.

    Args:
        storage_path: Optional explicit path to storage_state.json.

    Yields:
        Open PerplexityClient ready for API calls.
    """
    auth = require_auth(storage_path)
    try:
        async with PerplexityClient(auth) as client:
            yield client
    except PerplexityError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
