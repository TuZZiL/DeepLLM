#!/usr/bin/env python3
"""Search for thread-like links through a XenForo-style tag page."""
import argparse

from titsintops_toolkit import add_common_args, bounded_search, print_json, tag_url_for_tag


def main() -> int:
    parser = argparse.ArgumentParser(description="Search topics from a XenForo-style tag page.")
    parser.add_argument("tag", help="Tag name or slug")
    add_common_args(parser)
    args = parser.parse_args()
    payload = bounded_search(tag_url_for_tag(args.tag), args.storage_state, args.allow_external, args.require_auth)
    payload["tag"] = args.tag
    print_json(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
