#!/usr/bin/env python3
"""CLI wrapper for thread inspection without downloads.

Agents should prefer this command before scrape_thread.py because it returns a
reviewable JSON list of candidate media URLs.
"""
import argparse

from titsintops_toolkit import add_common_args, inspect_thread, print_json, resolve_full_size_media


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect bounded thread pages and extract media candidates without downloading.")
    parser.add_argument("url", help="Thread URL")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum thread pages to inspect")
    parser.add_argument("--resolve-full", action="store_true", help="Resolve preview images to full-size URLs without downloading")
    parser.add_argument("--full-method", choices=["static", "http", "browser", "auto"], default="static", help="Full-size resolver to use")
    parser.add_argument("--full-timeout-ms", type=int, default=8000, help="Per-image timeout for browser full-size resolver")
    add_common_args(parser)
    args = parser.parse_args()
    inspection = inspect_thread(args.url, max_pages=args.max_pages, storage_state=args.storage_state, allow_external=args.allow_external, require_auth=args.require_auth)
    if inspection.ok and args.resolve_full:
        inspection.resolution_report = resolve_full_size_media(
            inspection.media,
            method=args.full_method,
            storage_state=args.storage_state,
            require_auth=args.require_auth or args.full_method == "browser",
            allow_external=args.allow_external,
            timeout_ms=args.full_timeout_ms,
        )
    print_json(inspection.to_jsonable())
    return 0 if inspection.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
