"""Chat API for Perplexity.

Implements the ask endpoint using SSE streaming. Sends questions to
Perplexity's internal API and parses streamed responses into structured results.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from perplexity._core import PERPLEXITY_ASK_URL, ClientCore
from perplexity.types import AskResult, Source

logger = logging.getLogger(__name__)

# API version observed in captured traffic
_API_VERSION = "2.18"

# Minimal set of supported block types for the API response
_SUPPORTED_BLOCKS = [
    "answer_modes",
    "media_items",
    "knowledge_cards",
    "search_result_widgets",
    "inline_images",
    "inline_assets",
    "pending_followups",
]


def _detect_timezone() -> str:
    """Detect the local timezone name for the API request.

    Returns:
        IANA timezone string, or UTC as fallback.
    """
    try:
        now = datetime.now(timezone.utc).astimezone()
        tz_name = now.tzinfo.tzname(now) if now.tzinfo else None
        # tzname() may return abbreviations like "CET"; the API expects IANA names
        # For now, fall back to UTC if we can't determine the IANA name
        return tz_name if tz_name and "/" in tz_name else "UTC"
    except Exception:
        return "UTC"


def _build_ask_payload(
    question: str,
    model: str,
    mode: str,
    search_focus: str,
    language: str,
) -> dict[str, Any]:
    """Build the JSON payload for the perplexity_ask endpoint.

    Args:
        question: The user's question text.
        model: Model preference (e.g. "pplx_pro").
        mode: Chat mode (e.g. "copilot" for Pro).
        search_focus: Search focus (e.g. "internet").
        language: Language code (e.g. "en-US").

    Returns:
        Complete JSON payload dict ready for POST.
    """
    frontend_uuid = str(uuid.uuid4())
    context_uuid = str(uuid.uuid4())

    return {
        "query_str": question,
        "params": {
            "dsl_query": question,
            "attachments": [],
            "language": language,
            "timezone": _detect_timezone(),
            "search_focus": search_focus,
            "sources": ["web"],
            "frontend_uuid": frontend_uuid,
            "mode": mode,
            "model_preference": model,
            "is_related_query": False,
            "is_sponsored": False,
            "frontend_context_uuid": context_uuid,
            "prompt_source": "user",
            "query_source": "home",
            "is_incognito": False,
            "use_schematized_api": True,
            "send_back_text_in_streaming_api": False,
            "supported_block_use_cases": _SUPPORTED_BLOCKS,
            "client_coordinates": None,
            "mentions": [],
            "skip_search_enabled": True,
            "source": "default",
            "version": _API_VERSION,
        },
    }


def _extract_answer_text(block: dict[str, Any], chunks: list[str]) -> list[str]:
    """Extract answer text from an ask_text_0_markdown block.

    Handles both direct markdown_block format (from direct API calls)
    and diff_block patch format (from browser-like calls).

    Args:
        block: A block dict from the SSE event.
        chunks: Current accumulated text chunks (mutated in place).

    Returns:
        Updated chunks list.
    """
    # Direct block format (when use_schematized_api=True with minimal block types)
    mb = block.get("markdown_block")
    if mb:
        answer = mb.get("answer")
        if answer:
            return [answer]
        block_chunks = mb.get("chunks")
        if block_chunks:
            return list(block_chunks)

    # Diff/patch format (when supported_block_use_cases includes more types)
    diff = block.get("diff_block")
    if diff:
        for patch in diff.get("patches", []):
            val = patch.get("value", "")
            if isinstance(val, dict):
                # Initial replace with chunks array
                patch_chunks = val.get("chunks")
                if patch_chunks:
                    return list(patch_chunks)
                patch_answer = val.get("answer")
                if patch_answer:
                    return [patch_answer]
            elif isinstance(val, str):
                # Incremental chunk append
                chunks.append(val)

    return chunks


def _extract_sources(block: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract web sources from a web_results block.

    Args:
        block: A block dict from the SSE event.

    Returns:
        List of raw web result dicts, or empty list if none found.
    """
    # Direct block format
    wb = block.get("web_result_block")
    if wb:
        results = wb.get("web_results")
        if results:
            return results

    # Diff/patch format
    diff = block.get("diff_block")
    if diff:
        for patch in diff.get("patches", []):
            val = patch.get("value")
            if isinstance(val, dict):
                results = val.get("web_results")
                if results:
                    return results

    return []


