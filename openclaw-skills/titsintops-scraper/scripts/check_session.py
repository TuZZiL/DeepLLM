#!/usr/bin/env python3
"""Validate that saved Playwright cookies still unlock an authenticated page.

Use this after login.py and before search/inspect/download commands.
"""
import argparse

from titsintops_toolkit import BASE_URL, add_common_args, classify_response, make_http_client, normalize_url, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether saved session can access a URL.")
    parser.add_argument("url", nargs="?", default=BASE_URL, help="URL to check")
    add_common_args(parser)
    args = parser.parse_args()
    target = normalize_url(args.url, BASE_URL)
    with make_http_client(args.storage_state) as client:
        response = client.get(target, headers={"Referer": BASE_URL + "/"})
        ok, status = classify_response(response)
        payload = {"ok": ok, "status": status, "requested_url": target, "final_url": str(response.url), "http_status": response.status_code}
    print_json(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
