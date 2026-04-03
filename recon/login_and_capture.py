#!/usr/bin/env python3
"""Login to Perplexity.ai via browser and save session cookies.

Opens a real Chromium browser with a persistent profile so the user can:
1. Solve the Cloudflare Turnstile CAPTCHA
2. Log in to their Perplexity account
3. Close the browser tab/window to trigger cookie save

The cookies are saved to storage_state.json in the project recon/ directory.
A signal-file mode is also supported: create recon/.save_signal to trigger save.

Usage:
    uv run --with playwright recon/login_and_capture.py
"""

import json
import sys
import time
from pathlib import Path

PERPLEXITY_URL = "https://www.perplexity.ai/"
SCRIPT_DIR = Path(__file__).parent.resolve()
STORAGE_STATE_PATH = SCRIPT_DIR / "storage_state.json"
BROWSER_PROFILE_DIR = SCRIPT_DIR / "browser_profile"
SIGNAL_FILE = SCRIPT_DIR / ".save_signal"


def main() -> None:
    """Launch browser for Perplexity login and save session state."""
    # Lazy import so the script fails fast with a clear message if missing
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run:")
        print("  uv run --with playwright recon/login_and_capture.py")
        sys.exit(1)

    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    # Clean up any stale signal file from previous runs
    SIGNAL_FILE.unlink(missing_ok=True)

    print("=" * 60)
    print("  Perplexity.ai — Login & Cookie Capture")
    print("=" * 60)
    print()

    with sync_playwright() as p:
        # Launch persistent context (keeps cookies/profile across sessions)
        # Same anti-detection flags as notebooklm-py
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--password-store=basic",
            ],
            ignore_default_args=["--enable-automation"],
        )

        page = context.pages[0] if context.pages else context.new_page()

        print(f"Navigating to {PERPLEXITY_URL} ...")
        page.goto(PERPLEXITY_URL, wait_until="domcontentloaded")

        print()
        print("Instructions:")
        print("  1. Solve the Cloudflare CAPTCHA if it appears")
        print("  2. Log in to your Perplexity account")
        print("  3. Wait until the Perplexity homepage fully loads")
        print()
        print("Waiting for signal file: recon/.save_signal")
        print("  (Claude will create it when you say you're logged in)")
        print()

        # Poll for signal file instead of stdin (works in non-interactive shells)
        try:
            while not SIGNAL_FILE.exists():
                time.sleep(1)
        except KeyboardInterrupt:
            pass  # Ctrl+C also works to trigger save

        print("Signal received! Saving cookies...")

        # Navigate once more to ensure all cookies are set
        try:
            page.goto(PERPLEXITY_URL, wait_until="commit")
        except Exception:
            pass  # Navigation interrupts are OK

        # Save full browser storage state (cookies + localStorage)
        context.storage_state(path=str(STORAGE_STATE_PATH))

        # Restrict file permissions (sensitive auth data)
        if sys.platform != "win32":
            STORAGE_STATE_PATH.chmod(0o600)

        context.close()

    # Clean up signal file
    SIGNAL_FILE.unlink(missing_ok=True)

    # Print summary of what was captured
    print()
    print("=" * 60)
    print("  Cookies saved!")
    print("=" * 60)
    print(f"  File: {STORAGE_STATE_PATH}")
    print()

    _print_cookie_summary(STORAGE_STATE_PATH)


def _print_cookie_summary(path: Path) -> None:
    """Print a summary of captured cookies without exposing values."""
    with open(path) as f:
        state = json.load(f)

    cookies = state.get("cookies", [])
    print(f"  Total cookies: {len(cookies)}")
    print()

    # Group by domain
    domains: dict[str, list[str]] = {}
    for c in cookies:
        domain = c.get("domain", "unknown")
        name = c.get("name", "?")
        domains.setdefault(domain, []).append(name)

    for domain, names in sorted(domains.items()):
        print(f"  {domain} ({len(names)} cookies):")
        for name in sorted(names):
            print(f"    - {name}")
        print()


if __name__ == "__main__":
    main()