class ChatAPI:
    """Chat interface for Perplexity's ask endpoint.

    Provides methods to send questions and receive answers with
    source citations.

    Attributes:
        _core: The underlying HTTP client core.
    """

    def __init__(self, core: ClientCore):
        """Initialize the Chat API.

        Args:
            core: ClientCore instance for making HTTP requests.
        """
        self._core = core

    async def ask(
        self,
        question: str,
        model: str = "pplx_pro",
        mode: str = "copilot",
        search_focus: str = "internet",
        language: str = "en-US",
    ) -> AskResult:
        """Send a question and return the complete answer with sources.

        Streams the SSE response and collects all chunks into a final
        AskResult. Blocks until the full response is received.

        Args:
            question: The question to ask.
            model: Model preference. Defaults to "pplx_pro".
            mode: Chat mode. "copilot" for Pro search. Defaults to "copilot".
            search_focus: Search scope. Defaults to "internet".
            language: Response language code. Defaults to "en-US".

        Returns:
            AskResult with answer text, sources, and metadata.
        """
        payload = _build_ask_payload(question, model, mode, search_focus, language)

        chunks: list[str] = []
        raw_sources: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}

        async for evt in self._core.sse_request(PERPLEXITY_ASK_URL, payload):
            for block in evt.get("blocks", []):
                usage = block.get("intended_usage", "")

                if usage == "ask_text_0_markdown":
                    chunks = _extract_answer_text(block, chunks)

                elif usage == "web_results":
                    found = _extract_sources(block)
                    if found:
                        raw_sources = found

            # Capture read_write_token from any event (appears early in the stream)
            if evt.get("read_write_token") and "read_write_token" not in metadata:
                metadata["read_write_token"] = evt["read_write_token"]

            # Capture remaining metadata from the final event
            if evt.get("final_sse_message"):
                metadata.update({
                    "backend_uuid": evt.get("backend_uuid"),
                    "context_uuid": evt.get("context_uuid"),
                    "thread_url_slug": evt.get("thread_url_slug"),
                    "model": evt.get("display_model"),
                })

        sources = [
            Source(
                name=s.get("name", ""),
                url=s.get("url", ""),
                snippet=s.get("snippet", ""),
            )
            for s in raw_sources
        ]

        return AskResult(
            answer="".join(chunks),
            sources=sources,
            **metadata,
        )

    async def research(
        self,
        question: str,
        mode: str = "copilot",
        search_focus: str = "internet",
        language: str = "en-US",
    ) -> AskResult:
        """Run a deep research query.

        Uses the pplx_alpha model which triggers Perplexity's deep research
        mode. This takes significantly longer (1-3 minutes) but produces
        more thorough, multi-step research with extensive source analysis.

        Args:
            question: The research topic or question.
            mode: Chat mode. Defaults to "copilot".
            search_focus: Search scope. Defaults to "internet".
            language: Response language code. Defaults to "en-US".

        Returns:
            AskResult with the full research report and sources.
        """
        return await self.ask(
            question,
            model="pplx_alpha",
            mode=mode,
            search_focus=search_focus,
            language=language,
        )

    async def ask_followup(
        self,
        question: str,
        previous: AskResult,
        model: str = "pplx_pro",
        mode: str = "copilot",
        search_focus: str = "internet",
        language: str = "en-US",
    ) -> AskResult:
        """Send a follow-up question in an existing conversation thread.

        Continues the thread from a previous AskResult by passing the
        backend_uuid and read_write_token from that response.

        Args:
            question: The follow-up question.
            previous: AskResult from the previous message in the thread.
            model: Model preference.
            mode: Chat mode.
            search_focus: Search scope.
            language: Response language code.

        Returns:
            AskResult with the follow-up answer and updated metadata.

        Raises:
            ChatError: If previous result lacks required follow-up tokens.
        """
        from perplexity.exceptions import ChatError

        if not previous.backend_uuid or not previous.read_write_token:
            raise ChatError(
                "Cannot send follow-up: previous result is missing "
                "backend_uuid or read_write_token."
            )

        # Build base payload then override follow-up specific fields
        payload = _build_ask_payload(question, model, mode, search_focus, language)

        # Follow-up modifications (discovered via traffic capture)
        payload["params"]["query_source"] = "followup"
        payload["params"]["last_backend_uuid"] = previous.backend_uuid
        payload["params"]["read_write_token"] = previous.read_write_token
        payload["params"]["followup_source"] = "link"
        # These fields are null/omitted for follow-ups
        payload["params"]["frontend_context_uuid"] = None
        payload["params"]["dsl_query"] = None

        chunks: list[str] = []
        raw_sources: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}

        async for evt in self._core.sse_request(PERPLEXITY_ASK_URL, payload):
            for block in evt.get("blocks", []):
                usage = block.get("intended_usage", "")
                if usage == "ask_text_0_markdown":
                    chunks = _extract_answer_text(block, chunks)
                elif usage == "web_results":
                    found = _extract_sources(block)
                    if found:
                        raw_sources = found

            if evt.get("read_write_token") and "read_write_token" not in metadata:
                metadata["read_write_token"] = evt["read_write_token"]

            if evt.get("final_sse_message"):
                metadata.update({
                    "backend_uuid": evt.get("backend_uuid"),
                    "context_uuid": evt.get("context_uuid"),
                    "thread_url_slug": evt.get("thread_url_slug"),
                    "model": evt.get("display_model"),
                })

        sources = [
            Source(name=s.get("name", ""), url=s.get("url", ""), snippet=s.get("snippet", ""))
            for s in raw_sources
        ]

        return AskResult(answer="".join(chunks), sources=sources, **metadata)

    async def ask_stream(
        self,
        question: str,
        model: str = "pplx_pro",
        mode: str = "copilot",
        search_focus: str = "internet",
        language: str = "en-US",
    ) -> AsyncIterator[str]:
        """Stream answer text chunks as they arrive.

        Yields individual text chunks for live terminal rendering.
        Sources and metadata are not returned; use ask() if you need them.

        Args:
            question: The question to ask.
            model: Model preference.
            mode: Chat mode.
            search_focus: Search scope.
            language: Response language code.

        Yields:
            Text chunks as they are received from the SSE stream.
        """
        payload = _build_ask_payload(question, model, mode, search_focus, language)
        prev_len = 0

        async for evt in self._core.sse_request(PERPLEXITY_ASK_URL, payload):
            for block in evt.get("blocks", []):
                if block.get("intended_usage") != "ask_text_0_markdown":
                    continue

                # Direct format: yield new chunks
                mb = block.get("markdown_block")
                if mb:
                    new_chunks = mb.get("chunks", [])
                    for chunk in new_chunks[prev_len:]:
                        yield chunk
                    prev_len = len(new_chunks)
                    continue

                # Diff format: yield patch values that are strings (appended chunks)
                diff = block.get("diff_block")
                if diff:
                    for patch in diff.get("patches", []):
                        val = patch.get("value")
                        if isinstance(val, str):
                            yield val
                        elif isinstance(val, dict):
                            for chunk in val.get("chunks", []):
                                yield chunk
