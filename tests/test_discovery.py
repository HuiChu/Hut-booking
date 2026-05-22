from pathlib import Path

import pytest

from hut_bot.routes.discovery import (
    DiscoveredRoute,
    load_routes_yaml,
    parse_route_options,
    slugify,
    write_routes_yaml,
)

FIXTURE = Path(__file__).parent / "fixtures" / "apply_1_public.html"


@pytest.fixture
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parse_route_options_finds_all_routes(fixture_html: str) -> None:
    routes = parse_route_options(fixture_html)
    assert len(routes) >= 90, f"expected ~95 routes, got {len(routes)}"


def test_parse_route_options_extracts_known_routes(fixture_html: str) -> None:
    routes = parse_route_options(fixture_html)
    by_code = {r.code: r for r in routes}

    assert "100" in by_code
    assert "雪山主峰" in by_code["100"].display_name
    assert by_code["100"].difficulty == "4級"

    assert "99" in by_code
    assert by_code["99"].difficulty == "3級"

    assert "150" in by_code
    assert "屏風山線" == by_code["150"].display_name
    assert by_code["150"].difficulty is None


def test_parse_route_options_assigns_unique_route_ids(fixture_html: str) -> None:
    routes = parse_route_options(fixture_html)
    route_ids = [r.route_id for r in routes]
    assert all(rid for rid in route_ids), "every route should have a non-empty route_id"


def test_slugify_strips_leading_difficulty_only() -> None:
    assert slugify("(4級) 雪山主峰(單日往返)") == "雪山主峰-單日往返"
    assert slugify("屏風山線") == "屏風山線"
    assert "奇萊" in slugify("奇萊東稜")


def test_parse_route_options_no_duplicate_route_ids(fixture_html: str) -> None:
    routes = parse_route_options(fixture_html)
    ids = [r.route_id for r in routes]
    assert len(ids) == len(set(ids)), f"duplicates: {[i for i in ids if ids.count(i) > 1]}"


def test_parse_empty_html_returns_empty() -> None:
    assert parse_route_options("<html><body>no select here</body></html>") == []


def test_yaml_roundtrip(tmp_path: Path) -> None:
    routes = [
        DiscoveredRoute(code="100", display_name="(4級) 雪山主峰", route_id="雪山主峰", difficulty="4級"),
        DiscoveredRoute(code="150", display_name="屏風山線", route_id="屏風山線"),
    ]
    out = tmp_path / "routes.yaml"
    write_routes_yaml(routes, out)

    loaded = load_routes_yaml(out)
    assert len(loaded) == 2
    assert loaded[0].code == "100"
    assert loaded[0].difficulty == "4級"
    assert loaded[1].code == "150"
    assert loaded[1].difficulty is None
