"""HTTP client infrastructure for Perplexity API.

Manages the httpx async client lifecycle and provides SSE streaming
for the Perplexity chat endpoint.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from perplexity.auth import AuthTokens
from perplexity.exceptions import AuthenticationError, ChatError, RateLimitError

logger = logging.getLogger(__name__)

PERPLEXITY_BASE_URL = "https://www.perplexity.ai"
PERPLEXITY_ASK_URL = f"{PERPLEXITY_BASE_URL}/rest/sse/perplexity_ask"

# Mimic a real Chrome browser to avoid bot detection
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 60.0
DEFAULT_CONNECT_TIMEOUT = 10.0


class ClientCore:
    """Low-level HTTP client for Perplexity API requests.

    Manages httpx.AsyncClient lifecycle and provides SSE streaming.
    Used internally by the ChatAPI; not intended for direct use.

    Attributes:
        auth: Authentication tokens from browser login.
    """

    def __init__(
        self,
        auth: AuthTokens,
        timeout: float = DEFAULT_TIMEOUT,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    ):
        """Initialize the core client.

        Args:
            auth: Authentication tokens with browser cookies.
            timeout: HTTP read/write timeout in seconds.
            connect_timeout: Connection establishment timeout in seconds.
        """
        self.auth = auth
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        """Open the HTTP client connection."""
        if self._client is None:
            timeout = httpx.Timeout(
                connect=self._connect_timeout,
                read=self._timeout,
                write=self._timeout,
                pool=self._timeout,
            )
            self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> ClientCore:
        await self.open()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for Perplexity API requests."""
        return {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cookie": self.auth.cookie_header,
            "User-Agent": BROWSER_USER_AGENT,
            "Referer": f"{PERPLEXITY_BASE_URL}/",
        }

    async def sse_request(
        self, url: str, payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Send a POST request and stream SSE events.

        Sends a JSON POST to the given URL and yields parsed JSON objects
        from each SSE `data:` line in the response stream.

        Args:
            url: The SSE endpoint URL.
            payload: JSON request body.

        Yields:
            Parsed JSON dicts from each SSE event.

        Raises:
            AuthenticationError: On 401/403 responses.
            RateLimitError: On 429 responses.
            ChatError: On other HTTP errors.
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        headers = self._build_headers()

        async with self._client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            _check_response_status(response)

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                    if parsed:  # Skip empty final event {}
                        yield parsed
                except json.JSONDecodeError:
                    logger.warning("Failed to parse SSE data: %s", raw[:200])


    async def get_json(self, url: str) -> Any:
        """Send an authenticated GET request and return parsed JSON.

        Args:
            url: The API endpoint URL.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: On 401/403 responses.
            RateLimitError: On 429 responses.
            ChatError: On other HTTP errors.
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        headers = self._build_headers()
        headers["Accept"] = "application/json"

        response = await self._client.get(url, headers=headers)
        _check_response_status(response)
        return response.json()


def _check_response_status(response: httpx.Response) -> None:
    """Raise appropriate exception for non-200 HTTP responses.

    Args:
        response: The httpx response to check.

    Raises:
        AuthenticationError: On 401/403 responses.
        RateLimitError: On 429 responses.
        ChatError: On other non-2xx responses.
    """
    status = response.status_code
    if 200 <= status < 300:
        return
    if status in (401, 403):
        raise AuthenticationError(
            f"Authentication failed (HTTP {status}). Run 'perplexity login' to re-authenticate."
        )
    if status == 429:
        raise RateLimitError("Rate limit exceeded. Please wait before trying again.")
    raise ChatError(f"API request failed with HTTP {status}.")
