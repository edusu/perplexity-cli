"""Tests for the exception hierarchy."""

from __future__ import annotations

from perplexity.exceptions import FinanceError, PerplexityError


def test_finance_error_is_perplexity_error() -> None:
    """FinanceError must inherit from PerplexityError for uniform handling."""
    assert issubclass(FinanceError, PerplexityError)


def test_finance_error_carries_message() -> None:
    exc = FinanceError("Unknown ticker: XYZ")
    assert str(exc) == "Unknown ticker: XYZ"
