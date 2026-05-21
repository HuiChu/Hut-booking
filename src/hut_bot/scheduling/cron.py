from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..grabber.client import HIKE_ORIGIN, build_client, warm_up
from ..grabber.poster import grab_until
from ..routes.base import BookingParams
from ..routes.catalog import get_handler
from .precise_wait import wait_until

log = structlog.get_logger(__name__)


async def run_one_shot(
    route_id: str,
    params: BookingParams,
    auth_state_path,
    *,
    target: datetime,
    deadline: datetime,
    ntp_server: str = "time.stdtime.gov.tw",
    warmup_url: str = HIKE_ORIGIN + "/",
) -> None:
    """Pre-warm → wait_until(target) → grab_until(deadline) for a single occurrence."""
    handler = get_handler(route_id)
    async with build_client(auth_state_path) as client:
        log.info("schedule.warmup.start", url=warmup_url)
        await warm_up(client, warmup_url)
        log.info("schedule.wait_until.target", target=target.isoformat())
        actual = await wait_until(target, ntp_server=ntp_server)
        log.info(
            "schedule.fire",
            target=target.isoformat(),
            actual=actual.isoformat(),
            delta_ms=round((actual - target).total_seconds() * 1000, 2),
        )
        result = await grab_until(handler, client, params, deadline=deadline)
        log.info(
            "schedule.result",
            route=route_id,
            success=result.success,
            booking_id=result.booking_id,
            error=result.error_message,
            http_status=result.http_status,
        )


def _next_open_time(hour: int, minute: int, second: int) -> datetime:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def run_daily_schedule(
    route_id: str,
    params: BookingParams,
    auth_state_path,
    *,
    open_hour: int = 7,
    open_minute: int = 0,
    open_second: int = 0,
    retry_window_seconds: int = 60,
    warmup_lead_seconds: int = 10,
    ntp_server: str = "time.stdtime.gov.tw",
) -> None:
    """Run a daemon that fires `run_one_shot` every day at the configured open time.

    Each day APScheduler triggers `warmup_lead_seconds` before the open time;
    the job then precise-waits to the exact second and retries until
    `retry_window_seconds` after the open time.
    """
    scheduler = AsyncIOScheduler()

    async def job() -> None:
        target = datetime.now().replace(
            hour=open_hour, minute=open_minute, second=open_second, microsecond=0
        )
        if target < datetime.now() - timedelta(seconds=warmup_lead_seconds + 5):
            target += timedelta(days=1)
        deadline = target + timedelta(seconds=retry_window_seconds)
        await run_one_shot(
            route_id,
            params,
            auth_state_path,
            target=target,
            deadline=deadline,
            ntp_server=ntp_server,
        )

    pre_trigger_seconds = (open_second - warmup_lead_seconds) % 60
    pre_trigger_minute = open_minute - (1 if open_second - warmup_lead_seconds < 0 else 0)
    pre_trigger_hour = open_hour - (1 if pre_trigger_minute < 0 else 0)
    pre_trigger_minute %= 60
    pre_trigger_hour %= 24

    scheduler.add_job(
        job,
        CronTrigger(
            hour=pre_trigger_hour,
            minute=pre_trigger_minute,
            second=pre_trigger_seconds,
        ),
        id=f"grab_{route_id}",
        name=f"Daily grab for {route_id}",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    log.info(
        "schedule.started",
        route=route_id,
        open_time=f"{open_hour:02d}:{open_minute:02d}:{open_second:02d}",
        pre_trigger=f"{pre_trigger_hour:02d}:{pre_trigger_minute:02d}:{pre_trigger_seconds:02d}",
        next_target=_next_open_time(open_hour, open_minute, open_second).isoformat(),
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("schedule.shutdown")
        scheduler.shutdown(wait=False)
