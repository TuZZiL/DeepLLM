#!/usr/bin/env python3
"""Bounded scrape wrapper: inspect first, then dry-run or download media.

The default mode is dry-run. Passing --no-dry-run is the explicit confirmation
that files may be downloaded within --max-pages/--max-media/--delay limits.
"""
import argparse
from pathlib import Path

from titsintops_toolkit import DEFAULT_DOWNLOAD_DIR, add_common_args, download_media, inspect_thread, print_json, resolve_full_size_media


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a thread and optionally download bounded media candidates.")
    parser.add_argument("url", help="Thread URL")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum thread pages to inspect")
    parser.add_argument("--max-media", type=int, default=20, help="Maximum media files to download or list")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay in seconds between media downloads")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DOWNLOAD_DIR, help="Download output directory")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually download media; default is dry-run")
    parser.add_argument("--resolve-full", action="store_true", help="Resolve preview images to full-size URLs before dry-run/download")
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
            max_media=args.max_media,
            timeout_ms=args.full_timeout_ms,
        )
    payload = {"inspection": inspection.to_jsonable(), "download": None}
    if inspection.ok:
        payload["download"] = download_media(
            inspection.media,
            output_dir=args.output_dir,
            max_media=args.max_media,
            delay=args.delay,
            storage_state=args.storage_state,
            referer=args.url,
            require_auth=args.require_auth,
            dry_run=not args.no_dry_run,
        )
    print_json(payload)
    return 0 if inspection.ok and (payload["download"] is None or payload["download"].get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
