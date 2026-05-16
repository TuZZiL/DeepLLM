#!/usr/bin/env python3
"""Shared utilities for conservative, authorized XenForo inspection tools.

Agent orientation:
- CLI entrypoints are intentionally thin wrappers around this module.
- The default safe path is public HTTP: check_session.py -> search/inspect -> scrape_thread.py.
- login.py is optional and only needed when a page actually requires a user session.
- The module never stores credentials; when ``storage_state.json`` exists it only
  reuses Playwright cookies produced by login.py.
- Parser functions are deliberately generic because XenForo templates and old
  phpBB-style routes can vary between forums.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import importlib
import importlib.util
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse, urlunparse

# Runtime knobs are environment-driven so the skill folder can be copied to an
# OpenClaw workspace without editing source code. Keep defaults local and safe.
BASE_URL = os.getenv("TITSINTOPS_BASE_URL", "https://titsintops.com").rstrip("/")
DEFAULT_STORAGE_STATE = Path(os.getenv("TITSINTOPS_STORAGE_STATE", "storage_state.json"))
DEFAULT_DOWNLOAD_DIR = Path(os.getenv("TITSINTOPS_DOWNLOAD_DIR", "downloads/titsintops"))
USER_AGENT = os.getenv(
    "TITSINTOPS_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)
# Extension allowlists keep the extractor focused on media-like URLs and avoid
# turning this into a general crawler.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".m4v", ".webm", ".mov")
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
BLOCK_STATUS_CODES = {401, 403, 429}


@dataclass
class MediaCandidate:
    """One possible downloadable item discovered on a thread page.

    ``source_page`` is preserved so downloads can send a realistic Referer and
    so an agent can explain where a media URL came from.
    """
    url: str
    kind: str
    source_page: str
    post_id: str | None = None
    text: str | None = None


@dataclass
class ThreadInspection:
    """Stable JSON shape returned by inspect_thread.py and scrape_thread.py.

    Agents should check ``ok`` and ``status`` before acting on ``media``.
    """
    ok: bool
    status: str
    url: str
    title: str | None = None
    pages_requested: int = 0
    pages_seen: list[str] = field(default_factory=list)
    media: list[MediaCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        data = asdict(self)
        data["media"] = [asdict(item) for item in self.media]
        return data


def import_dependency(name: str, install_hint: str | None = None) -> Any:
    """Import optional runtime dependencies with a useful setup hint."""
    spec = importlib.util.find_spec(name)
    if spec is None:
        hint = install_hint or f"Install dependency: pip install {name}"
        raise SystemExit(hint)
    return importlib.import_module(name)


def load_dotenv_if_present() -> None:
    if importlib.util.find_spec("dotenv") is not None:
        dotenv = importlib.import_module("dotenv")
        dotenv.load_dotenv()


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def normalize_url(url: str, base_url: str = BASE_URL) -> str:
    """Resolve relative/forum URLs and decode HTML entities from attributes."""
    return urljoin(base_url + "/", html.unescape(url.strip()))


def allowed_host(url: str, base_url: str = BASE_URL, allow_external: bool = False) -> bool:
    """Return whether a URL is inside the configured site boundary.

    ``allow_external`` exists for user-approved external image hosts, but the
    default same-host behavior prevents accidental broad crawling.
    """
    if allow_external:
        return True
    host = urlparse(url).hostname or ""
    base_host = urlparse(base_url).hostname or ""
    return host == base_host or host.endswith("." + base_host)


def sanitize_slug(value: str, fallback: str = "item") -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return value[:120] or fallback


def load_storage_state(path: Path = DEFAULT_STORAGE_STATE, require_auth: bool = False) -> dict[str, Any]:
    """Read Playwright storage_state JSON created by login.py when present.

    Public TitsInTops/XenForo pages can often be fetched without cookies. Missing
    session state is therefore not fatal unless the caller explicitly asks for
    ``require_auth``.
    """
    if not path.exists():
        if require_auth:
            raise SystemExit(f"Session state not found: {path}. Run login.py first or omit --require-auth.")
        return {"cookies": []}
    return json.loads(path.read_text(encoding="utf-8"))


def cookies_from_storage_state(path: Path = DEFAULT_STORAGE_STATE, require_auth: bool = False) -> dict[str, str]:
    """Convert optional Playwright cookies into the simple dict httpx expects."""
    state = load_storage_state(path, require_auth=require_auth)
    cookies: dict[str, str] = {}
    for cookie in state.get("cookies", []):
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            cookies[str(name)] = str(value)
    if require_auth and not cookies:
        raise SystemExit(f"No cookies found in {path}. Refresh login state or omit --require-auth.")
    return cookies


def make_http_client(
    storage_state: Path = DEFAULT_STORAGE_STATE,
    timeout: float = 30.0,
    require_auth: bool = False,
) -> Any:
    """Create an httpx client, adding saved browser cookies only if available.

    Anonymous/public HTTP is the default because real-world checks showed many
    forum and attachment URLs are publicly reachable. Use ``require_auth=True``
    only for pages that genuinely need a saved session.
    """
    httpx = import_dependency("httpx", "Install dependencies: pip install -r scripts/requirements.txt")
    cookies = cookies_from_storage_state(storage_state, require_auth=require_auth)
    return httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        cookies=cookies,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    )


def classify_response(response: Any) -> tuple[bool, str]:
    """Classify a fetched HTML page as usable or requiring a safe stop.

    This is not an anti-bot bypass. It only detects situations where the agent
    should stop and report the state to the user.
    """
    status_code = getattr(response, "status_code", 0)
    final_url = str(getattr(response, "url", ""))
    text = getattr(response, "text", "") or ""
    low = text[:20000].lower()
    if status_code in BLOCK_STATUS_CODES:
        return False, f"blocked_http_{status_code}"
    if status_code >= 500:
        return False, f"server_error_{status_code}"
    if "captcha" in low or "cf-challenge" in low or "cloudflare" in low and "checking your browser" in low:
        return False, "challenge_or_captcha_detected"
    if "must be logged" in low or "log in" in low and ("password" in low or "login" in final_url.lower()):
        return False, "login_required_or_session_expired"
    if status_code >= 400:
        return False, f"http_{status_code}"
    return True, "ok"


def soup_from_html(markup: str) -> Any:
    bs4 = import_dependency("bs4", "Install dependencies: pip install -r scripts/requirements.txt")
    return bs4.BeautifulSoup(markup, "html.parser")


def extract_page_title(soup: Any) -> str | None:
    for selector in ["h1.p-title-value", "h1", "title"]:
        found = soup.select_one(selector)
        if found:
            text = " ".join(found.get_text(" ", strip=True).split())
            if text:
                return text
    return None


def extract_links_from_search(html_text: str, page_url: str, allow_external: bool = False) -> list[dict[str, str]]:
    """Extract likely thread result links from a search/tag page.

    Selectors include modern XenForo ``/threads/`` links and legacy routes that
    were observed during earlier analysis. Results are intentionally minimal.
    """
    soup = soup_from_html(html_text)
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    selectors = [
        "a[href*='/threads/']",
        "a[href*='threads/']",
        "a[href*='/phpBB2/']",
        "a[href*='topic']",
    ]
    for selector in selectors:
        for link in soup.select(selector):
            href = link.get("href")
            if not href:
                continue
            absolute = normalize_url(href, page_url)
            if absolute in seen or not allowed_host(absolute, allow_external=allow_external):
                continue
            text = " ".join(link.get_text(" ", strip=True).split())
            if not text or len(text) < 2:
                continue
            seen.add(absolute)
            results.append({"title": text, "url": absolute})
    return results


def discover_thread_pages(soup: Any, current_url: str, max_pages: int, allow_external: bool = False) -> list[str]:
    """Find bounded pagination URLs from the first thread page.

    The function does not crawl recursively; it only collects visible page links
    and truncates to ``max_pages``.
    """
    urls = [current_url]
    candidates: set[str] = set()
    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        text = link.get_text(" ", strip=True).lower()
        if "page" not in href.lower() and not text.isdigit() and text not in {"next", "наступна", "далі"}:
            continue
        absolute = normalize_url(href, current_url)
        if allowed_host(absolute, allow_external=allow_external):
            candidates.add(strip_fragment(absolute))
    def sort_key(url: str) -> tuple[int, str]:
        match = re.search(r"(?:page[-=/]|[?&]page=)(\d+)", url)
        return (int(match.group(1)) if match else 1, url)
    for url in sorted(candidates, key=sort_key):
        if url not in urls:
            urls.append(url)
        if len(urls) >= max_pages:
            break
    return urls[:max_pages]


def strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def infer_media_kind(url: str, hint: str = "") -> str:
    parsed_path = urlparse(url).path.lower()
    if "/attachments/" in parsed_path:
        if parsed_path.endswith(VIDEO_EXTENSIONS):
            return "attachment_video"
        return "attachment"
    if parsed_path.endswith(VIDEO_EXTENSIONS):
        return "video"
    if parsed_path.endswith(IMAGE_EXTENSIONS):
        return "image"
    if hint:
        return hint
    return "media"


def extract_media_candidates(html_text: str, page_url: str, allow_external: bool = False) -> list[MediaCandidate]:
    """Collect attachment, inline image, lazy image, and direct media URLs.

    This only returns candidate URLs. Downloading is a separate explicit step so
    agents can present a dry-run list and request confirmation first.
    """
    soup = soup_from_html(html_text)
    seen: set[str] = set()
    media: list[MediaCandidate] = []

    def add(raw_url: str | None, kind_hint: str = "", text: str | None = None) -> None:
        # Ignore embedded/browser-only URLs; only network-fetchable URLs are useful.
        if not raw_url or raw_url.startswith("data:") or raw_url.startswith("blob:"):
            return
        absolute = strip_fragment(normalize_url(raw_url, page_url))
        if absolute in seen or not allowed_host(absolute, allow_external=allow_external):
            return
        path = urlparse(absolute).path.lower()
        # Keep extraction narrow: attachments or known media extensions only.
        if "/attachments/" not in path and not path.endswith(MEDIA_EXTENSIONS):
            return
        seen.add(absolute)
        media.append(MediaCandidate(url=absolute, kind=infer_media_kind(absolute, kind_hint), source_page=page_url, text=text))

    for img in soup.select("img"):
        for attr in ["src", "data-src", "data-url", "data-original", "data-lazy-src"]:
            add(img.get(attr), "image", img.get("alt"))
        srcset = img.get("srcset") or img.get("data-srcset")
        if srcset:
            for part in srcset.split(","):
                add(part.strip().split(" ")[0], "image", img.get("alt"))

    for link in soup.select("a[href]"):
        href = link.get("href")
        text = " ".join(link.get_text(" ", strip=True).split()) or None
        add(href, "attachment" if href and "/attachments/" in href else "media", text)

    return media


def inspect_thread(
    url: str,
    max_pages: int = 1,
    storage_state: Path = DEFAULT_STORAGE_STATE,
    allow_external: bool = False,
    require_auth: bool = False,
) -> ThreadInspection:
    """Inspect up to ``max_pages`` pages and return metadata/media candidates."""
    if max_pages < 1:
        raise SystemExit("--max-pages must be at least 1")
    start_url = normalize_url(url, BASE_URL)
    if not allowed_host(start_url, allow_external=allow_external):
        raise SystemExit(f"Refusing URL outside allowed host: {start_url}")
    inspection = ThreadInspection(ok=False, status="not_started", url=start_url, pages_requested=max_pages)
    with make_http_client(storage_state, require_auth=require_auth) as client:
        # Fetch page 1 first because it contains the title and visible pagination.
        first = client.get(start_url, headers={"Referer": BASE_URL + "/"})
        ok, status = classify_response(first)
        inspection.status = status
        if not ok:
            inspection.errors.append(f"Initial page failed: {status}")
            return inspection
        soup = soup_from_html(first.text)
        inspection.title = extract_page_title(soup)
        page_urls = discover_thread_pages(soup, str(first.url), max_pages, allow_external=allow_external)
        if str(first.url) not in page_urls:
            page_urls.insert(0, str(first.url))
        for index, page_url in enumerate(page_urls[:max_pages]):
            # Reuse the already-fetched first page; fetch remaining pages one by one.
            response = first if index == 0 and page_url == str(first.url) else client.get(page_url, headers={"Referer": start_url})
            ok, status = classify_response(response)
            if not ok:
                inspection.errors.append(f"Page failed {page_url}: {status}")
                inspection.status = status
                break
            inspection.pages_seen.append(str(response.url))
            for candidate in extract_media_candidates(response.text, str(response.url), allow_external=allow_external):
                if candidate.url not in {item.url for item in inspection.media}:
                    inspection.media.append(candidate)
        inspection.ok = not inspection.errors
        inspection.status = "ok" if inspection.ok else inspection.status
    return inspection


def search_url_for_query(query: str, base_url: str = BASE_URL) -> str:
    return f"{base_url}/search/?q={quote_plus(query)}"


def tag_url_for_tag(tag: str, base_url: str = BASE_URL) -> str:
    cleaned = sanitize_slug(tag.lower().replace(" ", "-"), "tag")
    return f"{base_url}/tags/{cleaned}/"


def bounded_search(url: str, storage_state: Path, allow_external: bool = False, require_auth: bool = False) -> dict[str, Any]:
    """Fetch one search/tag page and return normalized thread-like links."""
    target = normalize_url(url, BASE_URL)
    if not allowed_host(target, allow_external=allow_external):
        raise SystemExit(f"Refusing URL outside allowed host: {target}")
    with make_http_client(storage_state, require_auth=require_auth) as client:
        response = client.get(target, headers={"Referer": BASE_URL + "/"})
        ok, status = classify_response(response)
        payload = {"ok": ok, "status": status, "url": str(response.url), "items": []}
        if ok:
            payload["items"] = extract_links_from_search(response.text, str(response.url), allow_external=allow_external)
        return payload


def download_media(
    media: list[MediaCandidate],
    output_dir: Path = DEFAULT_DOWNLOAD_DIR,
    max_media: int = 20,
    delay: float = 3.0,
    storage_state: Path = DEFAULT_STORAGE_STATE,
    referer: str = BASE_URL,
    require_auth: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Download a bounded media list, or return a manifest in dry-run mode."""
    if max_media < 1:
        raise SystemExit("--max-media must be at least 1")
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = media[:max_media]
    manifest: dict[str, Any] = {"ok": True, "dry_run": dry_run, "output_dir": str(output_dir), "items": [], "errors": []}
    if dry_run:
        # Dry-run is the default safety path: show the agent/user what would be
        # downloaded without touching remote media URLs.
        manifest["items"] = [asdict(item) | {"downloaded": False} for item in selected]
        return manifest
    httpx = import_dependency("httpx", "Install dependencies: pip install -r scripts/requirements.txt")
    with make_http_client(storage_state, timeout=60.0, require_auth=require_auth) as client:
        for index, item in enumerate(selected, start=1):
            if index > 1 and delay > 0:
                time.sleep(delay)
            try:
                with client.stream("GET", item.url, headers={"Referer": item.source_page or referer, "Accept": "*/*"}) as response:
                    content_type = response.headers.get("content-type", "")
                    # Stop on the first blocked/error response instead of retrying aggressively.
                    if response.status_code in BLOCK_STATUS_CODES or response.status_code >= 400:
                        manifest["ok"] = False
                        manifest["errors"].append({"url": item.url, "status": f"http_{response.status_code}"})
                        break
                    # Media URLs that return HTML usually mean a login page, challenge,
                    # or intermediate viewer rather than the file itself.
                    if "text/html" in content_type.lower():
                        manifest["ok"] = False
                        manifest["errors"].append({"url": item.url, "status": "unexpected_html_instead_of_media"})
                        break
                    extension = extension_from_response(item.url, content_type)
                    stem = f"{index:05d}-{sanitize_slug(Path(urlparse(item.url).path).stem, 'media')}"
                    path = output_dir / f"{stem}{extension}"
                    digest = hashlib.sha256()
                    bytes_written = 0
                    with path.open("wb") as handle:
                        for chunk in response.iter_bytes(chunk_size=1024 * 256):
                            if chunk:
                                digest.update(chunk)
                                handle.write(chunk)
                                bytes_written += len(chunk)
                    manifest["items"].append(
                        asdict(item)
                        | {
                            "downloaded": True,
                            "path": str(path),
                            "sha256": digest.hexdigest(),
                            "bytes": bytes_written,
                            "content_type": content_type,
                        }
                    )
            except httpx.HTTPError as exc:
                manifest["ok"] = False
                manifest["errors"].append({"url": item.url, "status": f"http_error: {exc}"})
                break
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def extension_from_response(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in MEDIA_EXTENSIONS:
        return suffix
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }
    return mapping.get(content_type.split(";")[0].lower(), ".bin")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--storage-state", type=Path, default=DEFAULT_STORAGE_STATE, help="Optional Playwright storage_state JSON; public HTTP is used when missing")
    parser.add_argument("--require-auth", action="store_true", help="Fail if --storage-state is missing or has no cookies")
    parser.add_argument("--allow-external", action="store_true", help="Allow parsing external media hosts; default is same host only")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")


def run_async(coro: Any) -> Any:
    return asyncio.run(coro)
