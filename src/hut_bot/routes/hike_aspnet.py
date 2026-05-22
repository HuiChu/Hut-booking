"""hike.taiwan.gov.tw 國家公園山屋 2-step 申請 handler.

完整流程（半自動）：
    1. fetch_apply_1_2() → GET 路線同意條款頁
    2. submit_apply_1_2() → POST btnagree → 302 → 回傳 apply_1_3 URL
    3. fetch_apply_1_3(url) → GET 主表單頁，回傳 FormState
    4. build_step2_payload(state, params, vcode2) → 含申請人/領隊/隊員/留守人/床位
       + btnsetp2upnext + vcode2
    5. submit_step2() → POST → 回再次確認頁 (step 3)
    6. build_step3_payload(state3, vcode) → 含 btnsave + vcode
    7. submit_step3() → POST → 真正訂位

CAPTCHA (vcode2 & vcode) 由 caller 負責解（半自動：user 從瀏覽器看圖讀碼）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx
from lxml import html as lxml_html

from ..grabber.client import HIKE_ORIGIN
from ..grabber.viewstate import parse_all_hidden_inputs, parse_viewstate
from .base import BookingParams, BookingResult, Member, RouteHandler

HIKE_BASE = "https://hike.taiwan.gov.tw"

DEFAULT_SUCCESS_MARKERS = ("申請成功", "申請編號", "完成申請")
DEFAULT_FAILURE_MARKERS = (
    "已額滿",
    "申請失敗",
    "VIEWSTATE",
    "驗證碼錯誤",
    "尚未開放",
    "驗證失敗",
)
CONFIRM_PAGE_MARKERS = ("請確認資料正確無誤後", "btnsave", "再次確認", "確認送出")

STEP2_SUBMIT_BUTTON = "ctl00$con$btnsetp2upnext"
STEP3_SUBMIT_BUTTON = "ctl00$con$btnsave"
STEP3_BACK_BUTTON = "ctl00$con$btnstep3uppre"

VCODE2_FIELD = "ctl00$con$vcode2"          # step 2 CAPTCHA input
VCODE3_FIELD = "ctl00$con$vcode"            # step 3 CAPTCHA input

APPLY_1_2_BTNAGREE = "ctl00$con$btnagree"


@dataclass
class HikeAspnetConfig:
    route_id: str
    route_code: int         # apply_1.aspx dropdown value (= cid in URL)
    unit: str               # UUID — 國家公園系列在 apply_1.aspx 選路線後跳轉帶
    fid: int
    camp_id: int = 0

    @property
    def cid(self) -> int:
        return self.route_code

    @property
    def apply_1_2_url(self) -> str:
        return (
            f"{HIKE_BASE}/apply_1_2.aspx?unit={self.unit}"
            f"&cid={self.cid}&fid={self.fid}&camp_id={self.camp_id}"
        )


@dataclass
class FormState:
    url: str
    html: str
    viewstate: str
    viewstate_generator: str
    event_validation: str
    viewstate_encrypted: str = ""
    hidden_inputs: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_html(cls, html_text: str, url: str) -> "FormState":
        vs = parse_viewstate(html_text)
        return cls(
            url=url,
            html=html_text,
            viewstate=vs.viewstate,
            viewstate_generator=vs.viewstate_generator,
            event_validation=vs.event_validation,
            hidden_inputs=parse_all_hidden_inputs(html_text),
        )

    def base_payload(self) -> dict[str, str]:
        return {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": self.viewstate,
            "__VIEWSTATEGENERATOR": self.viewstate_generator,
            "__VIEWSTATEENCRYPTED": self.viewstate_encrypted,
            "__EVENTVALIDATION": self.event_validation,
        }


def _person_fields(prefix: str, m: Member) -> dict[str, str]:
    """Build form fields shared by 申請人 / 領隊 / 留守人 (apply_*/leader_*/stay_*)."""
    return {
        f"{prefix}_name": m.name,
        f"{prefix}_tel": m.tel,
        f"{prefix}_addr": m.addr,
        f"{prefix}_mobile": m.phone,
        f"{prefix}_fax": m.fax,
        f"{prefix}_email": m.email,
        f"{prefix}_nation": m.nation,
        f"{prefix}_sid": m.id_number,
        f"{prefix}_sex": m.sex,
        f"{prefix}_birthday": m.birthday.isoformat(),
        f"{prefix}_contactname": m.contact_name,
        f"{prefix}_contacttel": m.contact_tel,
    }


def _person_country_city(prefix: str, m: Member) -> dict[str, str]:
    """ctl00$con$ddl{prefix}_country / city — must keep ctl00$con$ prefix."""
    return {
        f"ctl00$con$ddl{prefix}_country": m.country_code,
        f"ctl00$con$ddl{prefix}_city": m.city_code,
    }


def _ctl(name: str) -> str:
    return f"ctl00$con${name}"


def _member_fields(idx: int, m: Member) -> dict[str, str]:
    """lisMem repeater: ctl00$con$lisMem$ctrl{idx}$<field>."""
    p = f"ctl00$con$lisMem$ctrl{idx}"
    return {
        f"{p}$num": str(idx),
        f"{p}$m_id": "0",
        f"{p}$member_name": m.name,
        f"{p}$member_tel": m.tel,
        f"{p}$ddlmember_country": m.country_code,
        f"{p}$ddlmember_city": m.city_code,
        f"{p}$member_addr": m.addr,
        f"{p}$member_mobile": m.phone,
        f"{p}$member_email": m.email,
        f"{p}$member_nation": m.nation,
        f"{p}$member_sid": m.id_number,
        f"{p}$member_sex": m.sex,
        f"{p}$member_birthday": m.birthday.isoformat(),
        f"{p}$member_contactname": m.contact_name,
        f"{p}$member_contacttel": m.contact_tel,
    }


def _daybed_fields(day_beds: list) -> dict[str, str]:
    """lisText repeater: ctl00$con$lisText$ctrl{day}$<field>."""
    out: dict[str, str] = {}
    for db in day_beds:
        p = f"ctl00$con$lisText$ctrl{db.day_index}"
        out[f"{p}$num"] = str(db.num)
        out[f"{p}$bedok"] = "1" if db.bedok else "0"
        out[f"{p}$bakroomok"] = "1" if db.bakroomok else "0"
        out[f"{p}$rooms"] = str(db.rooms)
    return out


class HikeAspnetHandler(RouteHandler):
    def __init__(self, config: HikeAspnetConfig) -> None:
        self.config = config
        self.route_id = config.route_id
        self.form_url = config.apply_1_2_url
        self.submit_url = config.apply_1_2_url  # placeholder; real URL comes from 302

    # ============ 2-step API ============

    async def fetch_apply_1_2(self, client: httpx.AsyncClient) -> FormState:
        url = self.config.apply_1_2_url
        response = await client.get(url, headers={"Referer": f"{HIKE_BASE}/apply_1.aspx"})
        response.raise_for_status()
        return FormState.from_html(response.text, url)

    async def submit_apply_1_2(
        self,
        client: httpx.AsyncClient,
        state: FormState,
        agree_check_indices: list[int] | None = None,
    ) -> str:
        """POST 同意條款 + 日期 checkboxes → 跟 302 → 回 apply_1_3 URL（含 RandomStr）."""
        payload: list[tuple[str, str]] = list(state.base_payload().items())
        payload.append(("ctl00$googletxt", ""))
        # RECON_TODO: chk[] 對應哪些日期/條款的 value 待 recon HAR 比對；先全勾 "on"
        for _ in (agree_check_indices or range(20)):
            payload.append(("chk[]", "on"))
        payload.append((APPLY_1_2_BTNAGREE, "我同意"))

        response = await client.post(
            self.config.apply_1_2_url,
            content=_urlencode_pairs(payload),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": self.config.apply_1_2_url,
                "Origin": HIKE_ORIGIN,
            },
            follow_redirects=False,
        )
        if response.status_code != 302:
            raise RuntimeError(
                f"apply_1_2 POST 預期 302，實際 {response.status_code}：{response.text[:200]}"
            )
        location = response.headers.get("location", "")
        if not location:
            raise RuntimeError("apply_1_2 302 沒帶 Location header")
        if location.startswith("/"):
            location = HIKE_BASE + location
        return location

    async def fetch_apply_1_3(self, client: httpx.AsyncClient, url: str) -> FormState:
        response = await client.get(url, headers={"Referer": self.config.apply_1_2_url})
        response.raise_for_status()
        return FormState.from_html(response.text, url)

    def build_step2_payload(
        self, state: FormState, params: BookingParams, vcode2: str
    ) -> dict[str, str]:
        """填表 step 2：申請人/領隊/隊員/留守人/床位 + btnsetp2upnext + vcode2."""
        payload = state.base_payload()
        # 預設 EVENTTARGET 空字串 = 真實 form submit
        payload["ctl00$googletxt"] = ""

        leader = params.leader
        applicant = params.applicant or leader
        same_as_applicant = params.applicant is None

        # 申請人
        payload.update(_person_fields("ctl00$con$apply", applicant))
        payload.update(_person_country_city("apply", applicant))
        # copyapply 勾選 → 表單複製到領隊；不勾則領隊獨立填
        payload[_ctl("copyapply")] = "on" if same_as_applicant else ""

        # 領隊
        payload.update(_person_fields("ctl00$con$leader", leader))
        payload.update(_person_country_city("leader", leader))

        # 隊員（lisMem repeater）
        for idx, m in enumerate(params.members, start=1):
            payload.update(_member_fields(idx, m))

        # 留守人
        if params.stay:
            payload.update(_person_fields("ctl00$con$stay", params.stay))
        else:
            # stay 欄位仍須在 payload，但留空
            for k in ("stay_name", "stay_tel", "stay_addr", "stay_mobile", "stay_fax",
                     "stay_email", "stay_nation", "stay_sid", "stay_sex",
                     "stay_birthday", "stay_contactname", "stay_contacttel"):
                payload[_ctl(k)] = ""

        # 隊伍 + 行程基本資料
        payload[_ctl("teams_name")] = params.team_name or leader.name + "隊"
        payload[_ctl("teams_count")] = str(params.people)
        payload[_ctl("climbline")] = str(self.config.route_code)
        payload[_ctl("climblinemain")] = ""  # RECON_TODO
        payload[_ctl("sumday")] = str(params.nights + 1)
        payload[_ctl("sumdays")] = str(params.nights + 1)
        payload[_ctl("applystart")] = params.start_date.isoformat()
        payload[_ctl("setapply_date")] = params.start_date.isoformat()
        # setapply_outdate：入山日 + nights
        from datetime import timedelta
        payload[_ctl("setapply_outdate")] = (
            params.start_date + timedelta(days=params.nights)
        ).isoformat()

        payload[_ctl("seminar")] = params.seminar
        payload[_ctl("satellitephone")] = params.satellite_phone
        payload[_ctl("frequency")] = params.radio_frequency
        payload[_ctl("note_user")] = params.note
        payload[_ctl("member_keytype")] = "1"  # RECON_TODO: 1 = 手動輸入？

        # 床位
        payload.update(_daybed_fields(params.day_beds))

        # 同意聲明
        payload[_ctl("applycheck")] = "on" if params.agree_terms else ""

        # CAPTCHA
        payload[VCODE2_FIELD] = vcode2

        # GUID 透傳（從 form state 抓）
        payload[_ctl("Guid_Id")] = state.hidden_inputs.get(_ctl("Guid_Id"), "")
        payload[_ctl("hA_id")] = state.hidden_inputs.get(_ctl("hA_id"), "")

        # 一些 hidden state — 透傳
        for hid in (
            "hidapplystart", "hidnowday", "hidnowdaycount", "hidarrayid",
            "hidtype", "Hidfinish", "hidchange", "hidclickmember",
            "hidfinalid", "Literal1",
        ):
            payload[_ctl(hid)] = state.hidden_inputs.get(_ctl(hid), "")

        # 送出鈕：value = "下一步"（會被 server 認得）
        payload[STEP2_SUBMIT_BUTTON] = "下一步"
        return payload

    async def submit_step2(
        self, client: httpx.AsyncClient, url: str, payload: dict[str, str]
    ) -> FormState:
        """POST 表單到 apply_1_3.aspx → 回 step 3「再次確認」頁."""
        response = await client.post(
            url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": url,
                "Origin": HIKE_ORIGIN,
            },
            follow_redirects=False,
        )
        response.raise_for_status()
        return FormState.from_html(response.text, url)

    def build_step3_payload(
        self, state3: FormState, vcode: str
    ) -> dict[str, str]:
        """再次確認 step 3：vcode + btnsave。其他欄位由 viewstate 帶."""
        payload = state3.base_payload()
        payload["ctl00$googletxt"] = ""
        payload[_ctl("Guid_Id")] = state3.hidden_inputs.get(_ctl("Guid_Id"), "")
        payload[_ctl("hA_id")] = state3.hidden_inputs.get(_ctl("hA_id"), "")
        payload[_ctl("hidapplystart")] = state3.hidden_inputs.get(_ctl("hidapplystart"), "")
        payload[VCODE3_FIELD] = vcode
        payload[STEP3_SUBMIT_BUTTON] = "確認送出"
        return payload

    async def submit_step3(
        self, client: httpx.AsyncClient, url: str, payload: dict[str, str]
    ) -> BookingResult:
        response = await client.post(
            url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": url,
                "Origin": HIKE_ORIGIN,
            },
            follow_redirects=False,
        )
        return self.parse_result(response.text, response.status_code)

    # ============ Legacy RouteHandler interface (synthetic test only) ============

    async def fetch_form_state(self, client: httpx.AsyncClient) -> dict:
        state = await self.fetch_apply_1_2(client)
        return {"url": state.url, "html": state.html, "_form_state": state}

    def build_payload(self, state: dict, params: BookingParams) -> dict:
        # Synthetic single-shot for tests: build step2 payload with empty vcode
        fs: FormState = state["_form_state"]
        return self.build_step2_payload(fs, params, vcode2="")

    def parse_result(self, html: str, http_status: int) -> BookingResult:
        booking_id = _extract_booking_id(html)
        is_confirm_page = any(m in html for m in CONFIRM_PAGE_MARKERS)
        success_hit = next((m for m in DEFAULT_SUCCESS_MARKERS if m in html), None)
        failure_hit = next((m for m in DEFAULT_FAILURE_MARKERS if m in html), None)

        if success_hit:
            return BookingResult(
                success=True,
                booking_id=booking_id,
                raw_html=html,
                http_status=http_status,
                confirmation_required=False,
            )
        if failure_hit:
            return BookingResult(
                success=False,
                booking_id=None,
                raw_html=html,
                error_message=failure_hit,
                http_status=http_status,
            )
        if is_confirm_page:
            return BookingResult(
                success=False,
                booking_id=None,
                raw_html=html,
                http_status=http_status,
                confirmation_required=True,
            )
        return BookingResult(
            success=False,
            booking_id=None,
            raw_html=html,
            error_message=f"unknown response (status={http_status})",
            http_status=http_status,
        )

    async def confirm_if_needed(
        self,
        client: httpx.AsyncClient,
        result: BookingResult,
        params: BookingParams,
    ) -> BookingResult:
        # 半自動流程：step 3 確認需要 user 解新的 CAPTCHA。Legacy 路徑無法自動處理。
        if not result.confirmation_required:
            return result
        raise NotImplementedError(
            "Step 3 (再次確認) 需要新的 CAPTCHA (vcode)，半自動流程須由 caller 解碼後呼叫 "
            "build_step3_payload + submit_step3。Legacy confirm_if_needed 不支援。"
        )


def _extract_booking_id(html: str) -> str | None:
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return None
    candidates = tree.xpath(
        "//*[contains(text(), '申請編號')]/following-sibling::*[1]/text() | "
        "//*[contains(text(), '申請編號')]/text()"
    )
    for raw in candidates:
        cleaned = raw.replace("申請編號", "").strip(" :：\n\t")
        if cleaned:
            return cleaned
    return None


def _urlencode_pairs(pairs: list[tuple[str, str]]) -> str:
    """urlencode preserving multiple values per key (e.g. chk[] arrays)."""
    from urllib.parse import quote_plus

    return "&".join(f"{quote_plus(k)}={quote_plus(v)}" for k, v in pairs)
