# Roster XLSX Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `waybill import-roster` CLI command that reads the "Freight Cars"
sheet of a OneDrive-synced `.xlsx` inventory spreadsheet and fully regenerates
`data/cars.yaml`, deriving AAR code / capacity / length from a free-text
description column.

**Architecture:** A new `waybill_generator/importers/roster_xlsx.py` module
provides pure functions for reading rows (via `openpyxl`), filtering sold/
incomplete rows, normalizing car type → AAR code (map-file-first, keyword
fallback), and deriving capacity/length via regex extraction with table-based
defaults. A single orchestration function (`build_cars`) ties these into a
`(list[Car], RosterImportReport)` result. The CLI command wires this to disk:
read the source file, write `data/cars.yaml`, print the report.

**Tech Stack:** Python 3.11+, `openpyxl` (new dependency), Pydantic v2 (`Car`
model), Click (CLI), PyYAML.

## Global Constraints

- Car id convention: `{road}-{car_number}` (from `CLAUDE.md`).
- Full resync only: every run replaces `data/cars.yaml` entirely — no merge
  with prior file content (per approved spec).
- Sold/listed/swap-marked rows are skipped entirely, not imported as
  `active: false` (per approved spec).
- AAR codes used are this project's own subset in `data/aar_codes.yaml`
  (e.g. `RB` = Refrigerator Car, `RS` = Stock Car) — not generic real-world
  AAR conventions.
- Guessed/fallback `aar_code` or `capacity_tons` values must be flagged
  inline in that car's `notes` field, not just in the terminal report.
- Follow the existing importer pattern in `waybill_generator/importers/`
  (dataclass rows, map-file-first + fallback normalization, a report object)
  for consistency with `normalizer.py` / `opsig.py` / `jbritton.py`.
- Spec: `docs/superpowers/specs/2026-07-15-roster-xlsx-import-design.md`

---

### Task 1: Row reader (`openpyxl` dependency + `RawRosterRow` + `read_freight_cars`)

**Files:**
- Create: `waybill_generator/importers/roster_xlsx.py`
- Modify: `pyproject.toml`
- Test: `tests/test_roster_import.py`

**Interfaces:**
- Produces: `RawRosterRow` dataclass with fields `inventory_status: str,
  road: str, location: str, type_text: str, car_number: str, notes: str`.
- Produces: `read_freight_cars(filepath: Path) -> list[RawRosterRow]`.
- Produces: `_cell_str(value) -> str` (module-private helper, converts a
  cell value to a stripped string, `""` for `None`).

- [ ] **Step 1: Add `openpyxl` to `pyproject.toml` and install it**

In `pyproject.toml`, change the `dependencies` list:

```toml
dependencies = [
    "click>=8",
    "pydantic>=2",
    "reportlab>=4",
    "pyyaml>=6",
    "xlrd>=2",
    "openpyxl>=3",
]
```

Run: `source .venv/bin/activate && pip install -e ".[dev]"`
Expected: install succeeds, `openpyxl` importable.

- [ ] **Step 2: Write the failing test**

Create `tests/test_roster_import.py` with this content:

