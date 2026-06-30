# Mass Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `waybill import FILEPATH` CLI command that parses OpSIG and JBritton source files, normalizes commodities and car types, and writes entries to `data/industry_catalog.yaml` with idempotent re-import support.

**Architecture:** New `waybill_generator/importers/` package handles parsing (one module per source format), grouping (one row per commodity → one entry per industry), and normalization (commodity map + auto-match + car type inference). `CatalogRepository` gains one write method. The CLI ties it together and prints a report.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, Click, xlrd (new dependency for `.xls` files)

## Global Constraints

- Python 3.11+; use `str | None` union syntax, not `Optional`
- Pydantic v2 — use `model_dump()`, not `.dict()`
- All test fixtures are inline strings, not files from `industry_database/`
- `data_path` defaults to `./data`; `industry_database/` is a separate root-level dir
- Line length ≤ 100 (ruff enforced)

---

### Task 1: Dependencies and data files

**Files:**
- Modify: `pyproject.toml`
- Create: `waybill_generator/importers/__init__.py`
- Create: `industry_database/commodity_map.yaml`
- Create: `industry_database/opsig_car_map.yaml`
- Create: `industry_database/README.md`

**Interfaces:**
- Produces: `industry_database/commodity_map.yaml` and `opsig_car_map.yaml` consumed by `normalizer.py` in Task 5

- [ ] **Step 1: Add xlrd to pyproject.toml**

In `pyproject.toml`, change the `dependencies` list to:

```toml
dependencies = [
    "click>=8",
    "pydantic>=2",
    "reportlab>=4",
    "pyyaml>=6",
    "xlrd>=2",
]
```

- [ ] **Step 2: Install the new dependency**

```bash
pip install -e ".[dev]"
```

Expected: installs without error; `xlrd` appears in `pip list`.

- [ ] **Step 3: Create the importers package**

Create `waybill_generator/importers/__init__.py` — empty file.

- [ ] **Step 4: Create commodity_map.yaml**

Create `industry_database/commodity_map.yaml`:

```yaml
# Map source-file commodity text to project commodity ids.
# Lookup is case-insensitive exact match on source_text.
# Set commodity_id to null to mark as intentionally unmapped
# (stays as free-text and is suppressed from the unmatched report).
#
# Example:
# - source_text: "Petroleum Products"
#   commodity_id: null
# - source_text: "Specialty Steel"
#   commodity_id: steel
```

- [ ] **Step 5: Create opsig_car_map.yaml**

Create `industry_database/opsig_car_map.yaml`:

```yaml
# OpSIG shorthand car type codes → AAR codes
# Pre-populated based on observed OpSIG data.
# Add new mappings as unknown codes appear in import reports.
# CB mapping is uncertain — update if source documentation clarifies.
T: TM    # Tank Car
H: HM    # Open Hopper
CH: LO   # Covered Hopper
B: XM    # Box Car
G: GB    # Gondola
CB: XM   # Covered/Combination Box (uncertain — verify against OpSIG docs)
```

- [ ] **Step 6: Create industry_database/README.md**

Create `industry_database/README.md`:

```markdown
# Industry Database

Source files for bulk import into `data/industry_catalog.yaml` via `waybill import`.

## Directory layout

```
industry_database/
  opsig/              OpSIG files (.txt and .xls)
  jbritton/           JBritton files (.txt)
  commodity_map.yaml  User-maintained commodity normalization overrides
  opsig_car_map.yaml  Pre-populated OpSIG car code → AAR code map
```

## OpSIG .txt format

10-column TSV, Windows CRLF (latin-1 encoding):

| Col | Field      | Notes                             |
|-----|------------|-----------------------------------|
| 0   | year       | e.g. `2004`, `55`, `90`           |
| 1   | name       | Industry name                     |
| 2   | city       |                                   |
| 3   | state      | 2-letter abbreviation             |
| 4   | railroad   | e.g. `PRR`, `P&W`, `CSX`         |
| 5   | direction  | `S` (ships) or `R` (receives)     |
| 6   | commodity  | Free-text                         |
| 7   | notes      | Description / process notes       |
| 8   | volume     | e.g. `VH`, `H(e)`, `M-H`         |
| 9   | car_types  | Comma-sep OpSIG codes, e.g. `CH,T`|

## OpSIG .xls format

Assumed same column layout as .txt. Verify during import — if columns differ,
update this README and `opsig.py`.

## JBritton .txt format

256-column wide TSV, Windows CRLF (latin-1 encoding). Most columns are empty.
Effective columns:

| Col | Field        | Notes                                   |
|-----|--------------|-----------------------------------------|
| 0   | year         |                                         |
| 1   | name         | Industry name                           |
| 2   | city         |                                         |
| 3   | state        |                                         |
| 4   | railroad     |                                         |
| 5   | direction    | `S`, `R`, or blank (station/delivery)   |
| 6   | commodity    | Free-text, or blank                     |
| 7   | (blank)      |                                         |
| 8   | location_ref | Division + milepost (stored as `notes`) |
| 9   | source_ref   | e.g. `pennsyrr.com PRR CT1000`          |

No car types. Car types are inferred from matched commodity ids.

## commodity_map.yaml

User-editable. Case-insensitive exact match on `source_text`.
`commodity_id: null` suppresses the entry from the unmatched-commodities report.

## opsig_car_map.yaml

Pre-populated. Do not edit casually — maps OpSIG shorthand to AAR codes.
Add new mappings when unknown codes appear in import reports.
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml waybill_generator/importers/__init__.py \
        industry_database/commodity_map.yaml industry_database/opsig_car_map.yaml \
        industry_database/README.md
git commit -m "feat: add importers package scaffold and industry_database data files"
```

---

### Task 2: ImportedRow, grouper, and ID generation

**Files:**
- Create: `waybill_generator/importers/base.py`
- Create: `tests/test_importers.py`

