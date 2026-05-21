from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

import typer

from .auth.playwright_login import interactive_login
from .config import Settings, load_settings
from .grabber.client import HIKE_ORIGIN, build_client, warm_up
from .grabber.poster import dry_run_once, grab_until, post_once
from .grabber.viewstate import parse_all_hidden_inputs, parse_viewstate
from .logging_setup import setup_logging
from .routes.base import BookingParams, Member
from .routes.catalog import get_handler, list_routes

app = typer.Typer(add_completion=False, help="Taiwan hut booking bot CLI")


@app.command()
def login() -> None:
    """互動登入 hike.taiwan.gov.tw，匯出 storage_state.json"""
    settings = load_settings()
    setup_logging(settings.log_level, settings.logs_dir)
    asyncio.run(
        interactive_login(
            settings.auth_state_path,
            username=settings.hike_username,
            password=settings.hike_password,
        )
    )


CANDIDATE_RECON_URLS: dict[str, str] = {
    "home": "https://hike.taiwan.gov.tw/",
    "apply_1": "https://hike.taiwan.gov.tw/apply_1.aspx?search=2",
    "applySearch": "https://hike.taiwan.gov.tw/applySearch.aspx",
    "apply_3": "https://hike.taiwan.gov.tw/apply_3.aspx",
    "bed_0": "https://hike.taiwan.gov.tw/bed_0.aspx",
}


@app.command()
def recon(
    url: str = typer.Option(..., "--url", "-u", help="要抓的表單頁完整 URL"),
    name: str = typer.Option(..., "--name", "-n", help="存檔名稱（無副檔名）"),
) -> None:
    """Phase 1 必經：抓指定表單頁、印出所有 form fields、HTML 存到 storage/form_fixtures/"""
    settings = load_settings()
    log = setup_logging(settings.log_level, settings.logs_dir)

    async def run() -> None:
        async with build_client(settings.auth_state_path) as client:
            response = await client.get(url, headers={"Referer": HIKE_ORIGIN + "/"})
            response.raise_for_status()
            html_text = response.text

            fixture_path = settings.fixtures_dir / f"{name}.html"
            fixture_path.write_text(html_text, encoding="utf-8")

            hidden = parse_all_hidden_inputs(html_text)
            viewstate = parse_viewstate(html_text)

            log.info(
                "recon.fetched",
                url=url,
                status=response.status_code,
                length=len(html_text),
                fixture=str(fixture_path),
                hidden_count=len(hidden),
                has_viewstate=bool(viewstate.viewstate),
                has_event_validation=bool(viewstate.event_validation),
            )

            typer.echo(f"\n=== Hidden inputs ({len(hidden)}) ===")
            for k, v in hidden.items():
                preview = v if len(v) <= 60 else v[:57] + "..."
                typer.echo(f"  {k} = {preview}")

            typer.echo(f"\n=== ViewState 摘要 ===")
            typer.echo(f"  __VIEWSTATE         len={len(viewstate.viewstate)}")
            typer.echo(f"  __VIEWSTATEGENERATOR len={len(viewstate.viewstate_generator)}")
            typer.echo(f"  __EVENTVALIDATION   len={len(viewstate.event_validation)}")
            typer.echo(f"\nHTML 已存到 {fixture_path}")

    asyncio.run(run())


@app.command("recon-batch")
def recon_batch() -> None:
    """批次抓所有候選 URL，存到 storage/form_fixtures/。需先 hut-bot login。"""
    settings = load_settings()
    log = setup_logging(settings.log_level, settings.logs_dir)

    async def run() -> None:
        async with build_client(settings.auth_state_path) as client:
            for name, target_url in CANDIDATE_RECON_URLS.items():
                try:
                    response = await client.get(target_url, headers={"Referer": HIKE_ORIGIN + "/"})
                    fixture_path = settings.fixtures_dir / f"{name}.html"
                    fixture_path.write_text(response.text, encoding="utf-8")
                    hidden = parse_all_hidden_inputs(response.text)
                    viewstate = parse_viewstate(response.text)
                    log.info(
                        "recon_batch.fetched",
                        name=name,
                        url=target_url,
                        status=response.status_code,
                        length=len(response.text),
                        hidden_count=len(hidden),
                        has_viewstate=bool(viewstate.viewstate),
                    )
                    typer.echo(
                        f"[{name}] {response.status_code} len={len(response.text)} "
                        f"hidden={len(hidden)} → {fixture_path}"
                    )
                except Exception as exc:
                    log.error("recon_batch.failed", name=name, url=target_url, error=str(exc))
                    typer.echo(f"[{name}] FAILED: {exc}")

    asyncio.run(run())


def _build_params_from_settings(
    settings: Settings,
    start_date: datetime,
    nights: int,
    people: int,
) -> BookingParams:
    missing = [
        name
        for name, val in (
            ("LEADER_NAME", settings.leader_name),
            ("LEADER_ID", settings.leader_id),
            ("LEADER_PHONE", settings.leader_phone),
            ("LEADER_BIRTHDAY", settings.leader_birthday),
        )
        if not val
    ]
    if missing:
        raise typer.BadParameter(f"請在 .env 設定：{', '.join(missing)}")

    leader = Member(
        name=settings.leader_name,
        id_number=settings.leader_id,
        phone=settings.leader_phone,
        birthday=settings.leader_birthday,
    )
    return BookingParams(
        start_date=start_date.date(),
        nights=nights,
        people=people,
        leader=leader,
        members=[],
    )


