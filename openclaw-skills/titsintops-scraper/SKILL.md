---
name: titsintops-scraper
description: Controlled OpenClaw/Codex skill for building and running authorized TitsInTops/XenForo forum automation. Use when the agent needs to check public or authenticated access, search topics by title or tag, inspect XenForo thread pages, extract media URLs, optionally manage login sessions, or perform dry-run/strictly bounded rate-limited downloads for content the user is permitted to access.
---

# TitsInTops Scraper

## Operating rules

Use this skill only for authorized access to content available to the user's account. Do not bypass CAPTCHA, Cloudflare challenges, paywalls, account restrictions, bans, or access controls. Do not collect private messages, user profiles, emails, or other personal data. Never print, store in logs, or commit credentials, cookies, `storage_state.json`, `.env`, downloaded media, or session databases.

Default to inspection and `--dry-run`. Ask for explicit user confirmation before running a command that downloads files. Keep bounded limits (`--max-pages`, `--max-media`, `--delay`) and stop on `403`, `429`, login redirects, or challenge pages.

## Setup

1. Create a virtualenv outside the skill folder or in an ignored location.
2. Install Python dependencies from `scripts/requirements.txt`. For public HTTP inspection, `httpx` and `beautifulsoup4` are the important packages.
3. Install Playwright browser/system dependencies only if you need `login.py`:
   - `playwright install chromium`
   - On clean Ubuntu/server images: `playwright install-deps chromium`
4. Set secrets through environment variables or a local `.env` that is not committed, only if login is needed:
   - `TITSINTOPS_BASE_URL` defaults to `https://titsintops.com`
   - `TITSINTOPS_USERNAME` and `TITSINTOPS_PASSWORD` are optional for assisted login; manual login is preferred
   - `TITSINTOPS_STORAGE_STATE` defaults to `./storage_state.json`
   - `TITSINTOPS_DOWNLOAD_DIR` defaults to `./downloads/titsintops`

## Workflow

Run commands from this skill directory unless passing absolute paths. Default to public/direct HTTP first; login is optional and only required for pages that actually return login-required/blocked status.

1. Validate local setup:
   ```bash
   python scripts/check_env.py
   ```
2. Verify public/direct HTTP access without downloading anything:
   ```bash
   python scripts/check_session.py
   ```
3. Search or inspect with public HTTP. Add `--resolve-full --full-method static` to upgrade previews when the thread HTML already exposes parent attachment links or larger `srcset` entries:
   ```bash
   python scripts/search_title.py "example topic" --json
   python scripts/search_tag.py "example-tag" --json
   python scripts/inspect_thread.py "https://titsintops.com/..." --max-pages 2 --resolve-full --full-method static --json
   ```
4. If full-size images require login/click, create/refresh a browser session and then rerun full-size resolution with `--require-auth`:
   ```bash
   python scripts/login.py --manual
   python scripts/check_session.py "https://titsintops.com/..." --require-auth
   ```
5. Inspect full-size candidates with a required saved session. Prefer `http` first; use `browser` only when full-size URLs appear after a legitimate authenticated click/lightbox:
   ```bash
   python scripts/inspect_thread.py "https://titsintops.com/..." --max-pages 2 --resolve-full --full-method http --json --require-auth
   python scripts/inspect_thread.py "https://titsintops.com/..." --max-pages 2 --resolve-full --full-method browser --json --require-auth
   ```
6. Download only after reviewing dry-run JSON and receiving user confirmation. Omit `--require-auth` for public media; add it only for authenticated-only full-size pages:
   ```bash
   python scripts/scrape_thread.py "https://titsintops.com/..." --max-pages 2 --max-media 20 --resolve-full --full-method browser --require-auth --delay 3
   python scripts/scrape_thread.py "https://titsintops.com/..." --max-pages 2 --max-media 20 --resolve-full --full-method browser --require-auth --delay 3 --no-dry-run
   ```



## Full-size image resolution

Use full-size resolution when public thread HTML exposes only thumbnails/previews. The skill supports three bounded resolver modes:

- `static`: no extra requests beyond the thread page; upgrades previews using parent attachment links, `srcset`, and lazy-image attributes already present in HTML.
- `http`: requests attachment/lightbox URLs with `httpx` and optional saved cookies, then accepts direct `image/*` responses or parses attachment HTML for full image URLs.
- `browser`: authenticated Playwright fallback for the click/lightbox case. It opens the saved session, clicks the preview image, and records a full-size image URL if one appears in the page/lightbox. It does not solve CAPTCHA or bypass access controls.

Recommended escalation path: `static` -> `http --require-auth` -> `browser --require-auth`. Keep `--max-pages`, `--max-media`, and dry-run defaults while reviewing `preview_url`, `full_url`, `resolution_status`, and `resolution_method` in JSON.

## Code orientation for agents

- Start from `SKILL.md` for policy and command order, then inspect `scripts/titsintops_toolkit.py` for shared behavior. The small CLI files intentionally only parse arguments and call toolkit functions.
- Read `MediaCandidate` and `ThreadInspection` first to understand the JSON returned by the tools.
- Follow this call chain when debugging: `scrape_thread.py` -> `inspect_thread()` -> `extract_media_candidates()` -> `download_media()`.
- Change parser selectors in one place (`titsintops_toolkit.py`) rather than duplicating parsing logic across CLI wrappers.
- Keep comments and docstrings near safety checks. Future agents should understand why a command stops instead of retrying or bypassing a challenge.

## Script guide

- `check_env.py`: validates Python version, optional dependencies, path configuration, and ignored-secret hygiene.
- `login.py`: optional Playwright helper for manual or environment-assisted login; requires Chromium/browser dependencies and writes Playwright `storage_state` for authenticated-only pages.
- `check_session.py`: checks public/direct HTTP by default, optionally loads saved cookies, and detects whether a URL appears blocked, challenged, or redirected to login.
- `search_title.py`: performs a conservative XenForo-style title search and emits normalized JSON results.
- `search_tag.py`: fetches a XenForo-style tag page and emits normalized JSON results.
- `inspect_thread.py`: inspects bounded thread pages, extracts thread metadata/media candidates, and can resolve full-size URLs with `--resolve-full`, but does not download.
- `scrape_thread.py`: reuses the inspector, optionally resolves full-size URLs, and downloads bounded media with delay, hashing, manifest output, and stop-on-error behavior.

For implementation assumptions and expected site patterns, read `references/xenforo_workflow.md` only when changing parsers or endpoints.