**Interfaces:**
- Produces:
  - `ImportedRow` dataclass — consumed by all parsers (Tasks 3, 4)
  - `group_rows(rows: list[ImportedRow]) -> list[dict]` — consumed by normalizer (Task 5) and CLI (Task 7)
  - `make_catalog_id(source_file, name, city, state, railroad) -> str` — consumed by normalizer (Task 5)

- [ ] **Step 1: Write failing tests**

Create `tests/test_importers.py`:

```python
from waybill_generator.importers.base import ImportedRow, group_rows, make_catalog_id


def _row(
    name="Acme Corp", city="Reading", state="PA", railroad="PRR",
    direction="S", commodity="coal", notes="", car_types=None, source_ref="",
) -> ImportedRow:
    return ImportedRow(
        year="1945", name=name, city=city, state=state, railroad=railroad,
        direction=direction, commodity=commodity, notes=notes,
        car_types=car_types or [], source_ref=source_ref,
    )


class TestGroupRows:
    def test_single_row_ships(self):
        groups = group_rows([_row(direction="S", commodity="coal")])
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == []

    def test_single_row_receives(self):
        groups = group_rows([_row(direction="R", commodity="lumber")])
        assert groups[0]["receives"] == ["lumber"]
        assert groups[0]["ships"] == []

    def test_blank_direction_non_empty_commodity_goes_to_both(self):
        groups = group_rows([_row(direction="", commodity="freight")])
        assert "freight" in groups[0]["ships"]
        assert "freight" in groups[0]["receives"]

    def test_blank_direction_blank_commodity_ignored(self):
        groups = group_rows([_row(direction="", commodity="")])
        assert groups[0]["ships"] == []
        assert groups[0]["receives"] == []

    def test_multiple_rows_same_industry_grouped(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="R", commodity="lumber")]
        groups = group_rows(rows)
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == ["lumber"]

    def test_duplicate_commodity_deduplicated(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="S", commodity="coal")]
        groups = group_rows(rows)
        assert groups[0]["ships"].count("coal") == 1

    def test_different_industries_produce_separate_groups(self):
        rows = [_row(name="A Corp"), _row(name="B Corp")]
        groups = group_rows(rows)
        assert len(groups) == 2

    def test_notes_taken_from_first_non_empty(self):
        rows = [_row(notes=""), _row(notes="Main Line - 220"), _row(notes="Different note")]
        groups = group_rows(rows)
        assert groups[0]["notes"] == "Main Line - 220"

    def test_car_types_merged_and_deduplicated(self):
        rows = [
            _row(car_types=["HM", "GB"]),
            _row(direction="R", commodity="ore", car_types=["GB", "XM"]),
        ]
        groups = group_rows(rows)
        assert set(groups[0]["raw_car_types"]) == {"HM", "GB", "XM"}

    def test_source_ref_from_first_row(self):
        rows = [_row(source_ref="pennsyrr.com"), _row(source_ref="other")]
        groups = group_rows(rows)
        assert groups[0]["source_ref"] == "pennsyrr.com"


class TestMakeCatalogId:
    def test_returns_cat_prefixed_8_hex(self):
        id_ = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        assert id_.startswith("cat-")
        assert len(id_) == 12  # "cat-" + 8 hex chars

    def test_deterministic(self):
        a = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        b = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        assert a == b

    def test_different_source_file_different_id(self):
        a = make_catalog_id("file-a.txt", "Acme", "Reading", "PA", "PRR")
        b = make_catalog_id("file-b.txt", "Acme", "Reading", "PA", "PRR")
        assert a != b

    def test_different_name_different_id(self):
        a = make_catalog_id("file.txt", "Acme", "Reading", "PA", "PRR")
        b = make_catalog_id("file.txt", "Other Corp", "Reading", "PA", "PRR")
        assert a != b
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_importers.py -v
```

Expected: `ImportError` — `waybill_generator.importers.base` does not exist yet.

- [ ] **Step 3: Implement base.py**

Create `waybill_generator/importers/base.py`:

```python
import hashlib
from dataclasses import dataclass, field


@dataclass
class ImportedRow:
    year: str
    name: str
    city: str
    state: str
    railroad: str
    direction: str        # "S", "R", or ""
    commodity: str
    notes: str
    car_types: list[str]  # raw source codes; empty for JBritton
    source_ref: str


def group_rows(rows: list[ImportedRow]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for row in rows:
        key = (row.name.strip(), row.city.strip(), row.state.strip(), row.railroad.strip())
        if key not in groups:
            groups[key] = {
                "name": row.name.strip(),
                "city": row.city.strip(),
                "state": row.state.strip(),
                "railroad": row.railroad.strip(),
                "ships": [],
                "receives": [],
                "notes": "",
                "raw_car_types": [],
                "source_ref": row.source_ref.strip(),
            }
        g = groups[key]
        commodity = row.commodity.strip()
        direction = row.direction.strip().upper()
        if commodity:
            if direction == "S":
                if commodity not in g["ships"]:
                    g["ships"].append(commodity)
            elif direction == "R":
                if commodity not in g["receives"]:
                    g["receives"].append(commodity)
            else:
                if commodity not in g["ships"]:
                    g["ships"].append(commodity)
                if commodity not in g["receives"]:
                    g["receives"].append(commodity)
        if not g["notes"] and row.notes.strip():
            g["notes"] = row.notes.strip()
        for ct in row.car_types:
            ct = ct.strip()
            if ct and ct not in g["raw_car_types"]:
                g["raw_car_types"].append(ct)
    return list(groups.values())


def make_catalog_id(source_file: str, name: str, city: str, state: str, railroad: str) -> str:
    key = f"{source_file}|{name}|{city}|{state}|{railroad}"
    return "cat-" + hashlib.sha256(key.encode()).hexdigest()[:8]
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_importers.py -v
```

