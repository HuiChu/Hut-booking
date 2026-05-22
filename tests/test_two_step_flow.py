"""Test the new 2-step half-automated HikeAspnet flow with mocked httpx."""
from datetime import date

import httpx
import pytest

from hut_bot.routes.base import BookingParams, DayBed, Member
from hut_bot.routes.hike_aspnet import (
    FormState,
    HikeAspnetConfig,
    HikeAspnetHandler,
    STEP2_SUBMIT_BUTTON,
    STEP3_SUBMIT_BUTTON,
    VCODE2_FIELD,
    VCODE3_FIELD,
)

APPLY_1_2_HTML = """<html><body><form>
<input type="hidden" name="__VIEWSTATE" value="VS_1_2" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="VG_1_2" />
<input type="hidden" name="__EVENTVALIDATION" value="EV_1_2" />
<input type="hidden" name="ctl00$con$btnagree" value="我同意" />
</form></body></html>"""

APPLY_1_3_FORM_HTML = """<html><body><form>
<input type="hidden" name="__VIEWSTATE" value="VS_1_3" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="VG_1_3" />
<input type="hidden" name="__EVENTVALIDATION" value="EV_1_3" />
<input type="hidden" name="ctl00$con$Guid_Id" value="abc-1234" />
<input type="hidden" name="ctl00$con$hA_id" value="" />
<input type="hidden" name="ctl00$con$hidapplystart" value="2026-06-15" />
<input type="text" name="ctl00$con$apply_name" />
</form></body></html>"""

APPLY_1_3_CONFIRM_HTML = """<html><body>
<div class="alert alert-info">請確認資料正確無誤後，再確認送出!</div>
<form>
<input type="hidden" name="__VIEWSTATE" value="VS_CONFIRM" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="VG_CONFIRM" />
<input type="hidden" name="__EVENTVALIDATION" value="EV_CONFIRM" />
<input type="hidden" name="ctl00$con$Guid_Id" value="abc-1234" />
<input name="ctl00$con$vcode" />
<input type="submit" name="ctl00$con$btnsave" value="確認送出" />
</form></body></html>"""

SUCCESS_HTML = "<html><body>申請成功！申請編號：HK20260615-001</body></html>"


def _config() -> HikeAspnetConfig:
    return HikeAspnetConfig(
        route_id="秀霸線",
        route_code=156,
        unit="e6dd4652-2d37-4346-8f5d-6e538353e0c2",
        fid=8,
        camp_id=0,
    )


def _params() -> BookingParams:
    leader = Member("王領隊", "A123", "0911", date(1990, 1, 1), sex="M")
    member = Member("林隊員", "B234", "0922", date(1991, 1, 1), sex="F")
    return BookingParams(
        start_date=date(2026, 6, 15),
        nights=2,
        people=2,
        leader=leader,
        members=[member],
        team_name="王領隊隊",
        day_beds=[DayBed(day_index=1, num=2, rooms=1)],
    )


def _make_client_recording() -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Mock client recording every request and returning canned responses by URL pattern."""
    recorded: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        path = request.url.path

        if path == "/apply_1_2.aspx" and request.method == "GET":
            return httpx.Response(200, text=APPLY_1_2_HTML)
        if path == "/apply_1_2.aspx" and request.method == "POST":
            return httpx.Response(
                302,
                text="",
                headers={"location": "/apply_1_3.aspx?RandomStr=999"},
            )
        if path == "/apply_1_3.aspx" and request.method == "GET":
            return httpx.Response(200, text=APPLY_1_3_FORM_HTML)
        if path == "/apply_1_3.aspx" and request.method == "POST":
            # First POST returns confirm page; second returns success
            count = sum(1 for r in recorded if r.url.path == path and r.method == "POST")
            if count == 1:
                return httpx.Response(200, text=APPLY_1_3_CONFIRM_HTML)
            return httpx.Response(200, text=SUCCESS_HTML)
        return httpx.Response(404, text="not mocked")

    return httpx.AsyncClient(transport=httpx.MockTransport(transport)), recorded


@pytest.mark.asyncio
async def test_full_two_step_flow_succeeds() -> None:
    handler = HikeAspnetHandler(_config())
    params = _params()
    client, recorded = _make_client_recording()

    async with client:
        # Step 1: apply_1_2 GET
        state_1_2 = await handler.fetch_apply_1_2(client)
        assert state_1_2.viewstate == "VS_1_2"

        # Step 2: apply_1_2 POST → 302 → apply_1_3 URL
        apply_1_3_url = await handler.submit_apply_1_2(client, state_1_2)
        assert apply_1_3_url.endswith("/apply_1_3.aspx?RandomStr=999")

        # Step 3: apply_1_3 GET
        state_1_3 = await handler.fetch_apply_1_3(client, apply_1_3_url)
        assert state_1_3.viewstate == "VS_1_3"
        assert state_1_3.hidden_inputs.get("ctl00$con$Guid_Id") == "abc-1234"

        # Step 4: build step2 payload + POST → confirm page
        payload2 = handler.build_step2_payload(state_1_3, params, vcode2="ABCD")
        assert payload2[VCODE2_FIELD] == "ABCD"
        assert payload2[STEP2_SUBMIT_BUTTON] == "下一步"
        assert payload2["ctl00$con$Guid_Id"] == "abc-1234"

        state_3 = await handler.submit_step2(client, apply_1_3_url, payload2)
        assert state_3.viewstate == "VS_CONFIRM"

        # Step 5: build step3 payload + POST → success
        payload3 = handler.build_step3_payload(state_3, vcode="EFGH")
        assert payload3[VCODE3_FIELD] == "EFGH"
        assert payload3[STEP3_SUBMIT_BUTTON] == "確認送出"

        result = await handler.submit_step3(client, apply_1_3_url, payload3)

    assert result.success is True
    assert result.booking_id and "HK20260615-001" in result.booking_id

    # Verify request count and order
    methods_paths = [(r.method, r.url.path) for r in recorded]
    assert methods_paths == [
        ("GET", "/apply_1_2.aspx"),
        ("POST", "/apply_1_2.aspx"),
        ("GET", "/apply_1_3.aspx"),
        ("POST", "/apply_1_3.aspx"),
        ("POST", "/apply_1_3.aspx"),
    ]


@pytest.mark.asyncio
async def test_apply_1_2_post_without_302_raises() -> None:
    handler = HikeAspnetHandler(_config())

    def transport(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text=APPLY_1_2_HTML)
        return httpx.Response(200, text="<html>unexpected 200 not 302</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        state = await handler.fetch_apply_1_2(client)
        with pytest.raises(RuntimeError, match="預期 302"):
            await handler.submit_apply_1_2(client, state)


def test_apply_1_2_url_built_from_config() -> None:
    config = _config()
    expected = (
        "https://hike.taiwan.gov.tw/apply_1_2.aspx"
        "?unit=e6dd4652-2d37-4346-8f5d-6e538353e0c2&cid=156&fid=8&camp_id=0"
    )
    assert config.apply_1_2_url == expected
