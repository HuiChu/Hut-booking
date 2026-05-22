from datetime import date
from pathlib import Path

import pytest

from hut_bot.grabber.viewstate import parse_viewstate
from hut_bot.routes.base import BookingParams, DayBed, Member
from hut_bot.routes.catalog import get_handler, list_routes
from hut_bot.routes.hike_aspnet import (
    FormState,
    HikeAspnetConfig,
    HikeAspnetHandler,
    STEP2_SUBMIT_BUTTON,
    STEP3_SUBMIT_BUTTON,
    VCODE2_FIELD,
    VCODE3_FIELD,
)

FIXTURE = Path(__file__).parent.parent / "storage" / "form_fixtures" / "synthetic_aspnet_form.html"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def form_state(fixture_html: str) -> FormState:
    return FormState.from_html(fixture_html, url="https://hike.taiwan.gov.tw/apply_1_3.aspx?RandomStr=999")


@pytest.fixture
def params() -> BookingParams:
    leader = Member(
        name="王小明",
        id_number="A123456789",
        phone="0912345678",
        birthday=date(1990, 1, 1),
        sex="M",
        email="leader@example.com",
        addr="台北市信義區",
        contact_name="王太太",
        contact_tel="0987654321",
    )
    alice = Member(
        name="林小華",
        id_number="B223456789",
        phone="0922334455",
        birthday=date(1991, 3, 12),
        sex="F",
        email="alice@example.com",
    )
    return BookingParams(
        start_date=date(2026, 6, 15),
        nights=2,
        people=2,
        leader=leader,
        members=[alice],
        agree_terms=True,
        team_name="王小明隊",
        day_beds=[
            DayBed(day_index=1, num=2, bedok=True, bakroomok=True, rooms=1),
            DayBed(day_index=2, num=2, bedok=True, bakroomok=False, rooms=1),
        ],
    )


@pytest.fixture
def handler() -> HikeAspnetHandler:
    config = HikeAspnetConfig(
        route_id="synthetic",
        route_code=156,
        unit="SYNTH-UNIT-UUID",
        fid=8,
        camp_id=0,
    )
    return HikeAspnetHandler(config)


def test_catalog_lists_synthetic_route() -> None:
    assert "synthetic" in list_routes()


def test_form_state_extracts_viewstate(form_state: FormState) -> None:
    assert form_state.viewstate == "SYNTH_VIEWSTATE_BASE64_PLACEHOLDER=="
    assert form_state.viewstate_generator == "A1B2C3D4"
    assert form_state.event_validation == "SYNTH_EVENTVAL_BASE64_PLACEHOLDER=="


def test_step2_payload_uses_real_field_names(
    handler: HikeAspnetHandler, form_state: FormState, params: BookingParams
) -> None:
    payload = handler.build_step2_payload(form_state, params, vcode2="ABCD")

    # ASP.NET base
    assert payload["__VIEWSTATE"] == "SYNTH_VIEWSTATE_BASE64_PLACEHOLDER=="
    assert payload["__EVENTVALIDATION"] == "SYNTH_EVENTVAL_BASE64_PLACEHOLDER=="
    assert payload["__VIEWSTATEGENERATOR"] == "A1B2C3D4"
    assert payload["__EVENTTARGET"] == ""

    # 領隊
    assert payload["ctl00$con$leader_name"] == "王小明"
    assert payload["ctl00$con$leader_sid"] == "A123456789"
    assert payload["ctl00$con$leader_mobile"] == "0912345678"
    assert payload["ctl00$con$leader_birthday"] == "1990-01-01"

    # 申請人預設複製領隊
    assert payload["ctl00$con$apply_name"] == "王小明"
    assert payload["ctl00$con$copyapply"] == "on"

    # 隊員（lisMem repeater）
    assert payload["ctl00$con$lisMem$ctrl1$member_name"] == "林小華"
    assert payload["ctl00$con$lisMem$ctrl1$member_sid"] == "B223456789"
    assert payload["ctl00$con$lisMem$ctrl1$member_birthday"] == "1991-03-12"

    # 隊伍 + 行程
    assert payload["ctl00$con$teams_name"] == "王小明隊"
    assert payload["ctl00$con$teams_count"] == "2"
    assert payload["ctl00$con$climbline"] == "156"
    assert payload["ctl00$con$applystart"] == "2026-06-15"
    assert payload["ctl00$con$sumday"] == "3"  # nights + 1

    # 床位 (lisText)
    assert payload["ctl00$con$lisText$ctrl1$num"] == "2"
    assert payload["ctl00$con$lisText$ctrl1$bedok"] == "1"
    assert payload["ctl00$con$lisText$ctrl2$bakroomok"] == "0"

    # CAPTCHA + 送出鈕
    assert payload[VCODE2_FIELD] == "ABCD"
    assert payload[STEP2_SUBMIT_BUTTON] == "下一步"

    # 同意聲明
    assert payload["ctl00$con$applycheck"] == "on"

    # ddl* fields keep the ctl00$con$ prefix (bug fix: not bare "ddlapply_country")
    assert "ctl00$con$ddlapply_country" in payload
    assert "ctl00$con$ddlleader_country" in payload
    assert "ddlapply_country" not in payload


def test_step2_payload_with_separate_applicant(
    handler: HikeAspnetHandler, form_state: FormState, params: BookingParams
) -> None:
    applicant = Member(
        name="代理人",
        id_number="E123456789",
        phone="0900000000",
        birthday=date(1985, 1, 1),
    )
    p = BookingParams(**{**params.__dict__, "applicant": applicant})
    payload = handler.build_step2_payload(form_state, p, vcode2="X")
    assert payload["ctl00$con$apply_name"] == "代理人"
    assert payload["ctl00$con$leader_name"] == "王小明"
    assert payload["ctl00$con$copyapply"] == ""


def test_step3_payload_minimal(handler: HikeAspnetHandler, form_state: FormState) -> None:
    payload = handler.build_step3_payload(form_state, vcode="EFGH")
    assert payload[VCODE3_FIELD] == "EFGH"
    assert payload[STEP3_SUBMIT_BUTTON] == "確認送出"
    assert payload["__VIEWSTATE"] == "SYNTH_VIEWSTATE_BASE64_PLACEHOLDER=="


def test_parse_result_detects_success(handler: HikeAspnetHandler) -> None:
    html = "<html><body>申請成功，申請編號：B240001</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.success is True
    assert result.booking_id and "B240001" in result.booking_id


def test_parse_result_detects_failure(handler: HikeAspnetHandler) -> None:
    html = "<html><body>很抱歉，該日期床位已額滿。</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.success is False
    assert result.error_message == "已額滿"


def test_parse_result_detects_confirm_page(handler: HikeAspnetHandler) -> None:
    html = "<html><body>請確認資料正確無誤後，再確認送出!</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.confirmation_required is True
    assert result.success is False


def test_parse_result_unknown_response(handler: HikeAspnetHandler) -> None:
    html = "<html><body>some unrelated content</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.success is False
    assert "unknown" in (result.error_message or "")
