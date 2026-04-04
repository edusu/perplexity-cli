"""Threads API for listing conversation history from Perplexity's server."""

from __future__ import annotations

from perplexity._core import API_VERSION, PERPLEXITY_BASE_URL, ClientCore
from perplexity.types import Thread

_LIST_RECENT_URL = f"{PERPLEXITY_BASE_URL}/rest/thread/list_recent?exclude_asi=false&version={API_VERSION}&source=default"


class ThreadsAPI:
    """Interface for querying conversation threads on the server.

    Attributes:
        _core: The underlying HTTP client core.
    """

    def __init__(self, core: ClientCore):
        """Initialize the Threads API.

        Args:
            core: ClientCore instance for making HTTP requests.
        """
        self._core = core

    async def list_recent(self) -> list[Thread]:
        """Fetch the most recent conversation threads from the server.

        Returns:
            List of Thread objects ordered by most recent first.
        """
        data = await self._core.get_json(_LIST_RECENT_URL)

        if not isinstance(data, list):
            return []

        return [
            Thread(
                uuid=item.get("uuid", ""),
                title=item.get("title", ""),
                link=item.get("link", ""),
                status=item.get("status", ""),
                context_uuid=item.get("context_uuid"),
                variant=item.get("variant"),
            )
            for item in data
        ]