Expected: all `TestGroupRows` and `TestMakeCatalogId` tests pass.

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/importers/base.py tests/test_importers.py
git commit -m "feat: add ImportedRow dataclass, grouper, and catalog ID generation"
```

---

### Task 3: OpSIG parser

**Files:**
- Create: `waybill_generator/importers/opsig.py`
- Modify: `tests/test_importers.py` (append tests)

**Interfaces:**
- Consumes: `ImportedRow` from `base.py`
- Produces: `parse_opsig(filepath: Path) -> list[ImportedRow]` — consumed by CLI (Task 7)
- Internal: `_parse_line(line: list[str]) -> ImportedRow | None` — tested directly

- [ ] **Step 1: Append OpSIG tests to tests/test_importers.py**

Add to the bottom of `tests/test_importers.py`:

```python
from waybill_generator.importers.opsig import parse_opsig, _parse_line as opsig_parse_line


class TestOpSIGParseLine:
    def test_full_row(self):
        line = ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S",
                "latex, plastic pellets", "butadiene prod.mfg", "VH(e)", "CH,T"]
        row = opsig_parse_line(line)
        assert row is not None
        assert row.name == "Dow"
        assert row.city == "Allyn's Point"
        assert row.state == "CT"
        assert row.railroad == "P&W"
        assert row.direction == "S"
        assert row.commodity == "latex, plastic pellets"
        assert row.notes == "butadiene prod.mfg"
        assert row.car_types == ["CH", "T"]
        assert row.source_ref == ""

    def test_blank_name_returns_none(self):
        line = ["2004", "", "City", "PA", "PRR", "S", "coal", "", "", ""]
        assert opsig_parse_line(line) is None

    def test_short_line_padded_to_10(self):
        line = ["2004", "Acme", "Reading", "PA", "PRR", "S", "coal"]
        row = opsig_parse_line(line)
        assert row is not None
        assert row.car_types == []

    def test_single_car_type(self):
        line = ["55", "Firm", "City", "PA", "PRR", "S", "steel", "", "", "G"]
        row = opsig_parse_line(line)
        assert row.car_types == ["G"]

    def test_receives_direction(self):
        line = ["2004", "Mill", "City", "PA", "PRR", "R", "coal", "", "", "HM"]
        row = opsig_parse_line(line)
        assert row.direction == "R"

    def test_blank_car_type_column(self):
        line = ["2004", "Mill", "City", "PA", "PRR", "R", "coal", "", "", ""]
        row = opsig_parse_line(line)
        assert row.car_types == []


class TestParseOpSIGFile:
    def test_parses_txt_rows(self, tmp_path):
        content = (
            "2004\tDow\tAllyn's Point\tCT\tP&W\tS\tlatex\tbutadiene\tVH\tCH,T\r\n"
            "2004\tPeter Paul\tBeacon Falls\tCT\tGRS\tR\tcorn syrup\tcandy mfg\tH\tT\r\n"
            "\t\t\t\t\t\t\t\t\t\r\n"
        )
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_opsig(p)
        assert len(rows) == 2
        assert rows[0].name == "Dow"
        assert rows[1].name == "Peter Paul"

    def test_skips_blank_name_rows(self, tmp_path):
        content = "\t\t\t\t\t\t\t\t\t\r\n2004\tAcme\tCity\tPA\tPRR\tS\tcoal\t\t\tH\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Acme"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_importers.py::TestOpSIGParseLine tests/test_importers.py::TestParseOpSIGFile -v
```

Expected: `ImportError` — `opsig` module does not exist yet.

- [ ] **Step 3: Implement opsig.py**

Create `waybill_generator/importers/opsig.py`:

```python
import csv
from pathlib import Path
from waybill_generator.importers.base import ImportedRow


def parse_opsig(filepath: Path) -> list[ImportedRow]:
    if filepath.suffix.lower() == ".xls":
        return _parse_xls(filepath)
    return _parse_txt(filepath)


def _parse_txt(filepath: Path) -> list[ImportedRow]:
    rows = []
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = _parse_line(line)
            if row:
                rows.append(row)
    return rows


def _parse_xls(filepath: Path) -> list[ImportedRow]:
    import xlrd
    wb = xlrd.open_workbook(str(filepath))
    ws = wb.sheet_by_index(0)
    rows = []
    for i in range(ws.nrows):
        line = [str(ws.cell_value(i, j)).strip() if j < ws.ncols else "" for j in range(10)]
        row = _parse_line(line)
        if row:
            rows.append(row)
    return rows


