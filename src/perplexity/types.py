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


@dataclass
class Model:
    """A model available in Perplexity.

    Attributes:
        name: Internal model identifier (e.g. "pplx_pro", "claude2").
        label: User-facing display name (e.g. "Best", "Claude Sonnet 4.0").
        description: Short description of the model's capabilities.
        mode: Execution mode (e.g. "search", "research", "agentic_research").
        provider: Provider name (e.g. "OPENAI", "ANTHROPIC", "GOOGLE") or None for Perplexity models.
    """

    name: str
    label: str
    description: str
    mode: str
    provider: str | None = None


@dataclass
class Thread:
    """A conversation thread from Perplexity's server history.

    Attributes:
        uuid: Server-assigned thread ID.
        title: Auto-generated thread title from the first question.
        link: Relative URL path to view the thread on perplexity.ai.
        status: Thread status (e.g. "completed").
        context_uuid: Context ID for the thread.
        variant: Thread type (e.g. "thread").
    """

    uuid: str
    title: str
    link: str
    status: str
    context_uuid: str | None = None
    variant: str | None = None
