"""CLI commands for authentication and session management."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from perplexity._core import PERPLEXITY_BASE_URL
from perplexity.cli.helpers import console, get_storage_from_ctx, require_auth
from perplexity.paths import get_browser_profile_dir, get_storage_path

PERPLEXITY_URL = f"{PERPLEXITY_BASE_URL}/"


@click.command()
def login() -> None:
    """Log in to Perplexity.ai via browser.

    Opens a Chromium browser window where you can solve the Cloudflare
    CAPTCHA and log in to your Perplexity account. Cookies are saved
    for CLI use after you press ENTER.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        console.print(
            "[red]Playwright is required for login.[/red]\n"
            "Install it with: [bold]pip install 'perplexity-cli[browser]'[/bold]\n"
            "Then run: [bold]playwright install chromium[/bold]"
        )
        raise SystemExit(1)

    storage_path = get_storage_path()
    browser_profile = get_browser_profile_dir()

    console.print()
    console.print("[bold]Perplexity.ai — Login[/bold]")
    console.print(f"[dim]Storage: {storage_path}[/dim]")
    console.print(f"[dim]Profile: {browser_profile}[/dim]")
    console.print()

    with sync_playwright() as p:
        # Anti-detection flags (same as notebooklm-py)
        launch_kwargs = {
            "user_data_dir": str(browser_profile),
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--password-store=basic",
            ],
            "ignore_default_args": ["--enable-automation"],
        }

        try:
            context = p.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            if "executable doesn't exist" in str(e).lower():
                console.print(
                    "[red]Chromium not found.[/red]\n"
                    "Install it with: [bold]playwright install chromium[/bold]"
                )
                raise SystemExit(1) from None
            raise

        page = context.pages[0] if context.pages else context.new_page()

        console.print("[yellow]Opening Chromium for Perplexity login...[/yellow]")
        page.goto(PERPLEXITY_URL, wait_until="domcontentloaded")

        console.print()
        console.print("[bold green]Instructions:[/bold green]")
        console.print("  1. Solve the Cloudflare CAPTCHA if it appears")
        console.print("  2. Log in to your Perplexity account")
        console.print("  3. Wait until the Perplexity homepage loads")
        console.print("  4. Press [bold]ENTER[/bold] here to save and close")
        console.print()

        try:
            input("[Press ENTER when logged in] ")
        except EOFError:
            # Non-interactive shell — wait for signal file instead
            import time

            signal_file = get_storage_path().parent / ".save_signal"
            signal_file.unlink(missing_ok=True)
            console.print(
                "[dim]Non-interactive mode: create ~/.perplexity/.save_signal to save[/dim]"
            )
            try:
                while not signal_file.exists():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            signal_file.unlink(missing_ok=True)

        # Navigate once more to ensure all Set-Cookie headers are captured
        try:
            page.goto(PERPLEXITY_URL, wait_until="commit")
        except Exception:
            pass

        # Save storage state with cookies
        context.storage_state(path=str(storage_path))

        # Restrict file permissions (sensitive auth data)
        if sys.platform != "win32":
            storage_path.chmod(0o600)

        context.close()

    console.print()
    console.print("[bold green]Login successful![/bold green]")
    console.print(f"Cookies saved to: {storage_path}")
    console.print()
    _print_cookie_summary(storage_path)


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current authentication status."""
    auth = require_auth(get_storage_from_ctx(ctx))
    n_cookies = len(auth.cookies)
    console.print(f"[green]Logged in[/green] — {n_cookies} cookies loaded")
    console.print()
    # Show key cookie names (not values)
    key_cookies = [
        "__Secure-next-auth.session-token",
        "cf_clearance",
        "pplx.session-id",
    ]
    for name in key_cookies:
        if name in auth.cookies:
            console.print(f"  [green]✓[/green] {name}")
        else:
            console.print(f"  [dim]✗ {name}[/dim]")


def _print_cookie_summary(storage_path: Path) -> None:
    """Print a summary of captured cookies grouped by domain.

    Args:
        storage_path: Path to the Playwright storage state JSON file.
    """
    with open(storage_path) as f:
        state = json.load(f)

    cookies = state.get("cookies", [])
    domains: dict[str, list[str]] = {}
    for c in cookies:
        domain = c.get("domain", "unknown")
        if "perplexity" in domain:
            domains.setdefault(domain, []).append(c.get("name", "?"))

    for domain, names in sorted(domains.items()):
        console.print(f"  [dim]{domain}[/dim] ({len(names)} cookies)")
