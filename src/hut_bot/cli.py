from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import typer

from .auth.playwright_login import interactive_login
from .config import load_settings
from .grabber.client import HIKE_ORIGIN, build_client, warm_up
from .grabber.viewstate import parse_all_hidden_inputs, parse_viewstate
from .logging_setup import setup_logging

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


@app.command("dry-run")
def dry_run(
    route: str = typer.Option(..., "--route", "-r"),
    start_date: datetime = typer.Option(..., "--start-date"),
    nights: int = typer.Option(1, "--nights"),
    people: int = typer.Option(1, "--people"),
) -> None:
    """完整跑 GET → 組 payload → 印出但不真的 POST。Phase 2 後才能實作。"""
    typer.echo("[stub] dry-run 尚未實作 — 等 Phase 2 完成 hike_aspnet handler 後再啟用")
    raise typer.Exit(code=2)


@app.command()
def grab(
    route: str = typer.Option(..., "--route", "-r"),
    start_date: datetime = typer.Option(..., "--start-date"),
    nights: int = typer.Option(1, "--nights"),
    people: int = typer.Option(1, "--people"),
) -> None:
    """立即搶（debug 用）。Phase 3 後才能實作。"""
    typer.echo("[stub] grab 尚未實作 — 等 Phase 3 完成搶票主迴圈後再啟用")
    raise typer.Exit(code=2)


@app.command()
def schedule(
    route: str = typer.Option(..., "--route", "-r"),
    start_date: datetime = typer.Option(..., "--start-date"),
    nights: int = typer.Option(1, "--nights"),
    people: int = typer.Option(1, "--people"),
) -> None:
    """常駐排程：每天 06:59:50 預熱 → 07:00:00.000 觸發。Phase 4 後才能實作。"""
    typer.echo("[stub] schedule 尚未實作 — 等 Phase 4 完成排程整合後再啟用")
    raise typer.Exit(code=2)


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
