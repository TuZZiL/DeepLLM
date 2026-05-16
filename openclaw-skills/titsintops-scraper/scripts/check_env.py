#!/usr/bin/env python3
"""Report whether the copied skill folder is ready to run.

This script is safe to run first: it does not contact the target site and does
not read secret values. It only reports whether environment variables are set.
"""
from pathlib import Path
import importlib.util
import os
import sys

from titsintops_toolkit import BASE_URL, DEFAULT_DOWNLOAD_DIR, DEFAULT_STORAGE_STATE, print_json


def main() -> int:
    deps = ["httpx", "bs4", "playwright", "dotenv"]
    dependency_status = {name: importlib.util.find_spec(name) is not None for name in deps}
    ignored_paths = [".env", str(DEFAULT_STORAGE_STATE), str(DEFAULT_DOWNLOAD_DIR), "downloads/", "*.sqlite", "cookies.json"]
    payload = {
        "ok": sys.version_info >= (3, 10) and dependency_status["httpx"] and dependency_status["bs4"],
        "python": sys.version.split()[0],
        "base_url": BASE_URL,
        "storage_state": str(DEFAULT_STORAGE_STATE),
        "storage_state_exists": DEFAULT_STORAGE_STATE.exists(),
        "download_dir": str(DEFAULT_DOWNLOAD_DIR),
        "dependencies": dependency_status,
        "dependency_notes": {
            "required_for_public_http": ["httpx", "beautifulsoup4"],
            "optional_for_login_browser": ["playwright", "python-dotenv"],
            "playwright_browser_install": "playwright install chromium",
            "ubuntu_system_dependencies": "playwright install-deps chromium",
        },
        "secret_hygiene": {
            "env_username_set": bool(os.getenv("TITSINTOPS_USERNAME")),
            "env_password_set": bool(os.getenv("TITSINTOPS_PASSWORD")),
            "do_not_commit": ignored_paths,
        },
    }
    print_json(payload)
    if not payload["ok"]:
        print("Install Python dependencies with: pip install -r scripts/requirements.txt", file=sys.stderr)
        print("For login.py on clean Ubuntu also run: playwright install chromium && playwright install-deps chromium", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