```python
from pathlib import Path

import openpyxl

from waybill_generator.importers.roster_xlsx import RawRosterRow, read_freight_cars


def _make_workbook(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Freight Cars"
    headers = {
        "A": "Inventory date", "B": "814", "C": "Manufacturer", "D": "Manufacturer #",
        "E": "Location", "F": "Type", "K": "Car #", "S": "Notes",
    }
    for col, val in headers.items():
        ws[f"{col}1"] = val
    for i, row in enumerate(rows, start=2):
        for col, val in row.items():
            ws[f"{col}{i}"] = val
    path = tmp_path / "roster.xlsx"
    wb.save(path)
    return path


class TestReadFreightCars:
    def test_reads_basic_row(self, tmp_path):
        path = _make_workbook(tmp_path, [
            {"A": "45711", "B": "PRR", "E": "Bin 1", "F": "40' Box Car",
             "K": "12345", "S": "a note"},
        ])
        rows = read_freight_cars(path)
        assert len(rows) == 1
        assert rows[0] == RawRosterRow(
            inventory_status="45711", road="PRR", location="Bin 1",
            type_text="40' Box Car", car_number="12345", notes="a note",
        )

    def test_row_with_blank_leading_cells_still_reads_correctly(self, tmp_path):
        # Regression case: Excel omits blank cells from a row entirely, so a
        # positional (non-reference-based) reader would misalign columns here.
        path = _make_workbook(tmp_path, [
            {"B": "ATSF", "F": "40' Box Car", "K": "140185"},
        ])
        rows = read_freight_cars(path)
        assert len(rows) == 1
        assert rows[0].road == "ATSF"
        assert rows[0].type_text == "40' Box Car"
        assert rows[0].car_number == "140185"

    def test_fully_blank_trailing_row_skipped(self, tmp_path):
        path = _make_workbook(tmp_path, [
            {"A": "45711", "B": "PRR", "F": "40' Box Car", "K": "12345"},
            {},
        ])
        rows = read_freight_cars(path)
        assert len(rows) == 1

    def test_numeric_cell_values_stringified(self, tmp_path):
        path = _make_workbook(tmp_path, [
            {"B": "PRR", "F": "40' Box Car", "K": 12345},
        ])
        rows = read_freight_cars(path)
        assert rows[0].car_number == "12345"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_roster_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'waybill_generator.importers.roster_xlsx'`

- [ ] **Step 4: Write minimal implementation**

Create `waybill_generator/importers/roster_xlsx.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import openpyxl


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


def read_freight_cars(filepath: Path) -> list[RawRosterRow]:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb["Freight Cars"]
    rows: list[RawRosterRow] = []
    for row in ws.iter_rows(min_row=2):
        cells = {cell.column_letter: cell.value for cell in row}
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_roster_import.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml waybill_generator/importers/roster_xlsx.py tests/test_roster_import.py
git commit -m "feat: add xlsx roster row reader"
```

---

### Task 2: Sold-status filter

**Files:**
- Modify: `waybill_generator/importers/roster_xlsx.py`
- Test: `tests/test_roster_import.py`

**Interfaces:**
- Consumes: `RawRosterRow` (Task 1).
- Produces: `is_sold(row: RawRosterRow) -> bool`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_roster_import.py`:

```python
from waybill_generator.importers.roster_xlsx import is_sold


def _row(inventory_status="45711", road="PRR", location="Bin 1",
         type_text="40' Box Car", car_number="12345", notes="") -> RawRosterRow:
    return RawRosterRow(
        inventory_status=inventory_status, road=road, location=location,
        type_text=type_text, car_number=car_number, notes=notes,
    )


class TestIsSold:
    def test_sold_in_inventory_status(self):
        assert is_sold(_row(inventory_status="SOLD"))

    def test_sell_in_location(self):
        assert is_sold(_row(location="Sell - Box 02 - Built"))

    def test_listed_swap_in_location(self):
        assert is_sold(_row(location="LISTED - HO SWAP"))

    def test_case_insensitive(self):
        assert is_sold(_row(inventory_status="sold"))

    def test_normal_row_not_sold(self):
        assert not is_sold(_row(inventory_status="45711", location="Bin 08 - Foreign Roads"))

    def test_blank_status_not_sold(self):
        assert not is_sold(_row(inventory_status="", location=""))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roster_import.py -v -k TestIsSold`
Expected: FAIL with `ImportError: cannot import name 'is_sold'`

- [ ] **Step 3: Write minimal implementation**

Add to `waybill_generator/importers/roster_xlsx.py`:

```python
SOLD_KEYWORDS = ("sold", "sell", "listed", "swap")


