from __future__ import annotations

import json
from pathlib import Path

import httpx

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HIKE_ORIGIN = "https://hike.taiwan.gov.tw"


def load_cookies_from_storage_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["name"]: c["value"] for c in data.get("cookies", [])}


def build_client(
    auth_state_path: Path | None = None,
    *,
    origin: str = HIKE_ORIGIN,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 10.0,
) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient with HTTP/2, keepalive, and Playwright-exported cookies."""
    cookies = load_cookies_from_storage_state(auth_state_path) if auth_state_path else {}

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Origin": origin,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=10,
        keepalive_expiry=60.0,
    )

    return httpx.AsyncClient(
        http2=True,
        cookies=cookies,
        headers=headers,
        limits=limits,
        timeout=httpx.Timeout(timeout, connect=5.0),
        follow_redirects=True,
    )


async def warm_up(client: httpx.AsyncClient, url: str) -> None:
    """Send a GET to establish DNS / TCP / TLS / HTTP/2 session ahead of time."""
    try:
        await client.get(url)
    except httpx.HTTPError:
        pass
