from datetime import datetime

from hut_bot.scheduling.cron import _next_open_time


def test_next_open_time_is_in_future() -> None:
    target = _next_open_time(7, 0, 0)
    assert target > datetime.now()
    assert target.hour == 7
    assert target.minute == 0
    assert target.second == 0


def test_next_open_time_today_if_still_ahead_else_tomorrow() -> None:
    now = datetime.now()
    target = _next_open_time(now.hour, now.minute, (now.second + 30) % 60)
    delta = (target - now).total_seconds()
    assert 0 < delta < 24 * 3600
