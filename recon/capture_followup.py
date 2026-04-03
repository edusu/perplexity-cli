#!/usr/bin/env python3
"""Capture network traffic for a follow-up conversation in Perplexity.

Opens browser, user asks two questions in the SAME thread, and we capture
both requests to see what params change for the follow-up.

Usage:
    uv run --with playwright recon/capture_followup.py
"""

import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PERPLEXITY_URL = "https://www.perplexity.ai/"
SCRIPT_DIR = Path(__file__).parent.resolve()
BROWSER_PROFILE_DIR = SCRIPT_DIR / "browser_profile"
SIGNAL_FILE = SCRIPT_DIR / ".save_signal"
OUTPUT_PATH = SCRIPT_DIR / "captured_followup.json"


def main() -> None:
    """Capture follow-up conversation traffic via CDP."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed.")
        sys.exit(1)

    SIGNAL_FILE.unlink(missing_ok=True)

    tracked: dict[str, dict] = {}

    print("=" * 60)
    print("  Perplexity.ai — Follow-up Conversation Capture")
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
            if "perplexity_ask" not in url:
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
                "post_data": post_json,
                "response_body": "",
            }
            q = post_json.get("query_str", "?") if isinstance(post_json, dict) else "?"
            n = len(tracked)
            print(f"  [REQ {n}] {q[:80]}")

        def on_response(params: dict) -> None:
            req_id = params.get("requestId", "")
            if req_id in tracked:
                tracked[req_id]["response_status"] = params.get("response", {}).get("status")

        def on_done(params: dict) -> None:
            req_id = params.get("requestId", "")
            if req_id not in tracked:
                return
            print(f"  [DONE] Stream finished for request {req_id[:12]}...")

        cdp.on("Network.requestWillBeSent", on_request)
        cdp.on("Network.responseReceived", on_response)
        cdp.on("Network.loadingFinished", on_done)

        print(f"Navigating to {PERPLEXITY_URL} ...")
        page.goto(PERPLEXITY_URL, wait_until="domcontentloaded")

        print()
        print("Instructions:")
        print("  1. Ask a question (e.g. 'What is the tallest building?')")
        print("  2. Wait for the answer to complete")
        print("  3. Ask a FOLLOW-UP in the same thread (e.g. 'How tall is it?')")
        print("  4. Wait for the second answer to complete")
        print("  5. Tell Claude you're done")
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

        # Fetch response bodies
        for req_id, entry in tracked.items():
            try:
                result = cdp.send("Network.getResponseBody", {"requestId": req_id})
                body = result.get("body", "")
                if result.get("base64Encoded"):
                    body = base64.b64decode(body).decode("utf-8", errors="replace")
                entry["response_body"] = body
                print(f"  [BODY] {len(body)} chars")
            except Exception as e:
                print(f"  [ERR] {e}")

        cdp.detach()
        context.close()

    SIGNAL_FILE.unlink(missing_ok=True)

    captures = list(tracked.values())
    OUTPUT_PATH.write_text(json.dumps(captures, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(captures)} requests to: {OUTPUT_PATH}")

    # Compare the two requests
    if len(captures) >= 2:
        print("\n=== DIFF: Request 1 vs Request 2 ===")
        p1 = captures[0].get("post_data", {}).get("params", {})
        p2 = captures[1].get("post_data", {}).get("params", {})
        all_keys = sorted(set(list(p1.keys()) + list(p2.keys())))
        for k in all_keys:
            v1 = p1.get(k)
            v2 = p2.get(k)
            if v1 != v2:
                print(f"  {k}:")
                print(f"    Q1: {json.dumps(v1, ensure_ascii=False)[:150]}")
                print(f"    Q2: {json.dumps(v2, ensure_ascii=False)[:150]}")


if __name__ == "__main__":
    main()
