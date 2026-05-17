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
    preview_url: str | None = None
    full_url: str | None = None
    resolution_status: str = "unresolved"
    resolution_method: str | None = None
    requires_auth: bool = False
    alternates: list[str] = field(default_factory=list)


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
    resolution_report: dict[str, Any] = field(default_factory=dict)

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


def media_path(url: str) -> str:
    """Return lower-case URL path for media/thumbnail heuristics."""
    return urlparse(url).path.lower()


def is_media_url(url: str) -> bool:
    """Return whether a URL looks like a direct media or XenForo attachment URL."""
    path = media_path(url)
    return "/attachments/" in path or path.endswith(MEDIA_EXTENSIONS)


def is_probable_thumbnail_url(url: str) -> bool:
    """Detect common preview/thumbnail URL patterns without site-specific crawling."""
    path = media_path(url)
    filename = Path(path).name
    return any(marker in path for marker in ["thumb", "thumbnail", "/small/", "/medium/", "/proxy.php"]) or bool(
        re.search(r"(?:^|[-_])(\d{2,4})x(\d{2,4})(?:[-_.]|$)", filename)
    )


def srcset_candidates(srcset: str | None, page_url: str) -> list[str]:
    """Parse srcset into URLs, sorted from smallest to largest descriptor."""
    if not srcset:
        return []
    parsed: list[tuple[float, str]] = []
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        url = strip_fragment(normalize_url(bits[0], page_url))
        score = 1.0
        if len(bits) > 1:
            descriptor = bits[1].strip().lower()
            try:
                if descriptor.endswith("w"):
                    score = float(descriptor[:-1] or 0)
                elif descriptor.endswith("x"):
                    score = float(descriptor[:-1] or 0) * 1000
            except ValueError:
                score = 1.0
        parsed.append((score, url))
    return [url for _, url in sorted(parsed, key=lambda item: item[0])]


def first_present_url(values: list[str | None], page_url: str) -> str | None:
    """Normalize and return the first usable URL-like attribute value."""
    for value in values:
        if not value or value.startswith("data:") or value.startswith("blob:"):
            continue
        return strip_fragment(normalize_url(value, page_url))
    return None


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
    """Collect preview URLs plus static hints for full-size media.

    The thread HTML often contains thumbnails while the parent anchor, srcset, or
    attachment link points at the full-size asset. This function records both:
    ``url`` remains the preview/current URL unless a later resolver upgrades it,
    while ``full_url`` and ``alternates`` preserve obvious full-size candidates.
    """
    soup = soup_from_html(html_text)
    seen: set[tuple[str, str | None, str | None]] = set()
    media: list[MediaCandidate] = []

    def add_candidate(
        raw_url: str | None,
        kind_hint: str = "",
        text: str | None = None,
        preview_url: str | None = None,
        full_url: str | None = None,
        alternates: list[str] | None = None,
        resolution_method: str | None = None,
    ) -> None:
        if not raw_url or raw_url.startswith("data:") or raw_url.startswith("blob:"):
            return
        absolute = strip_fragment(normalize_url(raw_url, page_url))
        normalized_preview = strip_fragment(normalize_url(preview_url, page_url)) if preview_url else None
        normalized_full = strip_fragment(normalize_url(full_url, page_url)) if full_url else None
        normalized_alternates = [strip_fragment(normalize_url(item, page_url)) for item in alternates or [] if item]
        if not allowed_host(absolute, allow_external=allow_external):
            return
        if normalized_full and not allowed_host(normalized_full, allow_external=allow_external):
            normalized_full = None
        normalized_alternates = [item for item in normalized_alternates if allowed_host(item, allow_external=allow_external)]
        if not is_media_url(absolute) and not (normalized_full and is_media_url(normalized_full)) and not any(is_media_url(item) for item in normalized_alternates):
            return
        key = (absolute, normalized_preview, normalized_full)
        if key in seen:
            return
        seen.add(key)
        resolved = bool(normalized_full and normalized_full != absolute and not is_probable_thumbnail_url(normalized_full))
        media.append(
            MediaCandidate(
                url=absolute,
                kind=infer_media_kind(normalized_full or absolute, kind_hint),
                source_page=page_url,
                text=text,
                preview_url=normalized_preview,
                full_url=normalized_full,
                resolution_status="static_hint" if resolved else "unresolved",
                resolution_method=resolution_method,
                requires_auth=False,
                alternates=[item for item in normalized_alternates if item not in {absolute, normalized_preview, normalized_full}],
            )
        )

    for img in soup.select("img"):
        preview = first_present_url(
            [img.get(attr) for attr in ["src", "data-src", "data-url", "data-original", "data-lazy-src"]],
            page_url,
        )
        srcset_urls = srcset_candidates(img.get("srcset") or img.get("data-srcset"), page_url)
        parent = img.find_parent("a", href=True)
        parent_url = strip_fragment(normalize_url(parent.get("href"), page_url)) if parent else None
        static_full = None
        if parent_url and is_media_url(parent_url):
            static_full = parent_url
        elif srcset_urls:
            static_full = srcset_urls[-1]
        if preview:
            add_candidate(
                preview,
                "image",
                img.get("alt"),
                preview_url=preview,
                full_url=static_full if static_full != preview else None,
                alternates=srcset_urls,
                resolution_method="static_html" if static_full and static_full != preview else None,
            )
        elif static_full:
            add_candidate(static_full, "image", img.get("alt"), full_url=static_full, alternates=srcset_urls, resolution_method="static_html")

    for link in soup.select("a[href]"):
        href = link.get("href")
        text = " ".join(link.get_text(" ", strip=True).split()) or None
        if href:
            add_candidate(href, "attachment" if "/attachments/" in href else "media", text, full_url=href, resolution_method="static_html")

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


