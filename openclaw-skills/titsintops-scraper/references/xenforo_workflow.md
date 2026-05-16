# XenForo workflow reference

## Scope

These scripts target authorized, rate-limited automation against XenForo-like forum pages. They are intentionally conservative and generic because live forms, search routes, and media layouts can change.

## Expected patterns

- Login/session access is represented by cookies saved in Playwright `storage_state.json`.
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

1. Keep `--dry-run` as the default for commands that can discover many resources.
2. Preserve `--max-pages`, `--max-media`, and `--delay` limits.
3. Keep JSON output stable: `ok`, `status`, `url`, `items`/`media`, `errors`.
4. Do not add credential logging.
5. Do not add CAPTCHA, anti-bot, paywall, or permission bypass logic.
