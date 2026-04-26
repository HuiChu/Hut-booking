from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta

import ntplib

SPIN_THRESHOLD_MS = 50.0


def get_ntp_offset(server: str = "time.stdtime.gov.tw", timeout: float = 2.0) -> float:
    """Return (server_time - local_time) in seconds. Returns 0.0 if NTP query fails."""
    try:
        client = ntplib.NTPClient()
        response = client.request(server, version=3, timeout=timeout)
        return float(response.offset)
    except Exception:
        return 0.0


def now_corrected(offset: float) -> datetime:
    return datetime.now() + timedelta(seconds=offset)


async def wait_until(
    target: datetime,
    *,
    ntp_server: str = "time.stdtime.gov.tw",
    spin_threshold_ms: float = SPIN_THRESHOLD_MS,
) -> datetime:
    """Sleep until `target` (local-naive datetime) with NTP correction and a busy-wait tail.

    Returns the actual corrected time at which the wait ended.
    """
    offset = get_ntp_offset(ntp_server)

    while True:
        corrected = now_corrected(offset)
        remaining = (target - corrected).total_seconds()
        if remaining <= 0:
            return corrected
        if remaining * 1000 <= spin_threshold_ms:
            break
        await asyncio.sleep(min(remaining - spin_threshold_ms / 1000, 1.0))

    deadline_perf = time.perf_counter() + remaining
    while time.perf_counter() < deadline_perf:
        pass
    return now_corrected(offset)


def next_occurrence(hour: int, minute: int = 0, second: int = 0) -> datetime:
    """Return the next datetime matching the given wall-clock time."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target