def is_sold(row: RawRosterRow) -> bool:
    combined = f"{row.inventory_status} {row.location}".lower()
    return any(keyword in combined for keyword in SOLD_KEYWORDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_roster_import.py -v -k TestIsSold`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/importers/roster_xlsx.py tests/test_roster_import.py
git commit -m "feat: add sold-status filter for roster import"
```

---

### Task 3: Car type map loading + AAR code resolution

**Files:**
- Modify: `waybill_generator/importers/roster_xlsx.py`
- Test: `tests/test_roster_import.py`

**Interfaces:**
- Produces: `load_car_type_map(path: Path) -> dict[str, str]` (keys are
  lowercased `source_text`, values are AAR codes).
- Produces: `resolve_aar_code(type_text: str, car_type_map: dict[str, str])
  -> tuple[str, str]` — returns `(aar_code, tier)` where `tier` is one of
  `"map"`, `"keyword"`, `"fallback"`.
- Produces: `FALLBACK_AAR_CODE: str = "XM"` module constant.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_roster_import.py`:

```python
from waybill_generator.importers.roster_xlsx import load_car_type_map, resolve_aar_code


class TestLoadCarTypeMap:
    def test_loads_entries_lowercased(self, tmp_path):
        p = tmp_path / "car_type_map.yaml"
        p.write_text(
            "- source_text: \"GS 40' Gondola\"\n  aar_code: GS\n"
            "- source_text: \"Bev-Bel Special Run Box Car\"\n  aar_code: XM\n"
        )
        cmap = load_car_type_map(p)
        assert cmap["gs 40' gondola"] == "GS"
        assert cmap["bev-bel special run box car"] == "XM"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_car_type_map(tmp_path / "nonexistent.yaml") == {}


class TestResolveAarCode:
    def test_explicit_map_wins(self):
        cmap = {"custom decorated hopper": "LO"}
        code, tier = resolve_aar_code("Custom Decorated Hopper", cmap)
        assert code == "LO"
        assert tier == "map"

    def test_keyword_box_car(self):
        code, tier = resolve_aar_code("40' Steel SD Box Car", {})
        assert code == "XM"
        assert tier == "keyword"

    def test_keyword_open_hopper(self):
        code, tier = resolve_aar_code("70 Ton 12 Panel Triple Hopper", {})
        assert code == "HM"
        assert tier == "keyword"

    def test_keyword_covered_hopper(self):
        code, tier = resolve_aar_code("PS-2 Covered Hopper", {})
        assert code == "LO"
        assert tier == "keyword"

    def test_keyword_grain_hopper(self):
        code, tier = resolve_aar_code("Grain Hopper Car", {})
        assert code == "LB"
        assert tier == "keyword"

    def test_keyword_cement_hopper(self):
        code, tier = resolve_aar_code("Cement Covered Hopper", {})
        assert code == "LC"
        assert tier == "keyword"

    def test_keyword_steel_gondola(self):
        code, tier = resolve_aar_code("40' Steel Gondola", {})
        assert code == "GS"
        assert tier == "keyword"

    def test_keyword_plain_gondola(self):
        code, tier = resolve_aar_code("Ore Gondola", {})
        assert code == "GB"
        assert tier == "keyword"

    def test_keyword_flat_car(self):
        code, tier = resolve_aar_code("50' Bulkhead Flat Car", {})
        assert code == "FM"
        assert tier == "keyword"

    def test_keyword_tank_car(self):
        code, tier = resolve_aar_code("10,000 Gal Tank Car", {})
        assert code == "TM"
        assert tier == "keyword"

    def test_keyword_reefer(self):
        code, tier = resolve_aar_code("40' Steam Era Ice Bunker Refer", {})
        assert code == "RB"
        assert tier == "keyword"

    def test_keyword_stock_car(self):
        code, tier = resolve_aar_code("40' Wood Stock Car", {})
        assert code == "RS"
        assert tier == "keyword"

    def test_fallback_when_unmatched(self):
        code, tier = resolve_aar_code("Mystery Custom Kitbash", {})
        assert code == "XM"
        assert tier == "fallback"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roster_import.py -v -k "TestLoadCarTypeMap or TestResolveAarCode"`
Expected: FAIL with `ImportError: cannot import name 'load_car_type_map'`

- [ ] **Step 3: Write minimal implementation**

Add to `waybill_generator/importers/roster_xlsx.py`:

```python
import yaml

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
```

Note: `yaml` and `Path` imports are added at module level (merge with the
existing `from pathlib import Path` and add `import yaml` near the top of
the file, alongside the existing `import openpyxl`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_roster_import.py -v -k "TestLoadCarTypeMap or TestResolveAarCode"`
Expected: PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/importers/roster_xlsx.py tests/test_roster_import.py
git commit -m "feat: add car type map and AAR code resolution"
```

---

### Task 4: Capacity and length extraction

**Files:**
- Modify: `waybill_generator/importers/roster_xlsx.py`
- Test: `tests/test_roster_import.py`

**Interfaces:**
- Produces: `extract_tonnage(type_text: str) -> int | None`.
- Produces: `extract_length_ft(type_text: str) -> int | None`.
- Produces: `CAPACITY_DEFAULTS: dict[str, int]` module constant, keyed by AAR code.
- Consumes: none of the AAR code resolution — `resolve_capacity_tons` takes
  an already-resolved `aar_code` string.
- Produces: `resolve_capacity_tons(type_text: str, aar_code: str) -> tuple[int, bool]`
  — returns `(capacity_tons, is_guessed)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_roster_import.py`:

```python
from waybill_generator.importers.roster_xlsx import (
    extract_tonnage, extract_length_ft, resolve_capacity_tons, CAPACITY_DEFAULTS,
)


class TestExtractTonnage:
    def test_extracts_leading_tonnage(self):
        assert extract_tonnage("70 Ton 12 Panel Triple Hopper") == 70

    def test_extracts_tonnage_mid_string(self):
        assert extract_tonnage("52'6 Bethlehem 70-Ton Riveted Drop-End Gondola") == 70

    def test_no_tonnage_returns_none(self):
        assert extract_tonnage("40' Steel SD Box Car") is None


class TestExtractLengthFt:
    def test_extracts_leading_length(self):
        assert extract_length_ft("40' Steel SD Box Car") == 40

    def test_extracts_leading_length_short_form(self):
        assert extract_length_ft("24' Rib Ore Car") == 24

    def test_no_leading_length_returns_none(self):
        assert extract_length_ft("GS 40' Gondola") is None

    def test_strips_leading_whitespace(self):
        assert extract_length_ft("  50' DD Box Car") == 50


class TestResolveCapacityTons:
    def test_regex_extracted_tonnage_used_when_present(self):
        tons, guessed = resolve_capacity_tons("70 Ton 12 Panel Triple Hopper", "HM")
        assert tons == 70
        assert guessed is False

    def test_falls_back_to_default_table(self):
        tons, guessed = resolve_capacity_tons("40' Steel SD Box Car", "XM")
        assert tons == CAPACITY_DEFAULTS["XM"]
        assert guessed is True

    def test_unknown_aar_code_defaults_to_50(self):
        tons, guessed = resolve_capacity_tons("Something Odd", "ZZ")
        assert tons == 50
        assert guessed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roster_import.py -v -k "TestExtractTonnage or TestExtractLengthFt or TestResolveCapacityTons"`
Expected: FAIL with `ImportError: cannot import name 'extract_tonnage'`

- [ ] **Step 3: Write minimal implementation**

Add to `waybill_generator/importers/roster_xlsx.py`:

```python
import re

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
```

Add `import re` near the top of the file alongside the other imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_roster_import.py -v -k "TestExtractTonnage or TestExtractLengthFt or TestResolveCapacityTons"`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/importers/roster_xlsx.py tests/test_roster_import.py
git commit -m "feat: add capacity and length derivation for roster import"
```

---

### Task 5: `RosterImportReport` + `build_cars` orchestration

**Files:**
- Modify: `waybill_generator/importers/roster_xlsx.py`
- Test: `tests/test_roster_import.py`

**Interfaces:**
- Consumes: `RawRosterRow`, `is_sold`, `resolve_aar_code`, `resolve_capacity_tons`,
  `extract_length_ft` (Tasks 1–4).
- Produces: `RosterImportReport` dataclass with fields `rows_read: int = 0,
  skipped_sold: int = 0, skipped_incomplete: int = 0, imported: int = 0,
  duplicate_ids: list[str] = field(default_factory=list), map_matched: int = 0,
  keyword_matched: int = 0, fallback_matched: int = 0, capacity_regex: int = 0,
  capacity_default: int = 0, unmapped_types: dict[str, int] = field(default_factory=dict)`.
- Produces: `build_cars(rows: list[RawRosterRow], car_type_map: dict[str, str])
  -> tuple[list[Car], RosterImportReport]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_roster_import.py`:

```python
from waybill_generator.importers.roster_xlsx import build_cars, RosterImportReport


class TestBuildCars:
    def test_normal_row_imported(self):
        rows = [_row(road="PRR", car_number="12345", type_text="40' Steel SD Box Car")]
        cars, report = build_cars(rows, {})
        assert len(cars) == 1
        assert cars[0].id == "PRR-12345"
        assert cars[0].road == "PRR"
        assert cars[0].car_number == "12345"
        assert cars[0].aar_code == "XM"
        assert cars[0].active is True
        assert report.imported == 1
        assert report.rows_read == 1

    def test_sold_row_skipped(self):
        rows = [_row(inventory_status="SOLD")]
        cars, report = build_cars(rows, {})
        assert cars == []
        assert report.skipped_sold == 1
        assert report.imported == 0

    def test_incomplete_row_skipped(self):
        rows = [_row(road=""), _row(car_number="")]
        cars, report = build_cars(rows, {})
        assert cars == []
        assert report.skipped_incomplete == 2

    def test_duplicate_id_last_row_wins(self):
        rows = [
            _row(road="PRR", car_number="1", type_text="40' Box Car", notes="first"),
            _row(road="PRR", car_number="1", type_text="40' Box Car", notes="second"),
        ]
        cars, report = build_cars(rows, {})
        assert len(cars) == 1
        assert "second" in cars[0].notes
        assert report.duplicate_ids == ["PRR-1"]
        assert report.imported == 1

    def test_map_matched_counted(self):
        rows = [_row(type_text="Custom Decorated Hopper")]
        cmap = {"custom decorated hopper": "LO"}
        _, report = build_cars(rows, cmap)
        assert report.map_matched == 1
        assert report.keyword_matched == 0
        assert report.fallback_matched == 0

    def test_keyword_matched_counted(self):
        rows = [_row(type_text="40' Box Car")]
        _, report = build_cars(rows, {})
        assert report.keyword_matched == 1

    def test_fallback_counted_and_notes_flagged(self):
        rows = [_row(type_text="Mystery Custom Kitbash")]
        cars, report = build_cars(rows, {})
        assert report.fallback_matched == 1
        assert report.unmapped_types == {"Mystery Custom Kitbash": 1}
        assert "guessed aar_code" in cars[0].notes
        assert "Mystery Custom Kitbash" in cars[0].notes

    def test_capacity_regex_vs_default_counted(self):
        rows = [
            _row(type_text="70 Ton 12 Panel Triple Hopper"),
            _row(road="PRR", car_number="2", type_text="40' Box Car"),
        ]
        cars, report = build_cars(rows, {})
        assert report.capacity_regex == 1
        assert report.capacity_default == 1
        guessed_car = next(c for c in cars if c.car_number == "2")
        assert "guessed capacity_tons" in guessed_car.notes

    def test_length_ft_derived_when_present(self):
        rows = [_row(type_text="40' Steel SD Box Car")]
        cars, _ = build_cars(rows, {})
        assert cars[0].length_ft == 40

    def test_length_ft_none_when_absent(self):
        rows = [_row(type_text="GS 40' Gondola")]
        cars, _ = build_cars(rows, {})
        assert cars[0].length_ft is None

    def test_original_notes_preserved_alongside_guess_markers(self):
        rows = [_row(type_text="Mystery Custom Kitbash", notes="Custom lighted")]
        cars, _ = build_cars(rows, {})
        assert "Custom lighted" in cars[0].notes
        assert "guessed aar_code" in cars[0].notes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roster_import.py -v -k TestBuildCars`
Expected: FAIL with `ImportError: cannot import name 'build_cars'`

- [ ] **Step 3: Write minimal implementation**

Add to `waybill_generator/importers/roster_xlsx.py`:

```python
from dataclasses import field

from waybill_generator.models.car import Car


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
```

Note: `field` needs to be imported alongside the existing `dataclass` import
— change the existing `from dataclasses import dataclass` line at the top of
the file to `from dataclasses import dataclass, field`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_roster_import.py -v -k TestBuildCars`
Expected: PASS (11 tests)

- [ ] **Step 5: Run the full test file to make sure nothing regressed**

Run: `pytest tests/test_roster_import.py -v`
Expected: PASS (all tests from Tasks 1–5)

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/importers/roster_xlsx.py tests/test_roster_import.py
git commit -m "feat: add build_cars orchestration and import report"
```

---

### Task 6: CLI command `import-roster`

**Files:**
- Modify: `waybill_generator/cli.py`
- Create: `data/car_type_map.yaml`
- Test: `tests/test_roster_import.py`

**Interfaces:**
- Consumes: `read_freight_cars`, `load_car_type_map`, `build_cars` (Tasks 1, 3, 5).
- Produces: `waybill import-roster --source PATH` CLI command (writes
  `<data-path>/cars.yaml`, reads `<data-path>/car_type_map.yaml`).

- [ ] **Step 1: Create the starter map file**

Create `data/car_type_map.yaml`:

```yaml
# Map roster spreadsheet "Type" free-text to AAR codes.
# Lookup is case-insensitive exact match on source_text.
# Add entries here as unmapped types appear in `waybill import-roster` reports.
#
# Example:
# - source_text: "Bev-Bel Special Run Box Car"
#   aar_code: XM
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_roster_import.py`:

```python
import yaml as _yaml
from click.testing import CliRunner
from waybill_generator.cli import main


def _make_roster_xlsx(tmp_path, rows: list[dict[str, object]]) -> Path:
    return _make_workbook(tmp_path, rows)


class TestImportRosterCommand:
    def test_writes_cars_yaml(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        source = _make_roster_xlsx(tmp_path, [
            {"A": "45711", "B": "PRR", "F": "40' Steel SD Box Car", "K": "12345", "S": "note"},
        ])

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import-roster", "--source", str(source),
        ])

        assert result.exit_code == 0, result.output
        cars = _yaml.safe_load((data_dir / "cars.yaml").read_text())
        assert len(cars) == 1
        assert cars[0]["id"] == "PRR-12345"

    def test_sold_row_excluded_from_output(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        source = _make_roster_xlsx(tmp_path, [
            {"A": "SOLD", "B": "PRR", "F": "40' Box Car", "K": "12345"},
            {"A": "45711", "B": "PRR", "F": "40' Box Car", "K": "99999"},
        ])

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import-roster", "--source", str(source),
        ])

        assert result.exit_code == 0, result.output
        cars = _yaml.safe_load((data_dir / "cars.yaml").read_text())
        assert len(cars) == 1
        assert cars[0]["id"] == "PRR-99999"

    def test_report_printed(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        source = _make_roster_xlsx(tmp_path, [
            {"A": "45711", "B": "PRR", "F": "40' Box Car", "K": "12345"},
        ])

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import-roster", "--source", str(source),
        ])

        assert "Rows read:" in result.output
        assert "Imported:" in result.output
        assert "AAR code resolution:" in result.output
        assert "Capacity resolution:" in result.output

    def test_full_resync_overwrites_prior_cars_yaml(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "cars.yaml").write_text(
            "- id: OLD-1\n  road: OLD\n  car_number: '1'\n  aar_code: XM\n  capacity_tons: 50\n"
        )
        source = _make_roster_xlsx(tmp_path, [
            {"B": "PRR", "F": "40' Box Car", "K": "12345"},
        ])

        runner = CliRunner()
        runner.invoke(main, [
            "--data-path", str(data_dir),
            "import-roster", "--source", str(source),
        ])

        cars = _yaml.safe_load((data_dir / "cars.yaml").read_text())
        ids = {c["id"] for c in cars}
        assert "OLD-1" not in ids
        assert "PRR-12345" in ids

    def test_unmapped_types_shown_in_report(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        source = _make_roster_xlsx(tmp_path, [
            {"B": "PRR", "F": "Mystery Custom Kitbash", "K": "12345"},
        ])

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import-roster", "--source", str(source),
        ])

        assert "Unmapped types" in result.output
        assert "Mystery Custom Kitbash" in result.output

    def test_uses_car_type_map_from_data_path(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "car_type_map.yaml").write_text(
            "- source_text: \"Custom Decorated Hopper\"\n  aar_code: LO\n"
        )
        source = _make_roster_xlsx(tmp_path, [
            {"B": "PRR", "F": "Custom Decorated Hopper", "K": "12345"},
        ])

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import-roster", "--source", str(source),
        ])

        assert result.exit_code == 0, result.output
        cars = _yaml.safe_load((data_dir / "cars.yaml").read_text())
        assert cars[0]["aar_code"] == "LO"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_roster_import.py -v -k TestImportRosterCommand`
Expected: FAIL with `Error: No such command 'import-roster'` (or similar
Click "no such command" failure reflected as non-zero `result.exit_code`)

- [ ] **Step 4: Write minimal implementation**

In `waybill_generator/cli.py`, add near the existing `import_catalog` command
(end of file):

```python
@main.command("import-roster")
@click.option("--source", required=True, type=click.Path(exists=True),
              help="Path to the roster .xlsx file (e.g. a OneDrive-synced spreadsheet)")