@app.command("list-routes")
def list_routes_cmd() -> None:
    """列出 catalog 已註冊的路線 ID。"""
    for route_id in list_routes():
        typer.echo(route_id)


@app.command("dry-run")
def dry_run(
    route: str = typer.Option(..., "--route", "-r"),
    start_date: datetime = typer.Option(..., "--start-date"),
    nights: int = typer.Option(1, "--nights"),
    people: int = typer.Option(1, "--people"),
) -> None:
    """完整跑 GET → 組 payload → 印出但不真的 POST。"""
    settings = load_settings()
    log = setup_logging(settings.log_level, settings.logs_dir)
    handler = get_handler(route)
    params = _build_params_from_settings(settings, start_date, nights, people)

    async def run() -> None:
        async with build_client(settings.auth_state_path) as client:
            report = await dry_run_once(handler, client, params)
            log.info(
                "dry_run.complete",
                route=route,
                form_url=report["form_url"],
                payload_keys=sorted(report["payload"].keys()),
            )
            typer.echo(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    asyncio.run(run())


@app.command()
def grab(
    route: str = typer.Option(..., "--route", "-r"),
    start_date: datetime = typer.Option(..., "--start-date"),
    nights: int = typer.Option(1, "--nights"),
    people: int = typer.Option(1, "--people"),
    deadline_minutes: int = typer.Option(
        1, "--deadline-minutes", help="從現在算起多少分鐘內持續重試"
    ),
    retry_backoff: float = typer.Option(0.0, "--retry-backoff"),
) -> None:
    """立即搶（debug 用）。會在 deadline_minutes 內持續重試直到成功。"""
    settings = load_settings()
    log = setup_logging(settings.log_level, settings.logs_dir)
    handler = get_handler(route)
    params = _build_params_from_settings(settings, start_date, nights, people)
    deadline = datetime.now() + timedelta(minutes=deadline_minutes)

    async def run() -> None:
        async with build_client(settings.auth_state_path) as client:
            await warm_up(client, HIKE_ORIGIN + "/")
            result = await grab_until(
                handler, client, params, deadline=deadline, retry_backoff=retry_backoff
            )
            log.info(
                "grab.complete",
                route=route,
                success=result.success,
                booking_id=result.booking_id,
                error=result.error_message,
                http_status=result.http_status,
            )
            typer.echo(
                json.dumps(
                    {
                        "success": result.success,
                        "booking_id": result.booking_id,
                        "error": result.error_message,
                        "http_status": result.http_status,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            raise typer.Exit(code=0 if result.success else 1)

    asyncio.run(run())


@app.command()
def schedule(
    route: str = typer.Option(..., "--route", "-r"),
    start_date: datetime = typer.Option(..., "--start-date"),
    nights: int = typer.Option(1, "--nights"),
    people: int = typer.Option(1, "--people"),
    open_hour: int = typer.Option(7, "--open-hour"),
    open_minute: int = typer.Option(0, "--open-minute"),
    open_second: int = typer.Option(0, "--open-second"),
    once: bool = typer.Option(False, "--once", help="只跑一次（下一個開放時段），不常駐"),
    retry_window_seconds: int = typer.Option(60, "--retry-window-seconds"),
) -> None:
    """常駐排程：每天 06:59:50 預熱 → 07:00:00.000 觸發 → 重試到 07:01:00。"""
    from .scheduling.cron import _next_open_time, run_daily_schedule, run_one_shot

    settings = load_settings()
    log = setup_logging(settings.log_level, settings.logs_dir)
    get_handler(route)  # validate route_id before scheduling
    params = _build_params_from_settings(settings, start_date, nights, people)

    if once:
        target = _next_open_time(open_hour, open_minute, open_second)
        deadline = target + timedelta(seconds=retry_window_seconds)
        log.info(
            "schedule.once",
            route=route,
            target=target.isoformat(),
            deadline=deadline.isoformat(),
        )
        asyncio.run(
            run_one_shot(
                route,
                params,
                settings.auth_state_path,
                target=target,
                deadline=deadline,
                ntp_server=settings.ntp_server,
            )
        )
    else:
        asyncio.run(
            run_daily_schedule(
                route,
                params,
                settings.auth_state_path,
                open_hour=open_hour,
                open_minute=open_minute,
                open_second=open_second,
                retry_window_seconds=retry_window_seconds,
                ntp_server=settings.ntp_server,
            )
        )


@app.command("precise-wait-test")
def precise_wait_test(
    seconds_from_now: int = typer.Option(10, "--in", help="幾秒後觸發"),
) -> None:
    """測試 precise_wait 整點命中精度。"""
    from datetime import timedelta

    from .scheduling.precise_wait import wait_until

    settings = load_settings()
    setup_logging(settings.log_level, settings.logs_dir)

    target = (datetime.now() + timedelta(seconds=seconds_from_now)).replace(microsecond=0)
    typer.echo(f"目標時間: {target.isoformat()}")

    async def run() -> None:
        actual = await wait_until(target, ntp_server=settings.ntp_server)
        delta_ms = (actual - target).total_seconds() * 1000
        typer.echo(f"實際命中: {actual.isoformat()}  Δ={delta_ms:+.2f}ms")

    asyncio.run(run())


if __name__ == "__main__":
    app()
