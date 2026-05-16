#!/usr/bin/env python3
"""CLI wrapper for thread inspection without downloads.

Agents should prefer this command before scrape_thread.py because it returns a
reviewable JSON list of candidate media URLs.
"""
import argparse

from titsintops_toolkit import add_common_args, inspect_thread, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect bounded thread pages and extract media candidates without downloading.")
    parser.add_argument("url", help="Thread URL")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum thread pages to inspect")
    add_common_args(parser)
    args = parser.parse_args()
    inspection = inspect_thread(args.url, max_pages=args.max_pages, storage_state=args.storage_state, allow_external=args.allow_external, require_auth=args.require_auth)
    print_json(inspection.to_jsonable())
    return 0 if inspection.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