def choose_best_full_url(candidate: MediaCandidate, allow_external: bool = False) -> str | None:
    """Choose the best already-known full-size URL from static HTML hints."""
    options = [candidate.full_url, *candidate.alternates, candidate.url]
    filtered: list[str] = []
    for option in options:
        if not option or option in filtered:
            continue
        if allowed_host(option, allow_external=allow_external) and is_media_url(option):
            filtered.append(option)
    if not filtered:
        return None
    non_thumbs = [option for option in filtered if not is_probable_thumbnail_url(option)]
    return (non_thumbs or filtered)[-1]


def apply_resolved_url(candidate: MediaCandidate, full_url: str, method: str, requires_auth: bool = False) -> None:
    """Update a media candidate in-place while preserving the preview URL."""
    if not candidate.preview_url and candidate.url != full_url:
        candidate.preview_url = candidate.url
    candidate.full_url = full_url
    candidate.url = full_url
    candidate.resolution_status = "resolved"
    candidate.resolution_method = method
    candidate.requires_auth = candidate.requires_auth or requires_auth


def resolve_static_full_size(media: list[MediaCandidate], allow_external: bool = False) -> dict[str, Any]:
    """Resolve full-size URLs using only attributes already present in HTML."""
    report = {"method": "static", "resolved": 0, "unresolved": 0, "errors": []}
    for candidate in media:
        full_url = choose_best_full_url(candidate, allow_external=allow_external)
        if full_url and (full_url != candidate.url or candidate.resolution_status == "static_hint" or not is_probable_thumbnail_url(full_url)):
            apply_resolved_url(candidate, full_url, "static_html", requires_auth=False)
            report["resolved"] += 1
        else:
            candidate.resolution_status = candidate.resolution_status or "unresolved"
            report["unresolved"] += 1
    return report


def extract_full_url_from_html(html_text: str, page_url: str, allow_external: bool = False) -> str | None:
    """Find likely full-size media URL inside an attachment/lightbox HTML page."""
    soup = soup_from_html(html_text)
    options: list[str] = []
    for meta_selector in ["meta[property='og:image']", "meta[name='twitter:image']"]:
        meta = soup.select_one(meta_selector)
        if meta and meta.get("content"):
            options.append(strip_fragment(normalize_url(meta.get("content"), page_url)))
    for img in soup.select("img"):
        options.extend(srcset_candidates(img.get("srcset") or img.get("data-srcset"), page_url))
        value = first_present_url([img.get(attr) for attr in ["data-original", "data-src", "data-url", "src"]], page_url)
        if value:
            options.append(value)
    for link in soup.select("a[href]"):
        href = strip_fragment(normalize_url(link.get("href"), page_url))
        if is_media_url(href):
            options.append(href)
    allowed = [url for url in options if allowed_host(url, allow_external=allow_external) and is_media_url(url)]
    non_thumbs = [url for url in allowed if not is_probable_thumbnail_url(url)]
    return (non_thumbs or allowed or [None])[-1]


