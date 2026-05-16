#!/usr/bin/env python3
"""Create an optional Playwright browser session for authenticated-only pages.

Most public forum pages can be handled with direct HTTP. Use this script only
when check/inspect reports that a specific page requires login. Manual login is
preferred because it keeps credentials out of prompts/logs and lets the user
handle any legitimate interactive checks in the browser.
"""
import argparse
import os
from pathlib import Path

from titsintops_toolkit import BASE_URL, DEFAULT_STORAGE_STATE, USER_AGENT, import_dependency, load_dotenv_if_present, run_async


async def fill_first_visible(page, selectors: list[str], value: str, label: str, timeout_ms: int) -> bool:
    """Try a list of possible XenForo/login selectors without a long 30s hang."""
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout_ms)
            await locator.fill(value)
            return True
        except Exception:
            continue
    return False


async def browser_login(args: argparse.Namespace) -> None:
    install_hint = (
        "Install Python deps and browser: pip install -r scripts/requirements.txt && playwright install chromium. "
        "On Ubuntu servers also run: playwright install-deps chromium"
    )
    playwright_api = import_dependency("playwright.async_api", install_hint)
    async with playwright_api.async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        await page.goto(args.login_url, wait_until="domcontentloaded")
        if args.use_env_credentials:
            username = os.getenv("TITSINTOPS_USERNAME")
            password = os.getenv("TITSINTOPS_PASSWORD")
            if not username or not password:
                raise SystemExit("TITSINTOPS_USERNAME and TITSINTOPS_PASSWORD must be set for --use-env-credentials")
            username_selectors = [
                args.username_selector,
                "input[name='login']",
                "input[name='loginName']",
                "input[name='username']",
                "input[name='email']",
                "input[type='email']",
                "input[autocomplete='username']",
                "input#ctrl_pageLogin_login",
                "form[action*='login'] input[type='text']",
            ]
            password_selectors = [
                args.password_selector,
                "input[name='password']",
                "input[type='password']",
                "input[autocomplete='current-password']",
                "input#ctrl_pageLogin_password",
            ]
            filled_user = await fill_first_visible(page, [s for s in username_selectors if s], username, "username", args.selector_timeout_ms)
            filled_pass = await fill_first_visible(page, [s for s in password_selectors if s], password, "password", args.selector_timeout_ms)
            if not filled_user or not filled_pass:
                print("Could not find login fields quickly. Continue manually; this can happen on public pages, changed forms, or challenge pages.")
            else:
                print("Credentials filled from environment. Submit manually if auto-submit fails.")
        if args.manual or not args.use_env_credentials:
            print("Complete login in the opened browser if needed. This script will save session state after you press Enter here.")
            input("Press Enter after successful login or after confirming no login is needed: ")
        else:
            submit_selector = "button[type='submit'], input[type='submit']"
            await page.locator(submit_selector).first.click()
            await page.wait_for_load_state("domcontentloaded")
        args.storage_state.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(args.storage_state))
        await browser.close()
        print(f"Saved session state to {args.storage_state}")


def main() -> int:
    load_dotenv_if_present()
    parser = argparse.ArgumentParser(description="Create or refresh Playwright authenticated session state.")
    parser.add_argument("--login-url", default=f"{BASE_URL}/login/", help="Login page URL")
    parser.add_argument("--storage-state", type=Path, default=DEFAULT_STORAGE_STATE, help="Output storage_state JSON")
    parser.add_argument("--manual", action="store_true", help="Require manual login before saving session")
    parser.add_argument("--use-env-credentials", action="store_true", help="Fill username/password from env without printing them")
    parser.add_argument("--headless", action="store_true", help="Run browser headless; requires Playwright system deps on Linux")
    parser.add_argument("--selector-timeout-ms", type=int, default=3000, help="Per-selector wait when filling env credentials")
    parser.add_argument("--username-selector", help="Override username/login CSS selector")
    parser.add_argument("--password-selector", help="Override password CSS selector")
    args = parser.parse_args()
    if args.headless and args.manual:
        raise SystemExit("--headless cannot be combined with --manual")
    run_async(browser_login(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
