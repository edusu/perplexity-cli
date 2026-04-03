#!/usr/bin/env python3
"""Capture the full SSE response from Perplexity chat endpoint.

Uses CDP (Chrome DevTools Protocol) to passively monitor network traffic
without intercepting/blocking the SSE stream. The page works normally
while we capture data chunks as they arrive.

Usage:
    uv run --with playwright recon/capture_chat_sse.py
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
SSE_OUTPUT_PATH = SCRIPT_DIR / "captured_sse_response.json"


def main() -> None:
    """Capture SSE chat response via CDP passive monitoring."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed.")
        sys.exit(1)

    if not BROWSER_PROFILE_DIR.exists():
        print("ERROR: No browser profile. Run login_and_capture.py first.")
        sys.exit(1)

    SIGNAL_FILE.unlink(missing_ok=True)

    # Track requests and their accumulated response bodies by CDP request ID
    tracked_requests: dict[str, dict] = {}

    print("=" * 60)
    print("  Perplexity.ai — Full SSE Chat Capture (CDP)")
    print("=" * 60)
    print()

    with sync_playwright() as p:
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

        # Open CDP session for passive network monitoring
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")

        def on_request_will_be_sent(params: dict) -> None:
            """Track requests to the perplexity_ask endpoint."""
            url = params.get("request", {}).get("url", "")
            if "perplexity_ask" not in url:
                return

            req_id = params.get("requestId", "")
            request = params.get("request", {})

            print(f"  [REQ] {request.get('method')} {url[:100]}")

            # Parse POST body
            post_data = request.get("postData", "")
            try:
                post_json = json.loads(post_data) if post_data else None
            except (json.JSONDecodeError, TypeError):
                post_json = post_data

            tracked_requests[req_id] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "method": request.get("method"),
                "request_headers": request.get("headers", {}),
                "post_data": post_json,
                "response_status": None,
                "response_headers": None,
                "response_chunks": [],
                "response_body": "",
            }

        def on_response_received(params: dict) -> None:
            """Capture response headers when they arrive."""
            req_id = params.get("requestId", "")
            if req_id not in tracked_requests:
                return

            response = params.get("response", {})
            tracked_requests[req_id]["response_status"] = response.get("status")
            tracked_requests[req_id]["response_headers"] = response.get("headers", {})
            content_type = response.get("headers", {}).get("content-type", "")
            print(f"  [RES] Status {response.get('status')} Content-Type: {content_type}")

        def on_data_received(params: dict) -> None:
            """Accumulate response body chunks as they stream in."""
            req_id = params.get("requestId", "")
            if req_id not in tracked_requests:
                return

            data_length = params.get("dataLength", 0)
            tracked_requests[req_id]["response_chunks"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data_length": data_length,
            })

        def on_loading_finished(params: dict) -> None:
            """Fetch the complete response body when the stream ends."""
            req_id = params.get("requestId", "")
            if req_id not in tracked_requests:
                return

            n_chunks = len(tracked_requests[req_id]["response_chunks"])
            print(f"  [DONE] Stream finished. {n_chunks} chunks received.")

            # Now fetch the full accumulated body via CDP
            try:
                result = cdp.send("Network.getResponseBody", {
                    "requestId": req_id,
                })
                body = result.get("body", "")
                is_base64 = result.get("base64Encoded", False)
                if is_base64:
                    body = base64.b64decode(body).decode("utf-8", errors="replace")

                tracked_requests[req_id]["response_body"] = body
                tracked_requests[req_id]["response_body_size"] = len(body)
                print(f"  [BODY] Captured {len(body)} chars of SSE response")
            except Exception as e:
                print(f"  [ERR] Could not get response body: {e}")
                tracked_requests[req_id]["response_body"] = f"<error: {e}>"

        # Register CDP event handlers
        cdp.on("Network.requestWillBeSent", on_request_will_be_sent)
        cdp.on("Network.responseReceived", on_response_received)
        cdp.on("Network.dataReceived", on_data_received)
        cdp.on("Network.loadingFinished", on_loading_finished)

        print(f"Navigating to {PERPLEXITY_URL} ...")
        page.goto(PERPLEXITY_URL, wait_until="domcontentloaded")

        print()
        print("CDP passive monitoring is ACTIVE (no blocking!)")
        print("The page works normally while we capture traffic.")
        print()
        print("Instructions:")
        print("  1. Ask ONE question in the chat")
        print("  2. Wait for the FULL response to finish")
        print("  3. Tell Claude you're done")
        print()
        print("Waiting for signal file: recon/.save_signal")
        print("-" * 60)

        try:
            while not SIGNAL_FILE.exists():
                # Use Playwright's wait instead of time.sleep so CDP events
                # get processed during the wait loop
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            pass

        print()
        print("Signal received!")

        # Yield to Playwright event loop to flush pending CDP events
        page.wait_for_timeout(3000)

        # Fetch response bodies BEFORE closing CDP session
        for req_id, entry in tracked_requests.items():
            if entry.get("response_body"):
                continue  # Already captured
            try:
                result = cdp.send("Network.getResponseBody", {
                    "requestId": req_id,
                })
                body = result.get("body", "")
                is_b64 = result.get("base64Encoded", False)
                if is_b64:
                    body = base64.b64decode(body).decode("utf-8", errors="replace")
                entry["response_body"] = body
                entry["response_body_size"] = len(body)
                print(f"  [BODY] Captured {len(body)} chars for {entry['url'][:80]}")
            except Exception as e:
                print(f"  [ERR] Could not get body for {req_id}: {e}")

        print("Closing browser...")
        cdp.detach()
        context.close()

    SIGNAL_FILE.unlink(missing_ok=True)

    if not tracked_requests:
        print("WARNING: No chat requests captured. Did you ask a question?")
        return

    # Convert to list and save
    captures = list(tracked_requests.values())
    SSE_OUTPUT_PATH.write_text(
        json.dumps(captures, indent=2, ensure_ascii=False)
    )
    print(f"Saved {len(captures)} capture(s) to: {SSE_OUTPUT_PATH}")
    print()

    # Analyze and summarize each capture
    for idx, capture in enumerate(captures):
        body = capture.get("response_body", "")
        query = "?"
        pd = capture.get("post_data")
        if isinstance(pd, dict):
            query = pd.get("query_str", "?")

        print(f"=== Capture {idx} ({len(body)} chars) ===")
        print(f"  Query: {query[:100]}")
        print(f"  Chunks received: {len(capture.get('response_chunks', []))}")
        print()

        # Parse SSE events
        events = []
        for line in body.split("\n"):
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        print(f"  Total SSE events parsed: {len(events)}")

        if events:
            last = events[-1]
            print(f"  Last event status: {last.get('status')}")
            print(f"  Last event text_completed: {last.get('text_completed')}")
            print(f"  Last event final_sse_message: {last.get('final_sse_message')}")

            # Show block types in last event
            blocks = last.get("blocks", [])
            usages = [b.get("intended_usage", "?") for b in blocks]
            print(f"  Last event block types: {usages}")
        print()


if __name__ == "__main__":
    main()
