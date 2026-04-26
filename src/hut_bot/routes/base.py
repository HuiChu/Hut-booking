from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import httpx


@dataclass(frozen=True)
class Member:
    name: str
    id_number: str
    phone: str
    birthday: date


@dataclass(frozen=True)
class BookingParams:
    start_date: date
    nights: int
    people: int
    leader: Member
    members: list[Member] = field(default_factory=list)
    agree_terms: bool = True


@dataclass
class BookingResult:
    success: bool
    booking_id: str | None
    raw_html: str
    error_message: str | None = None
    confirmation_required: bool = False
    http_status: int | None = None


class RouteHandler(ABC):
    route_id: str
    form_url: str
    submit_url: str

    @abstractmethod
    async def fetch_form_state(self, client: httpx.AsyncClient) -> dict:
        """GET 表單頁，回傳 hidden inputs / CSRF token 等送出時必須附帶的狀態。"""

    @abstractmethod
    def build_payload(self, state: dict, params: BookingParams) -> dict:
        """組 POST payload。state 是 fetch_form_state 的回傳值。"""

    @abstractmethod
    def parse_result(self, html: str, http_status: int) -> BookingResult:
        """解析 POST 回應 HTML，判斷成功/失敗、是否需要二次確認。"""

    @abstractmethod
    async def confirm_if_needed(
        self,
        client: httpx.AsyncClient,
        result: BookingResult,
        params: BookingParams,
    ) -> BookingResult:
        """若 result.confirmation_required，送出二次確認 POST。否則直接回傳 result。"""
