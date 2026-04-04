"""Authentication handling for Perplexity CLI.

Extracts and manages browser cookies from Playwright's storage state
for authenticating API requests to Perplexity.ai.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from perplexity.exceptions import AuthenticationError
from perplexity.paths import get_storage_path

logger = logging.getLogger(__name__)

# Domains from which we accept cookies for Perplexity auth
ALLOWED_COOKIE_DOMAINS = frozenset(
    {
        ".perplexity.ai",
        "www.perplexity.ai",
        "perplexity-ai.cloudflareaccess.com",
        "pplx-next-static-public.perplexity.ai",
        ".count.perplexity.ai",
    }
)

# At least one of these cookies must be present for auth to work
REQUIRED_COOKIE_NAMES = frozenset(
    {
        "__Secure-next-auth.session-token",
        "cf_clearance",
    }
)


def _is_allowed_domain(domain: str) -> bool:
    """Check if a cookie domain is relevant for Perplexity auth.

    Args:
        domain: Cookie domain string from Playwright storage state.

    Returns:
        True if the domain should be included in auth cookies.
    """
    if domain in ALLOWED_COOKIE_DOMAINS:
        return True
    # Accept exact match or any subdomain of perplexity.ai
    # Using ".perplexity.ai" suffix to avoid matching e.g. "evilperplexity.ai"
    return domain == "perplexity.ai" or domain.endswith(".perplexity.ai")


def extract_cookies_from_storage(storage_state: dict[str, Any]) -> dict[str, str]:
    """Extract Perplexity cookies from Playwright storage state.

    Filters cookies to include only those from perplexity.ai and related
    subdomains needed for API authentication.

    Args:
        storage_state: Parsed JSON from Playwright's storage state file.

    Returns:
        Dict mapping cookie names to their values.

    Raises:
        AuthenticationError: If no relevant cookies are found.
    """
    cookies: dict[str, str] = {}

    for cookie in storage_state.get("cookies", []):
        domain = cookie.get("domain", "")
        name = cookie.get("name")
        if not name or not _is_allowed_domain(domain):
            continue
        cookies[name] = cookie.get("value", "")

    if not cookies:
        raise AuthenticationError(
            "No Perplexity cookies found in storage state. Run 'perplexity login' first."
        )

    # Check for at least one critical cookie
    found_required = REQUIRED_COOKIE_NAMES & set(cookies.keys())
    if not found_required:
        raise AuthenticationError(
            f"Missing required cookies. Expected at least one of: "
            f"{', '.join(sorted(REQUIRED_COOKIE_NAMES))}. "
            f"Run 'perplexity login' to re-authenticate."
        )

    logger.debug("Extracted %d cookies from storage state", len(cookies))
    return cookies


def load_storage_state(path: Path | None = None) -> dict[str, Any]:
    """Load Playwright storage state from file or environment variable.

    Precedence:
        1. Explicit path parameter
        2. PERPLEXITY_AUTH_JSON environment variable (inline JSON)
        3. Default path (~/.perplexity/storage_state.json)

    Args:
        path: Optional explicit path to storage_state.json.

    Returns:
        Parsed storage state dict.

    Raises:
        AuthenticationError: If no storage state is found.
    """
    # 1. Explicit path
    if path is not None:
        resolved = Path(path)
        if not resolved.exists():
            raise AuthenticationError(f"Storage state file not found: {resolved}")
        return json.loads(resolved.read_text())

    # 2. Environment variable (inline JSON for CI/CD)
    env_json = os.environ.get("PERPLEXITY_AUTH_JSON")
    if env_json:
        try:
            return json.loads(env_json)
        except json.JSONDecodeError as e:
            raise AuthenticationError(f"Invalid JSON in PERPLEXITY_AUTH_JSON: {e}") from e

    # 3. Default path
    default_path = get_storage_path()
    if not default_path.exists():
        raise AuthenticationError("Not logged in. Run 'perplexity login' to authenticate.")
    return json.loads(default_path.read_text())


@dataclass
class AuthTokens:
    """Authentication tokens extracted from browser session.

    Attributes:
        cookies: Dict mapping cookie names to their values.
    """

    cookies: dict[str, str]

    @property
    def cookie_header(self) -> str:
        """Format cookies as an HTTP Cookie header value."""
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    @classmethod
    def from_storage(cls, path: Path | None = None) -> AuthTokens:
        """Create AuthTokens from a Playwright storage state file.

        This is the recommended way to create AuthTokens. Loads cookies
        from the storage state and validates them.

        Args:
            path: Optional explicit path to storage_state.json.

        Returns:
            AuthTokens with extracted cookies.

        Raises:
            AuthenticationError: If storage state is missing or invalid.
        """
        storage_state = load_storage_state(path)
        cookies = extract_cookies_from_storage(storage_state)
        return cls(cookies=cookies)
