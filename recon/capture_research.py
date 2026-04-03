#!/usr/bin/env python3
"""Capture network traffic for a Perplexity deep research session.

Opens browser with saved session, monitors ALL requests to perplexity.ai
REST endpoints via CDP, and saves the complete traffic for analysis.

Usage:
    uv run --with playwright recon/capture_research.py
"""

import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PERPLEXITY_URL = "https://www.perplexity.ai/"
SCRIPT_DIR = Path(__file__).parent.resolve()
BROWSER_PROFILE_DIR = SCRIPT_DIR / "browser_profile"
SIGNAL_FILE = SCRIPT_DIR / ".save_signal"
OUTPUT_PATH = SCRIPT_DIR / "captured_research.json"


def main() -> None:
    """Capture deep research traffic via CDP passive monitoring."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed.")
        sys.exit(1)

    SIGNAL_FILE.unlink(missing_ok=True)

    tracked: dict[str, dict] = {}

    print("=" * 60)
    print("  Perplexity.ai — Deep Research Traffic Capture")
    print("=" * 60)
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--password-store=basic"],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")

        def on_request(params: dict) -> None:
            url = params.get("request", {}).get("url", "")
            parsed = urlparse(url)
            # Track all REST API calls to perplexity.ai
            if "perplexity.ai" not in parsed.netloc:
                return
            if "/rest/" not in parsed.path and "/api/" not in parsed.path:
                return

            req_id = params.get("requestId", "")
            request = params.get("request", {})
            post_data = request.get("postData", "")
            try:
                post_json = json.loads(post_data) if post_data else None
            except (json.JSONDecodeError, TypeError):
                post_json = post_data

            tracked[req_id] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "method": request.get("method"),
                "post_data": post_json,
                "response_status": None,
                "response_headers": None,
                "response_body": "",
            }

            # Log interesting ones
            short_path = parsed.path
            method = request.get("method", "?")
            label = ""
            if "research" in url.lower() or "deep" in url.lower():
                label = " [RESEARCH]"
            elif "perplexity_ask" in url:
                label = " [ASK/SSE]"
            elif "sse" in url.lower():
                label = " [SSE]"
            print(f"  [{method}] {short_path[:80]}{label}")

        def on_response(params: dict) -> None:
            req_id = params.get("requestId", "")
            if req_id in tracked:
                resp = params.get("response", {})
                tracked[req_id]["response_status"] = resp.get("status")
                tracked[req_id]["response_headers"] = resp.get("headers", {})
                ct = resp.get("headers", {}).get("content-type", "")
                if "event-stream" in ct:
                    print(f"    ^ SSE stream detected")

        def on_done(params: dict) -> None:
            req_id = params.get("requestId", "")
            if req_id in tracked:
                url = tracked[req_id]["url"]
                short = urlparse(url).path
                print(f"  [DONE] {short[:60]}")

        cdp.on("Network.requestWillBeSent", on_request)
        cdp.on("Network.responseReceived", on_response)
        cdp.on("Network.loadingFinished", on_done)

        print(f"Navigating to {PERPLEXITY_URL} ...")
        page.goto(PERPLEXITY_URL, wait_until="domcontentloaded")

        print()
        print("Instructions:")
        print("  1. Start a DEEP RESEARCH query in Perplexity")
        print("     (Click 'Deep Research' or use the research toggle)")
        print("  2. Wait for the FULL research to complete")
        print("     (This may take 1-3 minutes)")
        print("  3. Tell Claude you're done")
        print()
        print("Waiting for signal: recon/.save_signal")
        print("-" * 60)

        try:
            while not SIGNAL_FILE.exists():
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            pass

        print()
        print("Signal received!")
        page.wait_for_timeout(3000)

        # Fetch response bodies for all tracked requests
        for req_id, entry in tracked.items():
            try:
                result = cdp.send("Network.getResponseBody", {"requestId": req_id})
                body = result.get("body", "")
                if result.get("base64Encoded"):
                    body = base64.b64decode(body).decode("utf-8", errors="replace")
                entry["response_body"] = body
                size = len(body)
                if size > 1000:
                    print(f"  [BODY] {size:,} chars — {entry['url'][:60]}")
            except Exception:
                pass

        cdp.detach()
        context.close()

    SIGNAL_FILE.unlink(missing_ok=True)

    captures = list(tracked.values())
    OUTPUT_PATH.write_text(json.dumps(captures, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(captures)} API requests to: {OUTPUT_PATH}")
    print()

    # Summary
    print("=" * 60)
    print("  CAPTURE SUMMARY")
    print("=" * 60)
    sse_reqs = [r for r in captures if "event-stream" in (r.get("response_headers") or {}).get("content-type", "")]
    post_reqs = [r for r in captures if r.get("method") == "POST"]
    research_reqs = [r for r in captures if "research" in r.get("url", "").lower()]

    print(f"  Total API requests: {len(captures)}")
    print(f"  SSE streams: {len(sse_reqs)}")
    print(f"  POST requests: {len(post_reqs)}")
    print(f"  Research-related: {len(research_reqs)}")
    print()

    # List unique endpoints
    endpoints = set()
    for r in captures:
        path = urlparse(r["url"]).path
        endpoints.add(f"{r.get('method', '?')} {path}")
    print("  Unique endpoints:")
    for ep in sorted(endpoints):
        print(f"    {ep}")


if __name__ == "__main__":
    main()
