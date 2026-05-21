from datetime import date, datetime, timedelta

import httpx
import pytest

from hut_bot.grabber.poster import grab_until, post_once
from hut_bot.routes.base import BookingParams, Member
from hut_bot.routes.hike_aspnet import HikeAspnetConfig, HikeAspnetHandler

FORM_HTML = """
<html><body><form>
<input type="hidden" name="__VIEWSTATE" value="VS1" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="VG1" />
<input type="hidden" name="__EVENTVALIDATION" value="EV1" />
</form></body></html>
"""

SUCCESS_HTML = "<html><body>申請成功，申請編號：X240001 完成。</body></html>"
FAILURE_HTML = "<html><body>申請失敗：已額滿</body></html>"


def _params() -> BookingParams:
    leader = Member("王", "A1", "0900000000", date(1990, 1, 1))
    return BookingParams(date(2026, 6, 1), 1, 1, leader, [])


def _handler() -> HikeAspnetHandler:
    return HikeAspnetHandler(
        HikeAspnetConfig(
            route_id="test",
            route_value="R1",
            form_url="https://example.test/form",
            submit_url="https://example.test/submit",
        )
    )


def _make_client(responses: list[httpx.Response]) -> httpx.AsyncClient:
    """Return an AsyncClient that replays `responses` in order, then repeats the last one."""
    index = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        i = min(index["i"], len(responses) - 1)
        index["i"] += 1
        r = responses[i]
        return httpx.Response(r.status_code, content=r.content, headers=r.headers)

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_post_once_returns_success_on_first_try() -> None:
    responses = [
        httpx.Response(200, text=FORM_HTML),
        httpx.Response(200, text=SUCCESS_HTML),
    ]
    async with _make_client(responses) as client:
        result = await post_once(_handler(), client, _params())
    assert result.success is True
    assert result.booking_id and "X240001" in result.booking_id


@pytest.mark.asyncio
async def test_grab_until_retries_until_success() -> None:
    responses = [
        httpx.Response(200, text=FORM_HTML),
        httpx.Response(200, text=FAILURE_HTML),
        httpx.Response(200, text=FORM_HTML),
        httpx.Response(200, text=SUCCESS_HTML),
    ]
    deadline = datetime.now() + timedelta(seconds=5)
    async with _make_client(responses) as client:
        result = await grab_until(_handler(), client, _params(), deadline=deadline)
    assert result.success is True


@pytest.mark.asyncio
async def test_grab_until_returns_last_failure_after_deadline() -> None:
    responses = [
        httpx.Response(200, text=FORM_HTML),
        httpx.Response(200, text=FAILURE_HTML),
    ]
    deadline = datetime.now() + timedelta(milliseconds=50)
    async with _make_client(responses) as client:
        result = await grab_until(_handler(), client, _params(), deadline=deadline)
    assert result.success is False
    assert result.error_message
