"""Perplexity CLI — unofficial Python client for Perplexity.ai."""

from perplexity.auth import AuthTokens
from perplexity.client import PerplexityClient
from perplexity.exceptions import (
    AuthenticationError,
    ChatError,
    PerplexityError,
    RateLimitError,
)
from perplexity.types import AskResult, Source

__version__ = "0.1.0"

__all__ = [
    "AuthTokens",
    "AskResult",
    "AuthenticationError",
    "ChatError",
    "PerplexityClient",
    "PerplexityError",
    "RateLimitError",
    "Source",
]
