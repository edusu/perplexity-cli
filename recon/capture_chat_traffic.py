#!/usr/bin/env python3
"""Capture network traffic from Perplexity.ai chat interactions.

Opens a browser with saved cookies, intercepts all network requests,
and saves them when the user finishes chatting. Focuses on API calls
(XHR/Fetch) and WebSocket/SSE connections used for chat.

Usage:
    uv run --with playwright recon/capture_chat_traffic.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PERPLEXITY_URL = "https://www.perplexity.ai/"
SCRIPT_DIR = Path(__file__).parent.resolve()
STORAGE_STATE_PATH = SCRIPT_DIR / "storage_state.json"
BROWSER_PROFILE_DIR = SCRIPT_DIR / "browser_profile"
SIGNAL_FILE = SCRIPT_DIR / ".save_signal"
TRAFFIC_OUTPUT_PATH = SCRIPT_DIR / "captured_traffic.json"


def main() -> None:
    """Open browser with saved session and capture chat network traffic."""
    try:
        from playwright.sync_api import sync_playwright, Request, Response
    except ImportError:
        print("ERROR: playwright not installed.")
        sys.exit(1)

    if not STORAGE_STATE_PATH.exists() and not BROWSER_PROFILE_DIR.exists():
        print("ERROR: No saved session. Run login_and_capture.py first.")
        sys.exit(1)

    SIGNAL_FILE.unlink(missing_ok=True)

    # Traffic capture storage
    captured_requests: list[dict] = []
    captured_websockets: list[dict] = []

    def on_request(request: Request) -> None:
        """Capture outgoing request details."""
        url = request.url
        parsed = urlparse(url)

        # Skip static assets (images, fonts, css, js bundles)
        skip_extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                          ".woff", ".woff2", ".ttf", ".css"}
        if any(parsed.path.endswith(ext) for ext in skip_extensions):
            return

        # Skip Next.js static chunks unless they're data fetches
        if "/_next/static/" in url:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "method": request.method,
            "resource_type": request.resource_type,
            "headers": dict(request.headers),
            "post_data": None,
        }

        # Capture POST body
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                post_data = request.post_data
                if post_data:
                    # Try to parse as JSON for readability
                    try:
                        entry["post_data"] = json.loads(post_data)
                    except (json.JSONDecodeError, TypeError):
                        entry["post_data"] = post_data[:5000]
            except Exception:
                entry["post_data"] = "<could not read>"

        captured_requests.append(entry)

        # Log interesting requests in real-time
        if any(kw in url for kw in ["/api/", "/rest/", "/graphql", "/trpc",
                                     "query", "chat", "search", "ask"]):
            print(f"  [API] {request.method} {url[:120]}")
        elif request.resource_type in ("websocket", "eventsource"):
            print(f"  [WS/SSE] {url[:120]}")

    def on_response(response: Response) -> None:
        """Attach response data to the corresponding captured request."""
        url = response.url

        # Find the matching request entry
        for entry in reversed(captured_requests):
            if entry["url"] == url and "response_status" not in entry:
                entry["response_status"] = response.status
                entry["response_headers"] = dict(response.headers)

                content_type = response.headers.get("content-type", "")
                entry["response_content_type"] = content_type

                # Flag streaming responses
                if "text/event-stream" in content_type:
                    entry["is_sse"] = True
                    print(f"  [SSE STREAM] {url[:120]}")
                if "chunked" in response.headers.get("transfer-encoding", ""):
                    entry["is_chunked"] = True

                # Capture response body (truncated for large responses)
                try:
                    body = response.text()
                    entry["response_body"] = body[:10000]
                    if len(body) > 10000:
                        entry["response_body_truncated"] = True
                        entry["response_body_full_size"] = len(body)
                except Exception:
                    entry["response_body"] = "<could not read>"

                break

    def on_websocket(ws) -> None:
        """Capture WebSocket connections and their frames."""
        ws_entry = {
            "url": ws.url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frames_sent": [],
            "frames_received": [],
        }
        captured_websockets.append(ws_entry)
        print(f"  [WS OPEN] {ws.url[:120]}")

        def on_frame_sent(payload: str) -> None:
            """Record frames sent by the client."""
            ws_entry["frames_sent"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": payload[:10000] if isinstance(payload, str) else "<binary>",
            })
            print(f"  [WS SENT] {str(payload)[:200]}")

        def on_frame_received(payload: str) -> None:
            """Record frames received from the server."""
            ws_entry["frames_received"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": payload[:10000] if isinstance(payload, str) else "<binary>",
            })
            # Only log first 200 chars to avoid flooding
            print(f"  [WS RECV] {str(payload)[:200]}")

        def on_close() -> None:
            """Record when WebSocket closes."""
            ws_entry["closed_at"] = datetime.now(timezone.utc).isoformat()
            print(f"  [WS CLOSE] {ws.url[:80]}")

        ws.on("framesent", on_frame_sent)
        ws.on("framereceived", on_frame_received)
        ws.on("close", on_close)

    print("=" * 60)
    print("  Perplexity.ai — Chat Traffic Capture")
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

        # Attach network listeners BEFORE navigation
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("websocket", on_websocket)

        print(f"Navigating to {PERPLEXITY_URL} ...")
        print()
        page.goto(PERPLEXITY_URL, wait_until="domcontentloaded")

        print("Network capture is ACTIVE. Intercepting all traffic.")
        print()
        print("Instructions:")
        print("  1. If Cloudflare appears, solve it")
        print("  2. Ask ONE question in the Perplexity chat")
        print("  3. Wait for the full response to finish")
        print("  4. Tell Claude you're done — he'll create the signal file")
        print()
        print("Waiting for signal file: recon/.save_signal")
        print("-" * 60)
        print()

        try:
            while not SIGNAL_FILE.exists():
                time.sleep(1)
        except KeyboardInterrupt:
            pass

        print()
        print("Signal received! Saving captured traffic...")

        # Save cookies too (they may have been refreshed)
        context.storage_state(path=str(STORAGE_STATE_PATH))
        context.close()

    SIGNAL_FILE.unlink(missing_ok=True)

    # Build output
    output = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "total_requests": len(captured_requests),
        "total_websockets": len(captured_websockets),
        "requests": captured_requests,
        "websockets": captured_websockets,
    }

    TRAFFIC_OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Traffic saved to: {TRAFFIC_OUTPUT_PATH}")
    print()

    # Print analysis summary
    _print_summary(output)


def _print_summary(data: dict) -> None:
    """Print a structured summary of the captured traffic."""
    requests = data["requests"]
    websockets = data["websockets"]

    print("=" * 60)
    print("  CAPTURE SUMMARY")
    print("=" * 60)
    print(f"  Total HTTP requests: {len(requests)}")
    print(f"  Total WebSocket connections: {len(websockets)}")
    print()

    # API endpoints (the interesting ones)
    api_requests = [r for r in requests if any(
        kw in r["url"] for kw in ["/api/", "/rest/", "/graphql", "/trpc",
                                    "query", "chat", "search", "ask",
                                    "/_next/data/"]
    )]
    if api_requests:
        print(f"  API endpoints found ({len(api_requests)}):")
        for r in api_requests:
            status = r.get("response_status", "?")
            sse = " [SSE]" if r.get("is_sse") else ""
            print(f"    {r['method']} {status} {r['url'][:100]}{sse}")
        print()

    # SSE streams
    sse_requests = [r for r in requests if r.get("is_sse")]
    if sse_requests:
        print(f"  SSE streams found ({len(sse_requests)}):")
        for r in sse_requests:
            print(f"    {r['url'][:100]}")
        print()

    # WebSocket details
    if websockets:
        print(f"  WebSocket connections ({len(websockets)}):")
        for ws in websockets:
            sent = len(ws.get("frames_sent", []))
            recv = len(ws.get("frames_received", []))
            print(f"    {ws['url'][:100]}")
            print(f"      Frames sent: {sent}, received: {recv}")
        print()

    # POST requests (likely mutations/queries)
    post_requests = [r for r in requests if r["method"] == "POST"]
    if post_requests:
        print(f"  POST requests ({len(post_requests)}):")
        for r in post_requests:
            status = r.get("response_status", "?")
            has_body = "yes" if r.get("post_data") else "no"
            print(f"    {status} {r['url'][:100]} (body: {has_body})")
        print()

    # Unique domains
    domains = set()
    for r in requests:
        parsed = urlparse(r["url"])
        domains.add(parsed.netloc)
    print(f"  Unique domains ({len(domains)}):")
    for d in sorted(domains):
        count = sum(1 for r in requests if d in r["url"])
        print(f"    {d} ({count} requests)")
    print()


if __name__ == "__main__":
    main()
