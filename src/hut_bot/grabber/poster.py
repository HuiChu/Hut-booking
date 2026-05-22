from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
import structlog

from ..routes.base import BookingParams, BookingResult, RouteHandler
from .client import HIKE_ORIGIN

log = structlog.get_logger(__name__)

POST_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": HIKE_ORIGIN,
}


async def post_once(
    handler: RouteHandler,
    client: httpx.AsyncClient,
    params: BookingParams,
) -> BookingResult:
    """Single round-trip: GET form to refresh viewstate → POST → parse → maybe confirm."""
    state = await handler.fetch_form_state(client)
    payload = handler.build_payload(state, params)

    headers: dict[str, Any] = {**POST_HEADERS, "Referer": handler.form_url}
    response = await client.post(handler.submit_url, data=payload, headers=headers)
    result = handler.parse_result(response.text, response.status_code)
    if result.confirmation_required:
        result = await handler.confirm_if_needed(client, result, params)
    return result


async def grab_until(
    handler: RouteHandler,
    client: httpx.AsyncClient,
    params: BookingParams,
    deadline: datetime,
    *,
    retry_backoff: float = 0.0,
) -> BookingResult:
    """Retry post_once until success or wall-clock passes deadline.

    Each attempt re-fetches the form state so __VIEWSTATE / __EVENTVALIDATION
    are always fresh (ASP.NET rejects reused values).
    """
    attempt = 0
    last_result: BookingResult | None = None

    while datetime.now() < deadline:
        attempt += 1
        started = datetime.now()
        try:
            last_result = await post_once(handler, client, params)
        except httpx.HTTPError as exc:
            log.warning(
                "grab.attempt.http_error",
                route=handler.route_id,
                attempt=attempt,
                error=str(exc),
            )
            if retry_backoff > 0:
                await asyncio.sleep(retry_backoff)
            continue

        elapsed_ms = (datetime.now() - started).total_seconds() * 1000
        log.info(
            "grab.attempt",
            route=handler.route_id,
            attempt=attempt,
            success=last_result.success,
            booking_id=last_result.booking_id,
            error=last_result.error_message,
            http_status=last_result.http_status,
            elapsed_ms=round(elapsed_ms, 2),
        )

        if last_result.success:
            return last_result
        if retry_backoff > 0:
            await asyncio.sleep(retry_backoff)

    if last_result is None:
        return BookingResult(
            success=False,
            booking_id=None,
            raw_html="",
            error_message="deadline reached before any attempt completed",
        )
    return last_result


async def dry_run_once(
    handler: RouteHandler,
    client: httpx.AsyncClient,
    params: BookingParams,
) -> dict[str, Any]:
    """Fetch form state and build payload, but DO NOT POST. Returns the would-be payload."""
    state = await handler.fetch_form_state(client)
    payload = handler.build_payload(state, params)
    return {
        "form_url": handler.form_url,
        "submit_url": handler.submit_url,
        "fetched_url": state.get("url"),
        "payload": payload,
    }
