#!/usr/bin/env python3
"""
Manual API health check — run after daily quota resets to verify the full
OpenStates integration end-to-end.

Requires the server to be running:
    uvicorn main:app --reload

Usage:
    source .venv/bin/activate && python scripts/check_api.py
"""

import sys
import httpx

BASE_URL = "http://127.0.0.1:8000"


def main() -> int:
    print(f"Connecting to {BASE_URL} ...")

    try:
        res = httpx.post(f"{BASE_URL}/api/fetch", timeout=30.0)
    except httpx.ConnectError:
        print("ERROR: Could not connect. Is the server running?")
        print("  Start it with: uvicorn main:app --reload")
        return 1

    if res.status_code == 429:
        print(f"RATE LIMITED: {res.json().get('detail', 'quota exceeded')}")
        print("Try again tomorrow after quota resets.")
        return 1

    if res.status_code >= 400:
        print(f"ERROR {res.status_code}: {res.json().get('detail', res.text)}")
        return 1

    data = res.json()
    print(f"OK — {data['updated']} bills updated, {data['new_actions']} new actions")

    if data.get("errors"):
        print(f"  {len(data['errors'])} bill(s) failed:")
        for err in data["errors"]:
            print(f"    {err['bill_id']}: {err['error']}")

    if data.get("skipped"):
        print(f"  Note: {data['skipped']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
