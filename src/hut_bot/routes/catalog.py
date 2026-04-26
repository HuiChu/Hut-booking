from __future__ import annotations

from .base import RouteHandler
from .hike_aspnet import HikeAspnetConfig, HikeAspnetHandler

# RECON_TODO: 路線目錄。每條路線的 form_url / submit_url / route_value
# 必須在 Phase 1 recon 後從真實 hike.taiwan.gov.tw 抓回，現在的值是合成 placeholder。

_ROUTE_CONFIGS: dict[str, HikeAspnetConfig] = {
    "yunleng": HikeAspnetConfig(
        route_id="yunleng",
        route_value="ROUTE_002",  # RECON_TODO
        form_url="https://hike.taiwan.gov.tw/applySearch.aspx",  # RECON_TODO
        submit_url="https://hike.taiwan.gov.tw/applySearch.aspx",  # RECON_TODO
    ),
    "synthetic": HikeAspnetConfig(
        route_id="synthetic",
        route_value="ROUTE_002",
        form_url="file://synthetic_aspnet_form.html",
        submit_url="file://synthetic_aspnet_form.html",
    ),
}


def get_handler(route_id: str) -> RouteHandler:
    if route_id not in _ROUTE_CONFIGS:
        raise KeyError(
            f"Unknown route_id={route_id!r}. Known: {sorted(_ROUTE_CONFIGS)}. "
            f"Add it in src/hut_bot/routes/catalog.py after Phase 1 recon."
        )
    return HikeAspnetHandler(_ROUTE_CONFIGS[route_id])


def list_routes() -> list[str]:
    return sorted(_ROUTE_CONFIGS)
