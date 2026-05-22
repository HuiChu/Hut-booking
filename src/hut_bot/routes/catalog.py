from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .base import RouteHandler
from .destinations import RouteDestination, load_destinations
from .discovery import DiscoveredRoute, load_routes_yaml
from .hike_aspnet import HikeAspnetConfig, HikeAspnetHandler

DEFAULT_ROUTES_YAML = Path("config/routes.yaml")
DEFAULT_DESTINATIONS_YAML = Path("config/routes_destinations.yaml")

_SYNTHETIC_CONFIG = HikeAspnetConfig(
    route_id="synthetic",
    route_code=2,
    unit="00000000-0000-0000-0000-000000000000",
    fid=0,
    camp_id=0,
)


@lru_cache(maxsize=1)
def _discovered_routes() -> dict[str, DiscoveredRoute]:
    if not DEFAULT_ROUTES_YAML.exists():
        return {}
    return {r.route_id: r for r in load_routes_yaml(DEFAULT_ROUTES_YAML)}


@lru_cache(maxsize=1)
def _destinations() -> dict[str, RouteDestination]:
    return load_destinations(DEFAULT_DESTINATIONS_YAML)


def list_routes() -> list[str]:
    return sorted({"synthetic", *_discovered_routes().keys()})


def list_configured_routes() -> list[str]:
    """已有 destination（可實際送出）的路線 id。"""
    return sorted({"synthetic", *_destinations().keys()})


def get_handler(route_id: str) -> RouteHandler:
    if route_id == "synthetic":
        return HikeAspnetHandler(_SYNTHETIC_CONFIG)

    routes = _discovered_routes()
    if route_id not in routes:
        raise KeyError(
            f"Unknown route_id={route_id!r}. "
            f"先跑 `uv run hut-bot discover` 產生 config/routes.yaml，"
            f"或用 `uv run hut-bot list-routes` 查可用 route_id。"
        )

    dests = _destinations()
    if route_id not in dests:
        raise NotImplementedError(
            f"Route {route_id!r} (code={routes[route_id].code}) 尚未在 "
            f"config/routes_destinations.yaml 設定 unit/fid。請登入後從 "
            f"apply_1.aspx 選此路線、記下跳轉的 unit/cid/fid，補進該檔。"
        )
    d = dests[route_id]
    config = HikeAspnetConfig(
        route_id=route_id,
        route_code=d.route_code,
        unit=d.unit,
        fid=d.fid,
        camp_id=d.camp_id,
    )
    return HikeAspnetHandler(config)
