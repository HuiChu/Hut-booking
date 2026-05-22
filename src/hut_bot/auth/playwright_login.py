from __future__ import annotations

from pathlib import Path

from playwright.async_api import async_playwright

HIKE_LOGIN_URL = "https://hike.taiwan.gov.tw/login.aspx"
HIKE_HOME_URL = "https://hike.taiwan.gov.tw/"


async def interactive_login(
    storage_state_path: Path,
    *,
    username: str = "",
    password: str = "",
    login_url: str = HIKE_LOGIN_URL,
    home_url: str = HIKE_HOME_URL,
) -> None:
    """Open a headed Chromium, prefill credentials if available, then let the user
    finish CAPTCHA / OTP manually. When the user navigates away from the login page
    (i.e. login succeeded), the storage_state is exported to disk.
    """
    storage_state_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(login_url)

        if username:
            await _try_fill(page, ["#txtAccount", "#txtUserName", "input[name*='Account']"], username)
        if password:
            await _try_fill(page, ["#txtPassword", "input[name*='Password']"], password)

        print(
            "[hut-bot] 已開啟登入頁。請手動完成 CAPTCHA / OTP 並登入成功，\n"
            "登入成功後（網址離開登入頁）腳本會自動匯出 cookie。\n"
            "若要中止，直接關閉瀏覽器即可。"
        )

        try:
            await page.wait_for_url(
                lambda url: "login" not in url.lower(),
                timeout=10 * 60 * 1000,
            )
        except Exception as exc:
            print(f"[hut-bot] 等待登入逾時或失敗：{exc}")
            await browser.close()
            return

        await context.storage_state(path=str(storage_state_path))
        print(f"[hut-bot] 登入狀態已匯出到 {storage_state_path}")
        await browser.close()


async def _try_fill(page, selectors: list[str], value: str) -> None:
    for selector in selectors:
        try:
            await page.fill(selector, value, timeout=1000)
            return
        except Exception:
            continue
