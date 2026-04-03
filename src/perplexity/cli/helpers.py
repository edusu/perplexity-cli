"""Shared utilities for CLI commands."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from rich.console import Console

console = Console(stderr=True)


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