def resolve_http_full_size(
    media: list[MediaCandidate],
    storage_state: Path = DEFAULT_STORAGE_STATE,
    require_auth: bool = False,
    allow_external: bool = False,
    max_media: int | None = None,
) -> dict[str, Any]:
    """Resolve full-size URLs by requesting attachment/lightbox URLs with httpx."""
    report = {"method": "http", "resolved": 0, "unresolved": 0, "errors": []}
    selected = media[:max_media] if max_media else media
    with make_http_client(storage_state, timeout=45.0, require_auth=require_auth) as client:
        for candidate in selected:
            probe_url = candidate.full_url or choose_best_full_url(candidate, allow_external=allow_external) or candidate.url
            if not probe_url:
                report["unresolved"] += 1
                continue
            try:
                response = client.get(probe_url, headers={"Referer": candidate.source_page, "Accept": "image/*,text/html,*/*;q=0.8"})
            except Exception as exc:
                report["errors"].append({"url": probe_url, "status": f"http_error: {exc}"})
                report["unresolved"] += 1
                continue
            content_type = response.headers.get("content-type", "").lower()
            if response.status_code in BLOCK_STATUS_CODES or response.status_code >= 500:
                candidate.requires_auth = True
                report["errors"].append({"url": probe_url, "status": f"http_{response.status_code}"})
                report["unresolved"] += 1
                continue
            if content_type.startswith("image/") or content_type.startswith("video/"):
                apply_resolved_url(candidate, str(response.url), "authenticated_http" if require_auth else "http", requires_auth=require_auth)
                report["resolved"] += 1
                continue
            ok, status = classify_response(response)
            if not ok:
                if status == "login_required_or_session_expired":
                    candidate.requires_auth = True
                report["errors"].append({"url": probe_url, "status": status})
                report["unresolved"] += 1
                continue
            full_url = extract_full_url_from_html(response.text, str(response.url), allow_external=allow_external)
            if full_url:
                apply_resolved_url(candidate, full_url, "authenticated_http" if require_auth else "http", requires_auth=require_auth)
                report["resolved"] += 1
            else:
                report["unresolved"] += 1
    return report


async def resolve_browser_full_size_async(
    media: list[MediaCandidate],
    storage_state: Path = DEFAULT_STORAGE_STATE,
    allow_external: bool = False,
    max_media: int | None = None,
    timeout_ms: int = 8000,
) -> dict[str, Any]:
    """Resolve full-size URLs by opening pages and clicking preview images."""
    load_storage_state(storage_state, require_auth=True)
    playwright_api = import_dependency(
        "playwright.async_api",
        "Install Playwright browser deps: pip install -r scripts/requirements.txt && playwright install chromium && playwright install-deps chromium",
    )
    selected = media[:max_media] if max_media else media
    report = {"method": "browser", "resolved": 0, "unresolved": 0, "errors": []}
    async with playwright_api.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(storage_state), user_agent=USER_AGENT)
        page = await context.new_page()
        for candidate in selected:
            try:
                await page.goto(candidate.source_page, wait_until="domcontentloaded", timeout=timeout_ms)
                basename = Path(urlparse(candidate.preview_url or candidate.url).path).name
                selectors = []
                if basename:
                    selectors.append(f"img[src*='{basename}']")
                if candidate.text:
                    safe_alt = candidate.text.replace("'", "\\'")[:80]
                    selectors.append(f"img[alt*='{safe_alt}']")
                clicked = False
                before = {strip_fragment(url) for url in await page.eval_on_selector_all("img", "imgs => imgs.map(img => img.currentSrc || img.src).filter(Boolean)")}
                for selector in selectors or ["img"]:
                    locator = page.locator(selector).first
                    try:
                        await locator.wait_for(state="visible", timeout=timeout_ms)
                        await locator.click(timeout=timeout_ms)
                        clicked = True
                        break
                    except Exception:
                        continue
                if not clicked:
                    report["unresolved"] += 1
                    report["errors"].append({"url": candidate.url, "status": "preview_not_found"})
                    continue
                await page.wait_for_timeout(min(timeout_ms, 3000))
                after = [strip_fragment(url) for url in await page.eval_on_selector_all("img", "imgs => imgs.map(img => img.currentSrc || img.src).filter(Boolean)")]
                options = [normalize_url(url, str(page.url)) for url in after if strip_fragment(url) not in before]
                options.extend([normalize_url(url, str(page.url)) for url in after])
                allowed = [url for url in options if allowed_host(url, allow_external=allow_external) and is_media_url(url)]
                non_thumbs = [url for url in allowed if not is_probable_thumbnail_url(url) and url != candidate.preview_url]
                full_url = (non_thumbs or allowed or [None])[-1]
                if full_url:
                    apply_resolved_url(candidate, full_url, "playwright_click", requires_auth=True)
                    report["resolved"] += 1
                else:
                    report["unresolved"] += 1
                await page.keyboard.press("Escape")
            except Exception as exc:
                report["unresolved"] += 1
                report["errors"].append({"url": candidate.url, "status": f"browser_error: {exc}"})
        await browser.close()
    return report


