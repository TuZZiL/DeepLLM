#!/usr/bin/env python3
"""Create a Playwright browser session for later authenticated HTTP calls.

Manual login is preferred because it keeps credentials out of prompts/logs and
lets the user handle any legitimate interactive checks in the browser.
"""
import argparse
import os
from pathlib import Path

from titsintops_toolkit import BASE_URL, DEFAULT_STORAGE_STATE, USER_AGENT, import_dependency, load_dotenv_if_present, run_async


async def browser_login(args: argparse.Namespace) -> None:
    playwright_api = import_dependency("playwright.async_api", "Install dependencies and browsers: pip install -r scripts/requirements.txt && playwright install chromium")
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
            username_selector = "input[name='login'], input[name='loginName'], input[name='username'], input[type='email']"
            password_selector = "input[name='password'], input[type='password']"
            await page.locator(username_selector).first.fill(username)
            await page.locator(password_selector).first.fill(password)
            print("Credentials filled from environment. Submit manually if auto-submit fails.")
        if args.manual or not args.use_env_credentials:
            print("Complete login in the opened browser. This script will save session state after you press Enter here.")
            input("Press Enter after successful login: ")
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
    parser.add_argument("--headless", action="store_true", help="Run browser headless; not recommended for first login")
    args = parser.parse_args()
    if args.headless and args.manual:
        raise SystemExit("--headless cannot be combined with --manual")
    run_async(browser_login(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
