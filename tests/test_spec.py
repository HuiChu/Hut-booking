from datetime import date, time
from pathlib import Path

import pytest
import yaml

from hut_bot.spec import (
    BookingSpec,
    Person,
    PersonalDb,
    load_bookings,
    load_personal,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_load_personal_with_leader_and_members(tmp_path: Path) -> None:
    path = tmp_path / "personal.yaml"
    _write_yaml(
        path,
        {
            "leader": {
                "name": "王小明",
                "id_number": "A123456789",
                "phone": "0912345678",
                "birthday": "1990-01-01",
            },
            "members": {
                "alice": {
                    "name": "林小華",
                    "id_number": "B223456789",
                    "phone": "0922334455",
                    "birthday": "1991-03-12",
                },
            },
        },
    )
    db = load_personal(path)
    assert db.leader.name == "王小明"
    assert db.leader.birthday == date(1990, 1, 1)
    assert db.get_member("alice").name == "林小華"


def test_load_personal_requires_leader(tmp_path: Path) -> None:
    path = tmp_path / "personal.yaml"
    _write_yaml(path, {"members": {}})
    with pytest.raises(ValueError, match="leader"):
        load_personal(path)


def test_get_member_unknown_alias_raises() -> None:
    db = PersonalDb(
        leader=Person(name="L", id_number="A", phone="0", birthday=date(1990, 1, 1)),
        members={},
    )
    with pytest.raises(KeyError):
        db.get_member("ghost")


def test_load_bookings_parses_spec(tmp_path: Path) -> None:
    path = tmp_path / "bookings.yaml"
    _write_yaml(
        path,
        {
            "bookings": [
                {
                    "name": "snow-main-2026-06",
                    "route": "雪山主峰-單日往返",
                    "start_date": "2026-06-15",
                    "nights": 1,
                    "members": ["alice", "bob"],
                    "open_time": "07:00:00",
                }
            ]
        },
    )
    specs = load_bookings(path)
    assert "snow-main-2026-06" in specs
    spec = specs["snow-main-2026-06"]
    assert spec.route == "雪山主峰-單日往返"
    assert spec.start_date == date(2026, 6, 15)
    assert spec.members == ["alice", "bob"]
    assert spec.open_time == time(7, 0, 0)


def test_load_bookings_rejects_duplicate_name(tmp_path: Path) -> None:
    path = tmp_path / "bookings.yaml"
    _write_yaml(
        path,
        {
            "bookings": [
                {"name": "dup", "route": "r", "start_date": "2026-06-15"},
                {"name": "dup", "route": "r", "start_date": "2026-06-16"},
            ]
        },
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_bookings(path)


def test_to_booking_params_counts_leader_plus_members() -> None:
    leader = Person(name="L", id_number="A1", phone="0900", birthday=date(1990, 1, 1))
    alice = Person(name="A", id_number="B1", phone="0911", birthday=date(1991, 1, 1))
    bob = Person(name="B", id_number="C1", phone="0922", birthday=date(1992, 1, 1))
    db = PersonalDb(leader=leader, members={"alice": alice, "bob": bob})

    spec = BookingSpec(
        name="t",
        route="r",
        start_date=date(2026, 6, 15),
        nights=2,
        members=["alice", "bob"],
    )
    params = spec.to_booking_params(db)
    assert params.people == 3  # leader + 2 members
    assert params.leader.name == "L"
    assert [m.name for m in params.members] == ["A", "B"]
    assert params.nights == 2
    assert params.start_date == date(2026, 6, 15)


def test_to_booking_params_unknown_member_alias_raises() -> None:
    db = PersonalDb(
        leader=Person(name="L", id_number="A", phone="0", birthday=date(1990, 1, 1)),
        members={},
    )
    spec = BookingSpec(
        name="t", route="r", start_date=date(2026, 6, 15), members=["ghost"]
    )
    with pytest.raises(KeyError):
        spec.to_booking_params(db)
