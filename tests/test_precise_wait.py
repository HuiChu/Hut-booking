from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from hut_bot.scheduling.precise_wait import next_occurrence, wait_until


def test_next_occurrence_returns_future_time() -> None:
    target = next_occurrence(7, 0, 0)
    assert target > datetime.now()
    assert target.hour == 7
    assert target.minute == 0
    assert target.second == 0


@pytest.mark.asyncio
async def test_wait_until_hits_target_within_50ms() -> None:
    target = datetime.now() + timedelta(milliseconds=300)
    with patch("hut_bot.scheduling.precise_wait.get_ntp_offset", return_value=0.0):
        actual = await wait_until(target, spin_threshold_ms=50.0)
    delta_ms = (actual - target).total_seconds() * 1000
    assert -1.0 <= delta_ms <= 50.0, f"Δ={delta_ms:.2f}ms outside ±50ms window"


@pytest.mark.asyncio
async def test_wait_until_returns_immediately_for_past_target() -> None:
    target = datetime.now() - timedelta(seconds=1)
    with patch("hut_bot.scheduling.precise_wait.get_ntp_offset", return_value=0.0):
        actual = await wait_until(target)
    assert actual >= target