@click.pass_context
def import_roster(ctx, source):
    """Import the Freight Cars sheet from a roster spreadsheet into cars.yaml."""
    from waybill_generator.importers.roster_xlsx import (
        read_freight_cars, load_car_type_map, build_cars,
    )

    data_path = Path(ctx.obj["data_path"])
    car_type_map_path = data_path / "car_type_map.yaml"

    rows = read_freight_cars(Path(source))
    car_type_map = load_car_type_map(car_type_map_path)
    cars, report = build_cars(rows, car_type_map)

    cars_path = data_path / "cars.yaml"
    cars_path.write_text(
        yaml.dump(
            [c.model_dump(exclude_none=True) for c in cars],
            default_flow_style=False,
            allow_unicode=True,
        )
    )

    click.echo(f"\nImporting roster: {Path(source).name}  [Freight Cars]")
    click.echo(f"  Rows read:             {report.rows_read}")
    click.echo(f"  Skipped (sold):        {report.skipped_sold}")
    click.echo(f"  Skipped (incomplete):  {report.skipped_incomplete}")
    click.echo(f"  Imported:              {report.imported}")
    click.echo(f"  Duplicate ids:         {len(report.duplicate_ids)}")
    click.echo()
    click.echo("AAR code resolution:")
    click.echo(f"  map-matched:      {report.map_matched}")
    click.echo(f"  keyword-matched:  {report.keyword_matched}")
    click.echo(f"  fallback (XM):    {report.fallback_matched}")
    click.echo()
    click.echo("Capacity resolution:")
    click.echo(f"  regex-extracted:  {report.capacity_regex}")
    click.echo(f"  default table:    {report.capacity_default}")

    if report.duplicate_ids:
        click.echo()
        click.echo("Duplicate ids (last row wins):")
        for id_ in report.duplicate_ids:
            click.echo(f"  {id_}")

    if report.unmapped_types:
        click.echo()
        click.echo("Unmapped types (add to car_type_map.yaml to resolve):")
        for type_text, count in sorted(report.unmapped_types.items(), key=lambda x: -x[1]):
            noun = "car" if count == 1 else "cars"
            click.echo(f"  {type_text!r:<50} {count} {noun}")
```

This uses `yaml`, `click`, and `Path` which are already imported at the top
of `cli.py` — no new top-level imports needed there.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_roster_import.py -v -k TestImportRosterCommand`
Expected: PASS (6 tests)

- [ ] **Step 6: Run the full project test suite**

Run: `pytest -v`
Expected: PASS (all tests, no regressions)

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/cli.py data/car_type_map.yaml tests/test_roster_import.py
git commit -m "feat: add waybill import-roster CLI command"
```

---

## Manual Verification (not automated)

After all tasks are complete, run against the real spreadsheet to sanity-check
the report output and a sample of `data/cars.yaml` before relying on it:

```bash
waybill import-roster --source "/Users/krolla/OneDrive/Trains/Modeling/Ho Models.xlsx"
```

Review the printed report's "Unmapped types" list and add entries to
`data/car_type_map.yaml` for any recurring types worth mapping precisely,
then re-run.