def _parse_line(line: list[str]) -> ImportedRow | None:
    while len(line) < 10:
        line.append("")
    name = line[1].strip()
    if not name:
        return None
    car_types = [c.strip() for c in line[9].split(",") if c.strip()]
    return ImportedRow(
        year=line[0].strip(),
        name=name,
        city=line[2].strip(),
        state=line[3].strip(),
        railroad=line[4].strip(),
        direction=line[5].strip(),
        commodity=line[6].strip(),
        notes=line[7].strip(),
        car_types=car_types,
        source_ref="",
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_importers.py::TestOpSIGParseLine tests/test_importers.py::TestParseOpSIGFile -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/importers/opsig.py tests/test_importers.py
git commit -m "feat: add OpSIG TSV and XLS parser"
```

---

### Task 4: JBritton parser

**Files:**
- Create: `waybill_generator/importers/jbritton.py`
- Modify: `tests/test_importers.py` (append tests)

**Interfaces:**
- Consumes: `ImportedRow` from `base.py`
- Produces: `parse_jbritton(filepath: Path) -> list[ImportedRow]` — consumed by CLI (Task 7)
- Internal: `_parse_line(line: list[str]) -> ImportedRow | None`

- [ ] **Step 1: Append JBritton tests to tests/test_importers.py**

Add to the bottom of `tests/test_importers.py`:

```python
from waybill_generator.importers.jbritton import parse_jbritton, _parse_line as jb_parse_line


class TestJBrittonParseLine:
    def _line(
        self, name="Standard Novelty Works", city="Duncannon", state="PA",
        railroad="PRR", direction="S", commodity="Sleds",
        location_ref="Middle Division - Main Line - 208",
        source_ref="pennsyrr.com PRR CT1000",
    ) -> list[str]:
        line = ["1945", name, city, state, railroad, direction, commodity,
                "", location_ref, source_ref]
        line.extend([""] * (256 - len(line)))
        return line

    def test_full_row(self):
        row = jb_parse_line(self._line())
        assert row is not None
        assert row.name == "Standard Novelty Works"
        assert row.city == "Duncannon"
        assert row.state == "PA"
        assert row.railroad == "PRR"
        assert row.direction == "S"
        assert row.commodity == "Sleds"
        assert row.notes == "Middle Division - Main Line - 208"
        assert row.source_ref == "pennsyrr.com PRR CT1000"
        assert row.car_types == []

    def test_blank_name_returns_none(self):
        assert jb_parse_line(self._line(name="")) is None

    def test_blank_direction_allowed(self):
        row = jb_parse_line(self._line(direction="", commodity=""))
        assert row is not None
        assert row.direction == ""
        assert row.commodity == ""

    def test_short_line_padded(self):
        line = ["1945", "Station", "Perdix", "PA", "PRR"]
        row = jb_parse_line(line)
        assert row is not None
        assert row.commodity == ""
        assert row.notes == ""
        assert row.source_ref == ""


class TestParseJBrittonFile:
    def test_parses_rows(self, tmp_path):
        tabs = "\t" * 246
        content = (
            f"1945\tStandard Novelty Works\tDuncannon\tPA\tPRR\tS\tSleds\t\tMain Line\tpennsyrr.com{tabs}\r\n"
            f"1945\tStandard Novelty Works\tDuncannon\tPA\tPRR\tR\tLumber\t\tMain Line\tpennsyrr.com{tabs}\r\n"
            f"1945\tStation\tPerdix\tPA\tPRR\t\t\t\tMain Line\tpennsyrr.com{tabs}\r\n"
        )
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_jbritton(p)
        assert len(rows) == 3
        assert rows[0].direction == "S"
        assert rows[1].direction == "R"
        assert rows[2].direction == ""

    def test_no_car_types(self, tmp_path):
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tsource{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows = parse_jbritton(p)
        assert rows[0].car_types == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_importers.py::TestJBrittonParseLine tests/test_importers.py::TestParseJBrittonFile -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement jbritton.py**

Create `waybill_generator/importers/jbritton.py`:

```python
import csv
from pathlib import Path
from waybill_generator.importers.base import ImportedRow


def parse_jbritton(filepath: Path) -> list[ImportedRow]:
    rows = []
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = _parse_line(line)
            if row:
                rows.append(row)
    return rows


def _parse_line(line: list[str]) -> ImportedRow | None:
    while len(line) < 10:
        line.append("")
    name = line[1].strip()
    if not name:
        return None
    return ImportedRow(
        year=line[0].strip(),
        name=name,
        city=line[2].strip(),
        state=line[3].strip(),
        railroad=line[4].strip(),
        direction=line[5].strip(),
        commodity=line[6].strip(),
        notes=line[8].strip(),
        car_types=[],
        source_ref=line[9].strip(),
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_importers.py::TestJBrittonParseLine tests/test_importers.py::TestParseJBrittonFile -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/importers/jbritton.py tests/test_importers.py
git commit -m "feat: add JBritton wide-TSV parser"
```

---

### Task 5: Normalizer

**Files:**
- Create: `waybill_generator/importers/normalizer.py`
- Modify: `tests/test_importers.py` (append tests)

**Interfaces:**
- Consumes: `group_rows` output (list of dicts), `make_catalog_id` from `base.py`; `CatalogIndustry` from `models/catalog.py`
- Produces:
  - `normalize_entries(grouped, source, source_file, commodity_map_path, opsig_car_map_path, commodities_path) -> tuple[list[CatalogIndustry], NormReport]` — consumed by CLI (Task 7)
  - `NormReport` dataclass with fields: `map_count: int`, `auto_count: int`, `free_count: int`, `unmatched: dict[str, int]`, `unknown_car_codes: list[str]`

- [ ] **Step 1: Append normalizer tests to tests/test_importers.py**

Add to the bottom of `tests/test_importers.py`:

```python
import pytest
from waybill_generator.importers.normalizer import (
    load_commodity_map,
    build_auto_map,
    load_opsig_car_map,
    _normalize_commodity,
    normalize_entries,
    NormReport,
)

_COMMODITIES_YAML = """\
- id: coal
  name: Bituminous Coal
  aar_code: "01210"
  acceptable_car_types: [HM, GB]
- id: lumber
  name: Lumber
  aar_code: "02410"
  acceptable_car_types: [FM, XM]
"""

_OPSIG_CAR_MAP_YAML = "T: TM\nH: HM\nB: XM\nCH: LO\nG: GB\n"


@pytest.fixture
def commodities_file(tmp_path):
    p = tmp_path / "commodities.yaml"
    p.write_text(_COMMODITIES_YAML)
    return p


@pytest.fixture
def opsig_car_map_file(tmp_path):
    p = tmp_path / "opsig_car_map.yaml"
    p.write_text(_OPSIG_CAR_MAP_YAML)
    return p


@pytest.fixture
def empty_commodity_map(tmp_path):
    p = tmp_path / "commodity_map.yaml"
    p.write_text("")
    return p


def _grouped(ships=None, receives=None, raw_car_types=None, source_ref="") -> list[dict]:
    return [{
        "name": "Test Industry", "city": "Reading", "state": "PA", "railroad": "PRR",
        "ships": ships or [], "receives": receives or [],
        "notes": "", "raw_car_types": raw_car_types or [], "source_ref": source_ref,
    }]


class TestLoadCommodityMap:
    def test_loads_entries_case_insensitive(self, tmp_path):
        p = tmp_path / "commodity_map.yaml"
        p.write_text("- source_text: Petroleum Products\n  commodity_id: null\n"
                     "- source_text: Specialty Steel\n  commodity_id: steel\n")
        cmap = load_commodity_map(p)
        assert cmap["petroleum products"] is None
        assert cmap["specialty steel"] == "steel"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_commodity_map(tmp_path / "nonexistent.yaml") == {}


class TestBuildAutoMap:
    def test_builds_from_commodity_names(self, commodities_file):
        auto = build_auto_map(commodities_file)
        assert auto["bituminous coal"] == "coal"
        assert auto["lumber"] == "lumber"


class TestLoadOpSIGCarMap:
    def test_loads_and_uppercases_keys(self, opsig_car_map_file):
        cmap = load_opsig_car_map(opsig_car_map_file)
        assert cmap["T"] == "TM"
        assert cmap["H"] == "HM"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_opsig_car_map(tmp_path / "nonexistent.yaml") == {}


class TestNormalizeCommodity:
    def setup_method(self):
        self.auto_map = {"bituminous coal": "coal", "lumber": "lumber"}
        self.commodity_map = {"petroleum products": None, "specialty steel": "steel"}

    def test_explicit_map_wins_over_auto(self):
        # "Specialty Steel" would not auto-match, but explicit map hits
        norm, mt = _normalize_commodity("Specialty Steel", self.commodity_map, self.auto_map)
        assert norm == "steel"
        assert mt == "map"

    def test_null_sentinel_keeps_free_text(self):
        norm, mt = _normalize_commodity("Petroleum Products", self.commodity_map, self.auto_map)
        assert norm == "Petroleum Products"
        assert mt == "map"

    def test_auto_match_case_insensitive(self):
        norm, mt = _normalize_commodity("Bituminous Coal", {}, self.auto_map)
        assert norm == "coal"
        assert mt == "auto"

    def test_auto_match_substring_source_contains_name(self):
        # "lumber" is in "lumber supply"
        norm, mt = _normalize_commodity("lumber supply", {}, self.auto_map)
        assert norm == "lumber"
        assert mt == "auto"

    def test_auto_match_substring_name_contains_source(self):
        # "coal" is in "bituminous coal"
        norm, mt = _normalize_commodity("coal", {}, self.auto_map)
        assert norm == "coal"
        assert mt == "auto"

    def test_free_text_fallback(self):
        norm, mt = _normalize_commodity("Sleds", {}, self.auto_map)
        assert norm == "Sleds"
        assert mt == "free"


class TestNormalizeEntries:
    def test_auto_matched_commodity_written_as_id(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, report = normalize_entries(
            _grouped(ships=["Bituminous Coal"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert entries[0].ships == ["coal"]
        assert report.auto_count == 1
        assert report.map_count == 0

    def test_map_matched_wins_over_auto(
        self, tmp_path, commodities_file, opsig_car_map_file
    ):
        cmap = tmp_path / "commodity_map.yaml"
        cmap.write_text("- source_text: Bituminous Coal\n  commodity_id: coal-override\n")
        entries, report = normalize_entries(
            _grouped(ships=["Bituminous Coal"]), "jbritton", "file.txt",
            cmap, opsig_car_map_file, commodities_file,
        )
        assert entries[0].ships == ["coal-override"]
        assert report.map_count == 1

    def test_free_text_tracked_in_report(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, report = normalize_entries(
            _grouped(ships=["Sleds"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert entries[0].ships == ["Sleds"]
        assert report.free_count == 1
        assert "Sleds" in report.unmatched

    def test_null_sentinel_suppresses_unmatched_report(
        self, tmp_path, commodities_file, opsig_car_map_file
    ):
        cmap = tmp_path / "commodity_map.yaml"
        cmap.write_text("- source_text: Sleds\n  commodity_id:\n")
        _, report = normalize_entries(
            _grouped(ships=["Sleds"]), "jbritton", "file.txt",
            cmap, opsig_car_map_file, commodities_file,
        )
        assert "Sleds" not in report.unmatched

    def test_opsig_car_types_mapped_to_aar(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, report = normalize_entries(
            _grouped(ships=["coal"], raw_car_types=["H", "T"]), "opsig", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert "HM" in entries[0].car_types
        assert "TM" in entries[0].car_types

    def test_unknown_opsig_car_code_logged(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        _, report = normalize_entries(
            _grouped(ships=["coal"], raw_car_types=["ZZ"]), "opsig", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert "ZZ" in report.unknown_car_codes

    def test_jbritton_car_types_inferred_from_matched_commodity(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, _ = normalize_entries(
            _grouped(ships=["Bituminous Coal"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert "HM" in entries[0].car_types
        assert "GB" in entries[0].car_types

    def test_jbritton_unmatched_commodity_empty_car_types(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, _ = normalize_entries(
            _grouped(ships=["Sleds"]), "jbritton", "file.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        assert entries[0].car_types == []

    def test_entry_fields_set_correctly(
        self, commodities_file, opsig_car_map_file, empty_commodity_map
    ):
        entries, _ = normalize_entries(
            _grouped(ships=["coal"], source_ref="pennsyrr.com"),
            "jbritton", "prr_middle.txt",
            empty_commodity_map, opsig_car_map_file, commodities_file,
        )
        e = entries[0]
        assert e.source == "jbritton"
        assert e.source_file == "prr_middle.txt"
        assert e.source_ref == "pennsyrr.com"
        assert e.id.startswith("cat-")
        assert len(e.id) == 12
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_importers.py -k "Normaliz or LoadCommodity or BuildAuto or LoadOpSIG" -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement normalizer.py**

Create `waybill_generator/importers/normalizer.py`:

```python
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from waybill_generator.models.catalog import CatalogIndustry
from waybill_generator.importers.base import make_catalog_id


@dataclass
class NormReport:
    map_count: int = 0
    auto_count: int = 0
    free_count: int = 0
    unmatched: dict[str, int] = field(default_factory=dict)
    unknown_car_codes: list[str] = field(default_factory=list)


def load_commodity_map(path: Path) -> dict[str, str | None]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or []
    return {entry["source_text"].lower(): entry.get("commodity_id") for entry in raw}


def build_auto_map(commodities_path: Path) -> dict[str, str]:
    raw = yaml.safe_load(commodities_path.read_text()) or []
    return {c["name"].lower(): c["id"] for c in raw}


def load_opsig_car_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    return {k.upper(): v for k, v in raw.items()}


def _normalize_commodity(
    source_text: str,
    commodity_map: dict[str, str | None],
    auto_map: dict[str, str],
) -> tuple[str, str]:
    lower = source_text.lower()
    if lower in commodity_map:
        mapped = commodity_map[lower]
        return (source_text if mapped is None else mapped, "map")
    for name, cid in auto_map.items():
        if name in lower or lower in name:
            return (cid, "auto")
    return (source_text, "free")


def normalize_entries(
    grouped: list[dict],
    source: str,
    source_file: str,
    commodity_map_path: Path,
    opsig_car_map_path: Path,
    commodities_path: Path,
) -> tuple[list[CatalogIndustry], NormReport]:
    commodity_map = load_commodity_map(commodity_map_path)
    auto_map = build_auto_map(commodities_path)
    opsig_car_map = load_opsig_car_map(opsig_car_map_path)
    raw_commodities = yaml.safe_load(commodities_path.read_text()) or []
    commodities_by_id = {c["id"]: c for c in raw_commodities}

    report = NormReport()
    entries = []

    for g in grouped:
        norm_ships, resolved_ship_ids, ship_best = _normalize_list(
            g["ships"], commodity_map, auto_map
        )
        norm_receives, resolved_recv_ids, recv_best = _normalize_list(
            g["receives"], commodity_map, auto_map
        )

        best = "free"
        for b in [ship_best, recv_best]:
            if b == "map":
                best = "map"
                break
            if b == "auto":
                best = "auto"
        if best == "map":
            report.map_count += 1
        elif best == "auto":
            report.auto_count += 1
        else:
            report.free_count += 1

        all_source = list(dict.fromkeys(g["ships"] + g["receives"]))
        for commodity in all_source:
            if not commodity:
                continue
            lower = commodity.lower()
            if lower in commodity_map and commodity_map[lower] is None:
                continue
            _, mt = _normalize_commodity(commodity, commodity_map, auto_map)
            if mt == "free":
                report.unmatched[commodity] = report.unmatched.get(commodity, 0) + 1

        resolved_ids = list(dict.fromkeys(resolved_ship_ids + resolved_recv_ids))
        if source == "opsig" and g["raw_car_types"]:
            car_types = []
            for code in g["raw_car_types"]:
                aar = opsig_car_map.get(code.upper())
                if aar:
                    if aar not in car_types:
                        car_types.append(aar)
                elif code not in report.unknown_car_codes:
                    report.unknown_car_codes.append(code)
        else:
            car_types = []
            for cid in resolved_ids:
                if cid in commodities_by_id:
                    for ct in commodities_by_id[cid].get("acceptable_car_types", []):
                        if ct not in car_types:
                            car_types.append(ct)

        entries.append(CatalogIndustry(
            id=make_catalog_id(source_file, g["name"], g["city"], g["state"], g["railroad"]),
            name=g["name"],
            city=g["city"],
            state=g["state"],
            railroad_id=g["railroad"] or None,
            source=source,
            source_file=source_file,
            source_ref=g["source_ref"] or None,
            ships=norm_ships,
            receives=norm_receives,
            car_types=car_types,
            notes=g["notes"] or None,
        ))

    return entries, report


def _normalize_list(
    commodities: list[str],
    commodity_map: dict[str, str | None],
    auto_map: dict[str, str],
) -> tuple[list[str], list[str], str]:
    """Returns (normalized_list, resolved_ids, best_match_type)."""
    normalized = []
    resolved_ids = []
    best = "free"
    for commodity in commodities:
        if not commodity:
            continue
        norm, mt = _normalize_commodity(commodity, commodity_map, auto_map)
        normalized.append(norm)
        if mt == "map":
            best = "map"
            mapped_id = commodity_map.get(commodity.lower())
            if mapped_id is not None and mapped_id not in resolved_ids:
                resolved_ids.append(mapped_id)
        elif mt == "auto":
            if best == "free":
                best = "auto"
            if norm not in resolved_ids:
                resolved_ids.append(norm)
    return normalized, resolved_ids, best
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_importers.py -k "Normaliz or LoadCommodity or BuildAuto or LoadOpSIG" -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/importers/normalizer.py tests/test_importers.py
git commit -m "feat: add commodity and car type normalizer"
```

---

### Task 6: CatalogRepository.replace_from_source()

**Files:**
- Modify: `waybill_generator/repository/catalog_repo.py`
- Modify: `tests/test_importers.py` (append tests)

**Interfaces:**
- Produces: `CatalogRepository.replace_from_source(source_file: str, new_entries: list[CatalogIndustry]) -> tuple[int, int]`
  - Returns `(replaced_count, added_count)` where `replaced_count = |new_ids ∩ old_ids|`, `added_count = |new_ids - old_ids|`, and `replaced + added = len(new_entries)`

- [ ] **Step 1: Append replace_from_source tests to tests/test_importers.py**

Add to the bottom of `tests/test_importers.py`:

```python
import yaml
from waybill_generator.repository.catalog_repo import CatalogRepository
from waybill_generator.models.catalog import CatalogIndustry


def _cat_entry(id_, source_file="file.txt", source="opsig") -> CatalogIndustry:
    return CatalogIndustry(
        id=id_, name=f"Industry {id_}", city="Reading", state="PA",
        source=source, source_file=source_file,
    )


def _write_catalog(tmp_path, entries) -> "Path":
    p = tmp_path / "industry_catalog.yaml"
    data = [e.model_dump(exclude_none=True) for e in entries]
    p.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    return p


class TestReplaceFromSource:
    def test_replaces_entries_from_source_file_only(self, tmp_path):
        old = [_cat_entry("cat-aaa", "file.txt"), _cat_entry("cat-bbb", "other.txt")]
        p = _write_catalog(tmp_path, old)
        repo = CatalogRepository(p)
        repo.replace_from_source("file.txt", [_cat_entry("cat-ccc", "file.txt")])
        ids = {e.id for e in CatalogRepository(p).search(limit=999)}
        assert "cat-bbb" in ids   # different source_file — untouched
        assert "cat-aaa" not in ids  # same source_file — replaced
        assert "cat-ccc" in ids   # new entry

    def test_returns_replaced_and_added_counts(self, tmp_path):
        old = [_cat_entry("cat-aaa", "file.txt"), _cat_entry("cat-bbb", "file.txt")]
        p = _write_catalog(tmp_path, old)
        repo = CatalogRepository(p)
        new = [_cat_entry("cat-aaa", "file.txt"), _cat_entry("cat-ccc", "file.txt")]
        replaced, added = repo.replace_from_source("file.txt", new)
        assert replaced == 1   # cat-aaa in both old and new
        assert added == 1      # cat-ccc is new

    def test_first_import_returns_zero_replaced(self, tmp_path):
        p = tmp_path / "industry_catalog.yaml"
        p.write_text("")
        repo = CatalogRepository(p)
        replaced, added = repo.replace_from_source("file.txt", [_cat_entry("cat-new")])
        assert replaced == 0
        assert added == 1

    def test_manual_entries_never_removed(self, tmp_path):
        old = [
            _cat_entry("cat-manual", "manual", "manual"),
            _cat_entry("cat-old", "file.txt", "opsig"),
        ]
        p = _write_catalog(tmp_path, old)
        repo = CatalogRepository(p)
        repo.replace_from_source("file.txt", [_cat_entry("cat-new", "file.txt")])
        ids = {e.id for e in CatalogRepository(p).search(limit=999)}
        assert "cat-manual" in ids
        assert "cat-old" not in ids

    def test_reimport_same_file_replaces_all(self, tmp_path):
        first = [_cat_entry("cat-aaa"), _cat_entry("cat-bbb")]
        p = _write_catalog(tmp_path, first)
        repo = CatalogRepository(p)
        second = [_cat_entry("cat-aaa"), _cat_entry("cat-bbb")]
        replaced, added = repo.replace_from_source("file.txt", second)
        assert replaced == 2
        assert added == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_importers.py::TestReplaceFromSource -v
```

Expected: `AttributeError` — `CatalogRepository` has no `replace_from_source`.

- [ ] **Step 3: Add replace_from_source to catalog_repo.py**

In `waybill_generator/repository/catalog_repo.py`, add after the `search` method:

```python
    def replace_from_source(
        self,
        source_file: str,
        new_entries: list[CatalogIndustry],
    ) -> tuple[int, int]:
        raw = yaml.safe_load(self._path.read_text()) if self._path.exists() else None
        existing = [CatalogIndustry(**r) for r in (raw or [])]

        old_ids = {e.id for e in existing if e.source_file == source_file}
        new_ids = {e.id for e in new_entries}

        replaced = len(old_ids & new_ids)
        added = len(new_ids - old_ids)

        kept = [e for e in existing if e.source_file != source_file]
        merged = kept + new_entries

        self._path.write_text(
            yaml.dump(
                [e.model_dump(exclude_none=True) for e in merged],
                default_flow_style=False,
                allow_unicode=True,
            )
        )
        self._entries = None
        return replaced, added
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_importers.py::TestReplaceFromSource -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/repository/catalog_repo.py tests/test_importers.py
git commit -m "feat: add CatalogRepository.replace_from_source() for idempotent re-import"
```

---

### Task 7: CLI import command

**Files:**
- Modify: `waybill_generator/cli.py`
- Modify: `tests/test_importers.py` (append tests)

**Interfaces:**
- Consumes: `parse_opsig`, `parse_jbritton`, `group_rows`, `normalize_entries`, `CatalogRepository.replace_from_source`
- Command: `waybill import FILEPATH [--source opsig|jbritton] [--industry-db PATH]`
  - `--source`: optional; auto-detected from parent directory name (`opsig/` or `jbritton/`)
  - `--industry-db`: defaults to `./industry_database`
  - reads `commodity_map.yaml` and `opsig_car_map.yaml` from `--industry-db`
  - reads `commodities.yaml` and `industry_catalog.yaml` from `--data-path`

- [ ] **Step 1: Append CLI tests to tests/test_importers.py**

Add to the bottom of `tests/test_importers.py`:

```python
from click.testing import CliRunner
from waybill_generator.cli import main


def _setup_dirs(tmp_path, commodities_yaml="[]"):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "commodities.yaml").write_text(commodities_yaml)
    (data_dir / "industry_catalog.yaml").write_text("")
    db_dir = tmp_path / "industry_database"
    db_dir.mkdir()
    (db_dir / "commodity_map.yaml").write_text("")
    (db_dir / "opsig_car_map.yaml").write_text("H: HM\nT: TM\nB: XM\n")
    return data_dir, db_dir


class TestImportCommand:
    def test_jbritton_import_writes_catalog(self, tmp_path):
        data_dir, db_dir = _setup_dirs(
            tmp_path,
            "- id: lumber\n  name: Lumber\n  aar_code: '02410'\n  acceptable_car_types: [FM]\n",
        )
        jb_dir = db_dir / "jbritton"
        jb_dir.mkdir()
        tabs = "\t" * 246
        content = (
            f"1945\tAcme Lumber Co\tReading\tPA\tPRR\tS\tLumber\t\tMain Line\tsrc{tabs}\r\n"
            f"1945\tAcme Lumber Co\tReading\tPA\tPRR\tR\tHardware\t\tMain Line\tsrc{tabs}\r\n"
        )
        src = jb_dir / "prr_middle.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import", str(src),
            "--industry-db", str(db_dir),
        ])

        assert result.exit_code == 0, result.output
        assert "1 industries grouped" in result.output
        catalog = yaml.safe_load((data_dir / "industry_catalog.yaml").read_text()) or []
        assert len(catalog) == 1
        assert catalog[0]["name"] == "Acme Lumber Co"
        assert "lumber" in catalog[0]["ships"]

    def test_auto_detects_opsig_from_dir(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        opsig_dir = db_dir / "opsig"
        opsig_dir.mkdir()
        content = "2004\tAcme Corp\tCity\tPA\tPRR\tS\tCoal\tnotes\tH\tH\r\n"
        src = opsig_dir / "test.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import", str(src),
            "--industry-db", str(db_dir),
        ])
        assert result.exit_code == 0, result.output
        assert "[opsig]" in result.output

    def test_unknown_dir_requires_source_flag(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        src = tmp_path / "mystery.txt"
        src.write_text("2004\tAcme\tCity\tPA\tPRR\tS\tCoal\t\t\t\r\n")

        runner = CliRunner()
        result = runner.invoke(main, [
            "--data-path", str(data_dir),
            "import", str(src),
            "--industry-db", str(db_dir),
        ])
        assert result.exit_code != 0

    def test_report_shows_replaced_added_total(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        jb_dir = db_dir / "jbritton"
        jb_dir.mkdir()
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tsrc{tabs}\r\n"
        src = jb_dir / "test.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        # First import
        runner.invoke(main, ["--data-path", str(data_dir), "import", str(src),
                             "--industry-db", str(db_dir)])
        # Re-import
        result = runner.invoke(main, ["--data-path", str(data_dir), "import", str(src),
                                      "--industry-db", str(db_dir)])

        assert result.exit_code == 0
        assert "Replaced:" in result.output
        assert "Added:" in result.output
        assert "Catalog total:" in result.output

    def test_unmatched_commodities_shown_in_report(self, tmp_path):
        data_dir, db_dir = _setup_dirs(tmp_path)
        jb_dir = db_dir / "jbritton"
        jb_dir.mkdir()
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tSleds\t\tMain Line\tsrc{tabs}\r\n"
        src = jb_dir / "test.txt"
        src.write_bytes(content.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, ["--data-path", str(data_dir), "import", str(src),
                                      "--industry-db", str(db_dir)])
        assert "Sleds" in result.output
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_importers.py::TestImportCommand -v
```

Expected: `UsageError` or exit code errors — `import` command does not exist yet.

- [ ] **Step 3: Add import command to cli.py**

In `waybill_generator/cli.py`, add after the `add_industry` command:

```python
@main.command("import")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--source", default=None, type=click.Choice(["opsig", "jbritton"]),
              help="Source format (auto-detected from parent directory if omitted)")
@click.option("--industry-db", default="./industry_database", show_default=True,
              help="Path to industry_database directory")
@click.pass_context
def import_catalog(ctx, filepath, source, industry_db):
    """Import an OpSIG or JBritton source file into the industry catalog."""
    from waybill_generator.importers.opsig import parse_opsig
    from waybill_generator.importers.jbritton import parse_jbritton
    from waybill_generator.importers.base import group_rows
    from waybill_generator.importers.normalizer import normalize_entries

    fp = Path(filepath)
    db_path = Path(industry_db)
    data_path = Path(ctx.obj["data_path"])

    if source is None:
        parent = fp.parent.name.lower()
        if parent == "opsig":
            source = "opsig"
        elif parent == "jbritton":
            source = "jbritton"
        else:
            click.echo(
                f"Cannot auto-detect source from directory {fp.parent.name!r}. "
                "Use --source opsig or --source jbritton.",
                err=True,
            )
            raise SystemExit(1)

    rows = parse_opsig(fp) if source == "opsig" else parse_jbritton(fp)
    grouped = group_rows(rows)
    source_file = fp.name

    catalog_path = data_path / "industry_catalog.yaml"
    entries, report = normalize_entries(
        grouped, source, source_file,
        db_path / "commodity_map.yaml",
        db_path / "opsig_car_map.yaml",
        data_path / "commodities.yaml",
    )

    catalog_repo = CatalogRepository(catalog_path)
    replaced, added = catalog_repo.replace_from_source(source_file, entries)
    total = len(catalog_repo.search(limit=999_999))

    click.echo(f"\nImporting: {source_file}  [{source}]")
    click.echo(f"  Rows parsed:    {len(rows):<6}  →  {len(grouped)} industries grouped")
    click.echo(f"  Replaced:       {replaced:<6}  existing entries")
    click.echo(f"  Added:          {added:<6}  new entries")
    click.echo(f"  Catalog total:  {total:<6}  entries")
    click.echo()
    click.echo("Commodity normalization:")
    click.echo(f"  map-matched:    {report.map_count}")
    click.echo(f"  auto-matched:   {report.auto_count}")
    click.echo(f"  free-text:      {report.free_count}")

    if report.unmatched:
        click.echo()
        click.echo("Unmatched commodities (add to commodity_map.yaml to normalize):")
        for commodity, count in sorted(report.unmatched.items(), key=lambda x: -x[1]):
            noun = "industry" if count == 1 else "industries"
            click.echo(f"  {commodity!r:<40} {count} {noun}")

    if report.unknown_car_codes:
        click.echo()
        unknown = ", ".join(report.unknown_car_codes)
        click.echo(f"Unknown OpSIG car codes (not in opsig_car_map.yaml): {unknown}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_importers.py::TestImportCommand -v
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: all pass.

- [ ] **Step 6: Smoke test with a real source file**

```bash
waybill import industry_database/jbritton/OpSig_prrmiddle1945_170802.txt \
  --industry-db industry_database
```

Expected: report prints without error; `data/industry_catalog.yaml` is updated with PRR Middle Division entries.

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/cli.py tests/test_importers.py
git commit -m "feat: add waybill import command for OpSIG and JBritton source files"
```
