"""Tests for the --finance search_focus override on ask."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from perplexity._chat import _build_ask_payload
from perplexity.cli import cli
from perplexity.types import AskResult


def test_build_payload_default_search_focus() -> None:
    payload = _build_ask_payload("hi", "pplx_pro", "copilot", "internet", "en-US")
    assert payload["params"]["search_focus"] == "internet"


def test_build_payload_finance_focus_passthrough() -> None:
    payload = _build_ask_payload("oil today", "pplx_pro", "copilot", "finance", "en-US")
    assert payload["params"]["search_focus"] == "finance"


def test_ask_cli_finance_flag_routes_to_chat_with_finance_focus() -> None:
    """`perplexity ask --finance "q"` must call chat.ask with search_focus="finance"."""
    runner = CliRunner()
    fake_client = MagicMock()
    fake_client.chat = MagicMock()
    fake_client.chat.ask = AsyncMock(return_value=AskResult(answer="ok", sources=[]))

    @asynccontextmanager
    async def _ctx(_storage):
        yield fake_client

    with patch("perplexity.cli.chat.authenticated_client", _ctx):
        result = runner.invoke(cli, ["ask", "--finance", "--raw", "oil?"])
    assert result.exit_code == 0, result.output
    call = fake_client.chat.ask.await_args
    assert call.kwargs.get("search_focus") == "finance"
