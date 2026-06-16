#!/usr/bin/env python
"""Print tunnel setup reminder and verify APP_BASE_URL is reachable."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from services.config import settings


def main() -> None:
    base = settings.app_base_url.rstrip("/")
    print(f"APP_BASE_URL = {base}")

    if not base.startswith("https://"):
        print("ERROR: APP_BASE_URL must be https:// for Twilio")
        sys.exit(1)

    try:
        r = httpx.get(f"{base}/health", timeout=15.0, follow_redirects=True)
        r.raise_for_status()
        print(f"OK   Tunnel reachable: {r.json()}")
    except Exception as exc:
        print(f"FAIL Tunnel not reachable: {exc}")
        print()
        print("Fix:")
        print("  1. Run: npx cloudflared tunnel --url http://127.0.0.1:8888")
        print("  2. Copy the https://*.trycloudflare.com URL into .env.local APP_BASE_URL")
        print("  3. Restart the server")
        sys.exit(1)

    print()
    print("Place a test call:")
    print(f"  python scripts/outbound_call.py 918275566293 --base-url {base}")


if __name__ == "__main__":
    main()
