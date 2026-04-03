"""Data types for Perplexity API responses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Source:
    """A web source cited in a Perplexity answer.

    Attributes:
        name: Title of the source page.
        url: URL of the source.
        snippet: Brief excerpt from the source content.
    """

    name: str
    url: str
    snippet: str


@dataclass
class AskResult:
    """Result from a Perplexity chat query.

    Attributes:
        answer: Full markdown-formatted answer text.
        sources: Web sources cited in the answer.
        backend_uuid: Server-assigned ID for this answer entry.
        context_uuid: Thread/conversation context ID for follow-ups.
        thread_url_slug: URL slug for viewing this thread on perplexity.ai.
        model: Model used for the response (e.g. "pplx_pro").
        read_write_token: Token required for sending follow-up messages in the same thread.
    """

    answer: str
    sources: list[Source] = field(default_factory=list)
    backend_uuid: str | None = None
    context_uuid: str | None = None
    thread_url_slug: str | None = None
    model: str | None = None
    read_write_token: str | None = None
