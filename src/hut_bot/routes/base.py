from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import httpx


@dataclass(frozen=True)
class Member:
    name: str
    id_number: str           # 身分證字號 (sid)
    phone: str               # 手機 (mobile) — 10 碼
    birthday: date
    sex: str = "M"           # 真實表單值可能是 "男"/"女" 或 "M"/"F"，待 Phase 1 確認
    email: str = ""
    addr: str = ""           # 地址
    tel: str = ""            # 市話 (tel)
    fax: str = ""
    nation: str = ""         # 國籍 UUID（中華民國 = 特定 UUID，待 recon）
    country_code: str = ""   # ddl 國別 code 例如 "TW"
    city_code: str = ""      # ddl 城市 code 例如 "Taipei"
    contact_name: str = ""   # 緊急聯絡人姓名
    contact_tel: str = ""    # 緊急聯絡人電話


@dataclass(frozen=True)
class DayBed:
    day_index: int           # 第幾天（1 起）
    num: int = 1             # 人數
    bedok: bool = True       # 床位是否需要
    bakroomok: bool = True   # 備用房是否可
    rooms: int = 0           # 房間數


@dataclass(frozen=True)
class BookingParams:
    start_date: date
    nights: int
    people: int
    leader: Member
    members: list[Member] = field(default_factory=list)
    agree_terms: bool = True

    applicant: Member | None = None       # 申請人（不填則 = 領隊，搭配 copyapply=on）
    stay: Member | None = None             # 留守人
    team_name: str = ""                    # 隊伍名稱
    seminar: str = ""                      # 研習證明
    satellite_phone: str = ""
    radio_frequency: str = ""
    note: str = ""
    day_beds: list[DayBed] = field(default_factory=list)


@dataclass
class BookingResult:
    success: bool
    booking_id: str | None
    raw_html: str
    error_message: str | None = None
    confirmation_required: bool = False
    http_status: int | None = None


class RouteHandler(ABC):
    """Legacy single-shot handler — kept for poster.py / scheduling 兼容。

    新 2-step 流程的 hike.taiwan.gov.tw 在 HikeAspnetHandler 用獨立方法暴露
    （fetch_apply_1_3 / build_step2_payload / submit_step2 / build_step3_payload
    / submit_step3），半自動 orchestration 直接用那些。本 ABC 走「全部 bot 自己跑」
    的舊路徑——對需要 CAPTCHA 的真實流程沒用，但 synthetic test 仍依賴。
    """

    route_id: str
    form_url: str
    submit_url: str

    @abstractmethod
    async def fetch_form_state(self, client: httpx.AsyncClient) -> dict: ...

    @abstractmethod
    def build_payload(self, state: dict, params: BookingParams) -> dict: ...

    @abstractmethod
    def parse_result(self, html: str, http_status: int) -> BookingResult: ...

    @abstractmethod
    async def confirm_if_needed(
        self,
        client: httpx.AsyncClient,
        result: BookingResult,
        params: BookingParams,
    ) -> BookingResult: ...
