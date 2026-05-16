#!/usr/bin/env python3
"""Check public or authenticated access to a page.

By default this uses direct public HTTP and optional cookies if storage_state.json
exists. Pass --require-auth only when testing an authenticated-only page.
"""
import argparse

from titsintops_toolkit import BASE_URL, add_common_args, classify_response, make_http_client, normalize_url, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether public or authenticated HTTP can access a URL.")
    parser.add_argument("url", nargs="?", default=BASE_URL, help="URL to check")
    add_common_args(parser)
    args = parser.parse_args()
    target = normalize_url(args.url, BASE_URL)
    with make_http_client(args.storage_state, require_auth=args.require_auth) as client:
        response = client.get(target, headers={"Referer": BASE_URL + "/"})
        ok, status = classify_response(response)
        payload = {"ok": ok, "auth_mode": "required" if args.require_auth else "public_or_cookie", "status": status, "requested_url": target, "final_url": str(response.url), "http_status": response.status_code}
    print_json(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