def resolve_browser_full_size(
    media: list[MediaCandidate],
    storage_state: Path = DEFAULT_STORAGE_STATE,
    allow_external: bool = False,
    max_media: int | None = None,
    timeout_ms: int = 8000,
) -> dict[str, Any]:
    """Synchronous wrapper for the Playwright click resolver."""
    return run_async(resolve_browser_full_size_async(media, storage_state, allow_external, max_media, timeout_ms))


def resolve_full_size_media(
    media: list[MediaCandidate],
    method: str = "static",
    storage_state: Path = DEFAULT_STORAGE_STATE,
    require_auth: bool = False,
    allow_external: bool = False,
    max_media: int | None = None,
    timeout_ms: int = 8000,
) -> dict[str, Any]:
    """Resolve candidates to full-size media using static, HTTP, browser, or auto mode."""
    report: dict[str, Any] = {"method": method, "steps": [], "resolved": 0, "unresolved": 0, "errors": []}
    methods = ["static", "http"] if method == "auto" else [method]
    if method == "auto" and require_auth:
        methods.append("browser")
    for step in methods:
        if step == "static":
            step_report = resolve_static_full_size(media, allow_external=allow_external)
        elif step == "http":
            unresolved = [item for item in media if item.resolution_status != "resolved"]
            step_report = resolve_http_full_size(unresolved, storage_state, require_auth, allow_external, max_media)
        elif step == "browser":
            unresolved = [item for item in media if item.resolution_status != "resolved"]
            step_report = resolve_browser_full_size(unresolved, storage_state, allow_external, max_media, timeout_ms)
        else:
            raise SystemExit(f"Unknown full-size resolver method: {step}")
        report["steps"].append(step_report)
    report["resolved"] = sum(1 for item in media if item.resolution_status == "resolved")
    report["unresolved"] = sum(1 for item in media if item.resolution_status != "resolved")
    report["errors"] = [error for step in report["steps"] for error in step.get("errors", [])]
    return report


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
            download_url = item.full_url if item.full_url and item.resolution_status == "resolved" else item.url
            download_source = "full_url" if item.full_url and item.resolution_status == "resolved" else ("preview_url" if item.preview_url and item.url == item.preview_url else "url")
            try:
                with client.stream("GET", download_url, headers={"Referer": item.source_page or referer, "Accept": "*/*"}) as response:
                    content_type = response.headers.get("content-type", "")
                    # Stop on the first blocked/error response instead of retrying aggressively.
                    if response.status_code in BLOCK_STATUS_CODES or response.status_code >= 400:
                        manifest["ok"] = False
                        manifest["errors"].append({"url": download_url, "status": f"http_{response.status_code}"})
                        break
                    # Media URLs that return HTML usually mean a login page, challenge,
                    # or intermediate viewer rather than the file itself.
                    if "text/html" in content_type.lower():
                        manifest["ok"] = False
                        manifest["errors"].append({"url": download_url, "status": "unexpected_html_instead_of_media"})
                        break
                    extension = extension_from_response(download_url, content_type)
                    stem = f"{index:05d}-{sanitize_slug(Path(urlparse(download_url).path).stem, 'media')}"
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
                            "content_length": response.headers.get("content-length"),
                            "preview_url": item.preview_url,
                            "full_url": item.full_url,
                            "resolution_status": item.resolution_status,
                            "resolution_method": item.resolution_method,
                            "download_source": download_source,
                        }
                    )
            except httpx.HTTPError as exc:
                manifest["ok"] = False
                manifest["errors"].append({"url": download_url, "status": f"http_error: {exc}"})
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
