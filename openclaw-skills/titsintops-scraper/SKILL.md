---
name: titsintops-scraper
description: Controlled OpenClaw/Codex skill for building and running authorized TitsInTops/XenForo forum automation. Use when the agent needs to manage login sessions, check authenticated access, search topics by title or tag, inspect XenForo thread pages, extract media URLs, or perform dry-run/strictly bounded rate-limited downloads for content the user is permitted to access.
---

# TitsInTops Scraper

## Operating rules

Use this skill only for authorized access to content available to the user's account. Do not bypass CAPTCHA, Cloudflare challenges, paywalls, account restrictions, bans, or access controls. Do not collect private messages, user profiles, emails, or other personal data. Never print, store in logs, or commit credentials, cookies, `storage_state.json`, `.env`, downloaded media, or session databases.

Default to inspection and `--dry-run`. Ask for explicit user confirmation before running a command that downloads files. Keep bounded limits (`--max-pages`, `--max-media`, `--delay`) and stop on `403`, `429`, login redirects, or challenge pages.

## Setup

1. Create a virtualenv outside the skill folder or in an ignored location.
2. Install dependencies from `scripts/requirements.txt`.
3. Set secrets through environment variables or a local `.env` that is not committed:
   - `TITSINTOPS_BASE_URL` defaults to `https://titsintops.com`
   - `TITSINTOPS_USERNAME` and `TITSINTOPS_PASSWORD` are optional for assisted login; manual login is preferred
   - `TITSINTOPS_STORAGE_STATE` defaults to `./storage_state.json`
   - `TITSINTOPS_DOWNLOAD_DIR` defaults to `./downloads/titsintops`

## Workflow

Run commands from this skill directory unless passing absolute paths.

1. Validate local setup:
   ```bash
   python scripts/check_env.py
   ```
2. Create or refresh an authenticated browser session:
   ```bash
   python scripts/login.py --manual
   ```
3. Verify access without downloading anything:
   ```bash
   python scripts/check_session.py
   ```
4. Search or inspect:
   ```bash
   python scripts/search_title.py "example topic" --json
   python scripts/search_tag.py "example-tag" --json
   python scripts/inspect_thread.py "https://titsintops.com/..." --max-pages 2 --json
   ```
5. Download only after user confirmation, with strict bounds:
   ```bash
   python scripts/scrape_thread.py "https://titsintops.com/..." --max-pages 2 --max-media 20 --delay 3 --no-dry-run
   ```


## Code orientation for agents

- Start from `SKILL.md` for policy and command order, then inspect `scripts/titsintops_toolkit.py` for shared behavior. The small CLI files intentionally only parse arguments and call toolkit functions.
- Read `MediaCandidate` and `ThreadInspection` first to understand the JSON returned by the tools.
- Follow this call chain when debugging: `scrape_thread.py` -> `inspect_thread()` -> `extract_media_candidates()` -> `download_media()`.
- Change parser selectors in one place (`titsintops_toolkit.py`) rather than duplicating parsing logic across CLI wrappers.
- Keep comments and docstrings near safety checks. Future agents should understand why a command stops instead of retrying or bypassing a challenge.

## Script guide

- `check_env.py`: validates Python version, optional dependencies, path configuration, and ignored-secret hygiene.
- `login.py`: uses Playwright to perform manual or environment-assisted login and writes Playwright `storage_state` for later scripts.
- `check_session.py`: loads the saved session and detects whether a URL appears authenticated, blocked, challenged, or redirected to login.
- `search_title.py`: performs a conservative XenForo-style title search and emits normalized JSON results.
- `search_tag.py`: fetches a XenForo-style tag page and emits normalized JSON results.
- `inspect_thread.py`: inspects bounded thread pages, extracts thread metadata and media candidates, but does not download.
- `scrape_thread.py`: reuses the inspector and downloads bounded media with delay, hashing, manifest output, and stop-on-error behavior.

For implementation assumptions and expected site patterns, read `references/xenforo_workflow.md` only when changing parsers or endpoints.
