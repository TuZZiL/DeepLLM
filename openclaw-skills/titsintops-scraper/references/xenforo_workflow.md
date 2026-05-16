# XenForo workflow reference

## Scope

These scripts target authorized, rate-limited automation against XenForo-like forum pages. They are intentionally conservative and generic because live forms, search routes, and media layouts can change.

## Expected patterns

- Public/direct HTTP is the default path. Many XenForo thread and attachment URLs can return `200` without `storage_state.json`.
- Login/session access is optional and represented by cookies saved in Playwright `storage_state.json`; use it only when a page actually requires authentication.
- Thread URLs normally follow XenForo-style `/threads/<slug>.<id>/`; older `/phpBB2/` prefixes can still appear as legacy routing aliases, not proof that the site is phpBB.
- Thread URLs may paginate with `/page-N`, `page=N`, or links containing `page-`.
- Media candidates can appear in:
  - attachment links containing `/attachments/`
  - inline `<img src>` values
  - lazy image attributes such as `data-src`, `data-url`, or `data-original`
  - `srcset` entries
  - direct links ending in image/video extensions
- Full-size media may require the authenticated cookies and sometimes a thread `Referer`.

## Safety behavior

Stop rather than retry aggressively when responses indicate:

- HTTP `401`, `403`, `429`, or `5xx`
- text that looks like a login form or “must be logged in” message
- Cloudflare/challenge text or CAPTCHA markers
- redirects away from the requested allowed host

## Parser update checklist

When changing endpoint or parser logic:

1. Keep public/direct HTTP as the default; require `--require-auth` only for authenticated-only pages.
2. Keep `--dry-run` as the default for commands that can discover many resources.
3. Preserve `--max-pages`, `--max-media`, and `--delay` limits.
4. Keep JSON output stable: `ok`, `status`, `url`, `items`/`media`, `errors`.
5. Do not add credential logging.
6. Do not add CAPTCHA, anti-bot, paywall, or permission bypass logic.
