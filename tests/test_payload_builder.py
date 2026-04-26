from datetime import date
from pathlib import Path

import pytest

from hut_bot.grabber.viewstate import parse_viewstate
from hut_bot.routes.base import BookingParams, Member
from hut_bot.routes.catalog import get_handler, list_routes
from hut_bot.routes.hike_aspnet import HikeAspnetHandler

FIXTURE = Path(__file__).parent.parent / "storage" / "form_fixtures" / "synthetic_aspnet_form.html"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def params() -> BookingParams:
    leader = Member(
        name="王小明",
        id_number="A123456789",
        phone="0912345678",
        birthday=date(1990, 1, 1),
    )
    member = Member(
        name="李大華",
        id_number="B234567890",
        phone="0987654321",
        birthday=date(1985, 5, 5),
    )
    return BookingParams(
        start_date=date(2026, 6, 1),
        nights=2,
        people=2,
        leader=leader,
        members=[member],
    )


def test_catalog_lists_synthetic_route() -> None:
    routes = list_routes()
    assert "synthetic" in routes


def test_synthetic_handler_builds_payload(fixture_html: str, params: BookingParams) -> None:
    handler = get_handler("synthetic")
    assert isinstance(handler, HikeAspnetHandler)

    state = {
        "html": fixture_html,
        "viewstate": parse_viewstate(fixture_html),
        "url": handler.form_url,
    }
    payload = handler.build_payload(state, params)

    assert payload["__VIEWSTATE"] == "SYNTH_VIEWSTATE_BASE64_PLACEHOLDER=="
    assert payload["__EVENTVALIDATION"] == "SYNTH_EVENTVAL_BASE64_PLACEHOLDER=="
    assert payload["__VIEWSTATEGENERATOR"] == "A1B2C3D4"
    assert payload["__EVENTTARGET"] == "btnSubmit"
    assert payload["ddlRoute"] == "ROUTE_002"
    assert payload["txtStartDate"] == "2026/06/01"
    assert payload["txtNights"] == "2"
    assert payload["txtPeople"] == "2"
    assert payload["txtLeaderName"] == "王小明"
    assert payload["txtMember1Name"] == "李大華"
    assert payload["chkAgree"] == "on"


def test_parse_result_detects_success() -> None:
    handler = get_handler("synthetic")
    html = "<html><body>申請成功，申請編號：B240001 您的床位已預約。</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.success is True
    assert result.booking_id is not None and "B240001" in result.booking_id


def test_parse_result_detects_failure_marker() -> None:
    handler = get_handler("synthetic")
    html = "<html><body>很抱歉，該日期床位已額滿。</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.success is False
    assert result.error_message == "已額滿"


def test_parse_result_unknown_response_marked_failure() -> None:
    handler = get_handler("synthetic")
    html = "<html><body>some unrelated content</body></html>"
    result = handler.parse_result(html, http_status=200)
    assert result.success is False
    assert "unknown" in (result.error_message or "")


def test_unknown_route_raises() -> None:
    with pytest.raises(KeyError):
        get_handler("does_not_exist")
