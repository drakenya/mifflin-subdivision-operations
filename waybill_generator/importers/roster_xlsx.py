import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import yaml

from waybill_generator.models.car import Car


@dataclass
class RawRosterRow:
    inventory_status: str
    road: str
    location: str
    type_text: str
    car_number: str
    notes: str


def _cell_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


SOLD_KEYWORDS = ("sold", "sell", "listed", "swap")


def is_sold(row: RawRosterRow) -> bool:
    combined = f"{row.inventory_status} {row.location}".lower()
    return any(keyword in combined for keyword in SOLD_KEYWORDS)


def read_freight_cars(filepath: Path) -> list[RawRosterRow]:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb["Freight Cars"]
    rows: list[RawRosterRow] = []
    for row in ws.iter_rows(min_row=2):
        cells = {cell.column_letter: cell.value for cell in row
                 if hasattr(cell, "column_letter")}
        raw = RawRosterRow(
            inventory_status=_cell_str(cells.get("A")),
            road=_cell_str(cells.get("B")),
            location=_cell_str(cells.get("E")),
            type_text=_cell_str(cells.get("F")),
            car_number=_cell_str(cells.get("K")),
            notes=_cell_str(cells.get("S")),
        )
        if any([
            raw.inventory_status, raw.road, raw.location,
            raw.type_text, raw.car_number, raw.notes,
        ]):
            rows.append(raw)
    return rows


FALLBACK_AAR_CODE = "XM"

_KEYWORD_RULES: list[tuple[str, str]] = [
    ("cement", "LC"),
    ("grain", "LB"),
    ("covered hopper", "LO"),
    ("hopper", "HM"),
    ("steel gondola", "GS"),
    ("gondola", "GB"),
    ("flat car", "FM"),
    ("tank car", "TM"),
    ("ice bunker", "RB"),
    ("ice hatch", "RB"),
    ("reefer", "RB"),
    ("refrigerator", "RB"),
    ("stock car", "RS"),
    ("box car", "XM"),
]


def load_car_type_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or []
    return {entry["source_text"].lower(): entry["aar_code"] for entry in raw}


def resolve_aar_code(type_text: str, car_type_map: dict[str, str]) -> tuple[str, str]:
    lower = type_text.lower()
    if lower in car_type_map:
        return car_type_map[lower], "map"
    for keyword, code in _KEYWORD_RULES:
        if keyword in lower:
            return code, "keyword"
    return FALLBACK_AAR_CODE, "fallback"


_TONNAGE_RE = re.compile(r"(\d+)[\s-]*ton", re.IGNORECASE)
_LENGTH_RE = re.compile(r"^(\d+)'")

CAPACITY_DEFAULTS: dict[str, int] = {
    "XM": 50, "XF": 50, "XL": 50, "XP": 50,
    "HM": 70, "HT": 70,
    "LO": 70, "LB": 70, "LC": 70,
    "GB": 50, "GS": 50,
    "FM": 50, "FC": 50, "FD": 50, "FA": 50,
    "TM": 50, "TP": 50,
    "RB": 40,
    "RS": 40,
}


def extract_tonnage(type_text: str) -> int | None:
    match = _TONNAGE_RE.search(type_text)
    return int(match.group(1)) if match else None


def extract_length_ft(type_text: str) -> int | None:
    match = _LENGTH_RE.match(type_text.strip())
    return int(match.group(1)) if match else None


def resolve_capacity_tons(type_text: str, aar_code: str) -> tuple[int, bool]:
    tonnage = extract_tonnage(type_text)
    if tonnage is not None:
        return tonnage, False
    return CAPACITY_DEFAULTS.get(aar_code, 50), True


@dataclass
class RosterImportReport:
    rows_read: int = 0
    skipped_sold: int = 0
    skipped_incomplete: int = 0
    imported: int = 0
    duplicate_ids: list[str] = field(default_factory=list)
    map_matched: int = 0
    keyword_matched: int = 0
    fallback_matched: int = 0
    capacity_regex: int = 0
    capacity_default: int = 0
    unmapped_types: dict[str, int] = field(default_factory=dict)


def build_cars(
    rows: list[RawRosterRow],
    car_type_map: dict[str, str],
) -> tuple[list[Car], RosterImportReport]:
    report = RosterImportReport(rows_read=len(rows))
    cars_by_id: dict[str, Car] = {}

    for row in rows:
        if is_sold(row):
            report.skipped_sold += 1
            continue
        if not row.road or not row.car_number:
            report.skipped_incomplete += 1
            continue

        aar_code, tier = resolve_aar_code(row.type_text, car_type_map)
        if tier == "map":
            report.map_matched += 1
        elif tier == "keyword":
            report.keyword_matched += 1
        else:
            report.fallback_matched += 1
            report.unmapped_types[row.type_text] = (
                report.unmapped_types.get(row.type_text, 0) + 1
            )

        capacity_tons, capacity_guessed = resolve_capacity_tons(row.type_text, aar_code)
        if capacity_guessed:
            report.capacity_default += 1
        else:
            report.capacity_regex += 1

        length_ft = extract_length_ft(row.type_text)

        notes_parts = []
        if row.notes:
            notes_parts.append(row.notes)
        if tier == "fallback":
            notes_parts.append(f'[import: guessed aar_code from "{row.type_text}"]')
        if capacity_guessed:
            notes_parts.append("[import: guessed capacity_tons]")
        notes = " ".join(notes_parts) or None

        car_id = f"{row.road}-{row.car_number}"
        if car_id in cars_by_id:
            report.duplicate_ids.append(car_id)

        cars_by_id[car_id] = Car(
            id=car_id,
            road=row.road,
            car_number=row.car_number,
            aar_code=aar_code,
            capacity_tons=capacity_tons,
            length_ft=length_ft,
            notes=notes,
        )

    report.imported = len(cars_by_id)
    return list(cars_by_id.values()), report
