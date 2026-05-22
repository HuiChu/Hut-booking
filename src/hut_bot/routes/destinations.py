from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RouteDestination:
    route_id: str
    subsystem: str
    route_code: int
    unit: str
    fid: int
    camp_id: int = 0


def load_destinations(path: Path) -> dict[str, RouteDestination]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("destinations") or {}
    out: dict[str, RouteDestination] = {}
    for route_id, fields in raw.items():
        out[route_id] = RouteDestination(
            route_id=route_id,
            subsystem=str(fields.get("subsystem", "national_park")),
            route_code=int(fields["route_code"]),
            unit=str(fields["unit"]),
            fid=int(fields["fid"]),
            camp_id=int(fields.get("camp_id", 0)),
        )
    return out
