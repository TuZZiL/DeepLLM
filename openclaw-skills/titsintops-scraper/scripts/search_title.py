#!/usr/bin/env python3
"""Search for thread-like links through a XenForo-style query URL."""
import argparse

from titsintops_toolkit import add_common_args, bounded_search, print_json, search_url_for_query


def main() -> int:
    parser = argparse.ArgumentParser(description="Search topics by title/query using a conservative XenForo-style search URL.")
    parser.add_argument("query", help="Search query")
    add_common_args(parser)
    args = parser.parse_args()
    payload = bounded_search(search_url_for_query(args.query), args.storage_state, args.allow_external)
    payload["query"] = args.query
    print_json(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
