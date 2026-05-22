from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path

import yaml

from .routes.base import BookingParams, DayBed, Member


@dataclass(frozen=True)
class Person:
    name: str
    id_number: str
    phone: str
    birthday: date
    sex: str = "M"
    email: str = ""
    addr: str = ""
    tel: str = ""
    fax: str = ""
    nation: str = ""
    country_code: str = ""
    city_code: str = ""
    contact_name: str = ""
    contact_tel: str = ""

    def to_member(self) -> Member:
        return Member(
            name=self.name,
            id_number=self.id_number,
            phone=self.phone,
            birthday=self.birthday,
            sex=self.sex,
            email=self.email,
            addr=self.addr,
            tel=self.tel,
            fax=self.fax,
            nation=self.nation,
            country_code=self.country_code,
            city_code=self.city_code,
            contact_name=self.contact_name,
            contact_tel=self.contact_tel,
        )


@dataclass
class PersonalDb:
    leader: Person
    members: dict[str, Person] = field(default_factory=dict)
    stay: Person | None = None
    applicant: Person | None = None

    def get_member(self, alias: str) -> Person:
        if alias not in self.members:
            raise KeyError(f"Unknown member alias {alias!r}. Known: {sorted(self.members)}")
        return self.members[alias]


@dataclass
class BookingSpec:
    name: str
    route: str
    start_date: date
    nights: int = 1
    members: list[str] = field(default_factory=list)
    open_time: time = time(7, 0, 0)
    agree_terms: bool = True
    team_name: str = ""
    seminar: str = ""
    satellite_phone: str = ""
    radio_frequency: str = ""
    note: str = ""
    day_beds: list[DayBed] = field(default_factory=list)

    def to_booking_params(self, db: PersonalDb) -> BookingParams:
        member_persons = [db.get_member(alias) for alias in self.members]
        applicant_member = db.applicant.to_member() if db.applicant else None
        stay_member = db.stay.to_member() if db.stay else None
        return BookingParams(
            start_date=self.start_date,
            nights=self.nights,
            people=1 + len(member_persons),
            leader=db.leader.to_member(),
            members=[p.to_member() for p in member_persons],
            agree_terms=self.agree_terms,
            applicant=applicant_member,
            stay=stay_member,
            team_name=self.team_name,
            seminar=self.seminar,
            satellite_phone=self.satellite_phone,
            radio_frequency=self.radio_frequency,
            note=self.note,
            day_beds=list(self.day_beds),
        )


def _person_from_dict(d: dict) -> Person:
    return Person(
        name=str(d["name"]),
        id_number=str(d["id_number"]),
        phone=str(d["phone"]),
        birthday=_as_date(d["birthday"]),
        sex=str(d.get("sex", "M")),
        email=str(d.get("email", "")),
        addr=str(d.get("addr", "")),
        tel=str(d.get("tel", "")),
        fax=str(d.get("fax", "")),
        nation=str(d.get("nation", "")),
        country_code=str(d.get("country_code", "")),
        city_code=str(d.get("city_code", "")),
        contact_name=str(d.get("contact_name", "")),
        contact_tel=str(d.get("contact_tel", "")),
    )


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_time(value: object) -> time:
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _daybed_from_dict(d: dict) -> DayBed:
    return DayBed(
        day_index=int(d["day_index"]),
        num=int(d.get("num", 1)),
        bedok=bool(d.get("bedok", True)),
        bakroomok=bool(d.get("bakroomok", True)),
        rooms=int(d.get("rooms", 0)),
    )


def load_personal(path: Path) -> PersonalDb:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    leader_data = data.get("leader")
    if not leader_data:
        raise ValueError(f"{path} 缺少 leader 區塊")
    leader = _person_from_dict(leader_data)
    members_raw = data.get("members") or {}
    members = {alias: _person_from_dict(d) for alias, d in members_raw.items()}
    stay = _person_from_dict(data["stay"]) if data.get("stay") else None
    applicant = _person_from_dict(data["applicant"]) if data.get("applicant") else None
    return PersonalDb(leader=leader, members=members, stay=stay, applicant=applicant)


def load_bookings(path: Path) -> dict[str, BookingSpec]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw_list = data.get("bookings") or []
    specs: dict[str, BookingSpec] = {}
    for entry in raw_list:
        name = str(entry["name"])
        spec = BookingSpec(
            name=name,
            route=str(entry["route"]),
            start_date=_as_date(entry["start_date"]),
            nights=int(entry.get("nights", 1)),
            members=[str(m) for m in entry.get("members", [])],
            open_time=_as_time(entry.get("open_time", "07:00:00")),
            agree_terms=bool(entry.get("agree_terms", True)),
            team_name=str(entry.get("team_name", "")),
            seminar=str(entry.get("seminar", "")),
            satellite_phone=str(entry.get("satellite_phone", "")),
            radio_frequency=str(entry.get("radio_frequency", "")),
            note=str(entry.get("note", "")),
            day_beds=[_daybed_from_dict(d) for d in (entry.get("day_beds") or [])],
        )
        if name in specs:
            raise ValueError(f"Duplicate booking name: {name}")
        specs[name] = spec
    return specs
