"""Main Perplexity client with async context manager.

Provides the primary interface for interacting with Perplexity's API.
Uses the namespaced API pattern from notebooklm-py.
"""

from __future__ import annotations

from pathlib import Path

from perplexity._chat import ChatAPI
from perplexity._core import ClientCore
from perplexity.auth import AuthTokens


class PerplexityClient:
    """Async client for the Perplexity.ai API.

    Usage::

        async with await PerplexityClient.from_storage() as client:
            result = await client.chat.ask("What is Python?")
            print(result.answer)

    Attributes:
        chat: Chat API for asking questions.
    """

    def __init__(self, auth: AuthTokens):
        """Initialize the client with authentication tokens.

        Args:
            auth: Authentication tokens from browser login.
        """
        self._core = ClientCore(auth)
        self.chat = ChatAPI(self._core)

    async def __aenter__(self) -> PerplexityClient:
        await self._core.open()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._core.close()

    @classmethod
    async def from_storage(cls, path: Path | None = None) -> PerplexityClient:
        """Create a client from saved browser session.

        Loads authentication cookies from the Playwright storage state file.

        Args:
            path: Optional explicit path to storage_state.json.

        Returns:
            Initialized PerplexityClient (not yet opened — use as async context manager).
        """
        auth = AuthTokens.from_storage(path)
        return cls(auth)
