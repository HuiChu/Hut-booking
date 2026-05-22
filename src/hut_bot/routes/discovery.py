from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import yaml
from lxml import html as lxml_html

from ..grabber.client import HIKE_ORIGIN

APPLY_1_URL = "https://hike.taiwan.gov.tw/apply_1.aspx"
ROUTE_SELECT_NAME = "ctl00$con$line"

_DIFFICULTY_RE = re.compile(r"^\s*\(([0-9一二三四五六]+\s*級)\)\s*")
_NONWORD_RE = re.compile(r"[^\w一-鿿]+", re.UNICODE)


@dataclass
class DiscoveredRoute:
    code: str
    display_name: str
    route_id: str
    difficulty: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def slugify(text: str) -> str:
    stripped = _DIFFICULTY_RE.sub("", text)
    cleaned = _NONWORD_RE.sub("-", stripped).strip("-").lower()
    return cleaned[:80] or "route"


def parse_route_options(html_text: str) -> list[DiscoveredRoute]:
    tree = lxml_html.fromstring(html_text)
    selects = tree.xpath(f'//select[@name="{ROUTE_SELECT_NAME}"]')
    if not selects:
        return []

    seen_codes: set[str] = set()
    parsed: list[DiscoveredRoute] = []
    for opt in selects[0].xpath('./option'):
        code = (opt.get("value") or "").strip()
        if not code or code in seen_codes:
            continue
        name = (opt.text_content() or "").strip()
        if not name:
            continue

        difficulty_match = _DIFFICULTY_RE.match(name)
        difficulty = difficulty_match.group(1).replace(" ", "") if difficulty_match else None

        parsed.append(
            DiscoveredRoute(
                code=code,
                display_name=name,
                route_id=slugify(name),
                difficulty=difficulty,
            )
        )
        seen_codes.add(code)

    slug_counts: dict[str, int] = {}
    for r in parsed:
        slug_counts[r.route_id] = slug_counts.get(r.route_id, 0) + 1
    return [
        DiscoveredRoute(
            code=r.code,
            display_name=r.display_name,
            route_id=f"{r.route_id}-{r.code}" if slug_counts[r.route_id] > 1 else r.route_id,
            difficulty=r.difficulty,
        )
        for r in parsed
    ]


async def discover_routes(client: httpx.AsyncClient) -> list[DiscoveredRoute]:
    response = await client.get(APPLY_1_URL, headers={"Referer": HIKE_ORIGIN + "/"})
    response.raise_for_status()
    return parse_route_options(response.text)


def write_routes_yaml(routes: list[DiscoveredRoute], path: Path) -> None:
    data = {
        "source_url": APPLY_1_URL,
        "route_count": len(routes),
        "routes": [r.to_dict() for r in routes],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def load_routes_yaml(path: Path) -> list[DiscoveredRoute]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return [DiscoveredRoute(**r) for r in data.get("routes", [])]
