from __future__ import annotations

from dataclasses import dataclass

import httpx
from lxml import html as lxml_html

from ..grabber.client import HIKE_ORIGIN
from ..grabber.viewstate import parse_viewstate
from .base import BookingParams, BookingResult, RouteHandler

# RECON_TODO: 以下所有欄位名都是依合成 fixture 設定，真實 hike.taiwan.gov.tw
# 表單欄位 name 必須在 Phase 1 recon 後覆蓋。標記 `# RECON_TODO:` 處要核對。

DEFAULT_FAILURE_MARKERS = (
    "已額滿",
    "申請失敗",
    "VIEWSTATE",
    "驗證碼錯誤",
    "尚未開放",
)
DEFAULT_SUCCESS_MARKERS = ("申請成功", "申請編號")


@dataclass
class HikeAspnetConfig:
    route_id: str
    route_value: str            # RECON_TODO: ddlRoute 的 option value
    form_url: str
    submit_url: str
    submit_event_target: str = "btnSubmit"   # RECON_TODO: 真實提交鈕的 name/UniqueID
    confirm_event_target: str | None = None  # RECON_TODO: 若有二次確認鈕，填它的 name


class HikeAspnetHandler(RouteHandler):
    def __init__(self, config: HikeAspnetConfig) -> None:
        self.config = config
        self.route_id = config.route_id
        self.form_url = config.form_url
        self.submit_url = config.submit_url

    async def fetch_form_state(self, client: httpx.AsyncClient) -> dict:
        response = await client.get(self.form_url, headers={"Referer": HIKE_ORIGIN + "/"})
        response.raise_for_status()
        viewstate = parse_viewstate(response.text)
        return {
            "html": response.text,
            "viewstate": viewstate,
            "url": str(response.url),
        }

    def build_payload(self, state: dict, params: BookingParams) -> dict:
        viewstate = state["viewstate"]
        payload = viewstate.as_payload()
        payload.update(
            {
                "__EVENTTARGET": self.config.submit_event_target,
                "__EVENTARGUMENT": "",
                # RECON_TODO: 以下欄位 name 全部是合成 fixture 預設值，
                # 跑完 hut-bot recon 後請對照 fixture 修正。
                "ddlRoute": self.config.route_value,
                "txtStartDate": params.start_date.strftime("%Y/%m/%d"),
                "txtNights": str(params.nights),
                "txtPeople": str(params.people),
                "txtLeaderName": params.leader.name,
                "txtLeaderID": params.leader.id_number,
                "txtLeaderPhone": params.leader.phone,
                "txtLeaderBirthday": params.leader.birthday.strftime("%Y/%m/%d"),
            }
        )
        if params.agree_terms:
            payload["chkAgree"] = "on"

        for idx, member in enumerate(params.members, start=1):
            # RECON_TODO: 隊員多列輸入的欄位 name pattern 待 recon 後確認
            payload[f"txtMember{idx}Name"] = member.name
            payload[f"txtMember{idx}ID"] = member.id_number
            payload[f"txtMember{idx}Phone"] = member.phone
            payload[f"txtMember{idx}Birthday"] = member.birthday.strftime("%Y/%m/%d")

        return payload

    def parse_result(self, html: str, http_status: int) -> BookingResult:
        text = html
        success_hit = next((m for m in DEFAULT_SUCCESS_MARKERS if m in text), None)
        failure_hit = next((m for m in DEFAULT_FAILURE_MARKERS if m in text), None)

        booking_id = _extract_booking_id(text)

        if success_hit:
            return BookingResult(
                success=True,
                booking_id=booking_id,
                raw_html=text,
                http_status=http_status,
                confirmation_required=_confirmation_required(text),
            )
        if failure_hit:
            return BookingResult(
                success=False,
                booking_id=None,
                raw_html=text,
                error_message=failure_hit,
                http_status=http_status,
            )
        return BookingResult(
            success=False,
            booking_id=None,
            raw_html=text,
            error_message=f"unknown response (status={http_status})",
            http_status=http_status,
        )

    async def confirm_if_needed(
        self,
        client: httpx.AsyncClient,
        result: BookingResult,
        params: BookingParams,
    ) -> BookingResult:
        if not result.confirmation_required or self.config.confirm_event_target is None:
            return result

        viewstate = parse_viewstate(result.raw_html)
        payload = viewstate.as_payload()
        payload["__EVENTTARGET"] = self.config.confirm_event_target
        payload["__EVENTARGUMENT"] = ""

        response = await client.post(
            self.submit_url,
            data=payload,
            headers={"Referer": self.submit_url, "Origin": HIKE_ORIGIN},
        )
        return self.parse_result(response.text, response.status_code)


def _extract_booking_id(html: str) -> str | None:
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return None
    # RECON_TODO: 真實成功頁的 booking_id 顯示位置待確認，這只是一個 fallback heuristic
    candidates = tree.xpath(
        "//*[contains(text(), '申請編號')]/following-sibling::*[1]/text() | "
        "//*[contains(text(), '申請編號')]/text()"
    )
    for raw in candidates:
        cleaned = raw.replace("申請編號", "").strip(" :：\n\t")
        if cleaned:
            return cleaned
    return None


def _confirmation_required(html: str) -> bool:
    # RECON_TODO: 真實「再次確認」頁的指紋待 recon 確認
    return "再次確認" in html or "確認送出" in html
