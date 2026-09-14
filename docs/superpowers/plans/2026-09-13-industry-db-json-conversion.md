# Industry Database JSON Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the raw OpSIG (`.xls`/`.txt`) and JBritton (`.txt`) industry source files under `industry_database/` into structured JSON (one JSON file per source file), as a reusable, normalization-free parsing step other tools can consume.

**Architecture:** A new `waybill_generator/converters/` package holds format-agnostic row parsing (`base.py`) plus one module per source format (`opsig.py`, `jbritton.py`). A new `waybill convert-industry-db` CLI command walks `industry_database/{opsig,jbritton}/`, parses each file, groups rows into per-industry records, and writes pretty-printed JSON to a sibling `json/` subfolder.

**Tech Stack:** Python 3.11+, Click (CLI), `xlrd` (legacy `.xls` reading), stdlib `csv`/`json`.

**Spec:** `docs/superpowers/specs/2026-09-13-industry-db-json-conversion-design.md`

## Global Constraints

- Pure format conversion only — no commodity/car-type normalization, no writes to `data/industry_catalog.yaml` (spec: Purpose)
- Every JSON record has all fields present regardless of source (`car_types: []` for JBritton, `source_ref: ""` for OpSIG) — no branching on `source` to know available keys (spec: JSON Record Schema)
- `.xls` files are legacy pre-2007 format — must use `xlrd`, not `openpyxl` (spec: Architecture, Dependencies)
- File encoding for all `.txt` reads is `latin-1` (spec: Background — matches source files' original encoding)
- Column layout is 0-indexed: year=0, name=1, city=2, state=3, railroad=4, direction=5, commodity=6; notes/source_ref/car_types columns vary by format (spec: Background table)

---

### Task 1: Shared row parsing and grouping (`converters/base.py`)

**Files:**
- Create: `waybill_generator/converters/__init__.py`
- Create: `waybill_generator/converters/base.py`
- Test: `tests/test_converters.py`

**Interfaces:**
- Produces: `RawRow` dataclass (`year, name, city, state, railroad, direction, commodity, notes, car_types: list[str], source_ref: str`); `parse_tab_line(line: list[str], *, notes_col: int, source_ref_col: int | None, car_types_col: int | None) -> RawRow | None`; `group_by_industry(rows: list[RawRow]) -> list[dict]`; `to_json_records(groups: list[dict], source: str, source_file: str) -> list[dict]`

- [ ] **Step 1: Create the package init file**

```bash
mkdir -p waybill_generator/converters
touch waybill_generator/converters/__init__.py
```

- [ ] **Step 2: Write failing tests for `parse_tab_line`**

Create `tests/test_converters.py`:

```python
from waybill_generator.converters.base import RawRow, parse_tab_line, group_by_industry, to_json_records


class TestParseTabLine:
    def test_full_opsig_style_row(self):
        line = ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S",
                "latex, plastic pellets", "butadiene prod.mfg", "VH(e)", "CH,T"]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        assert row is not None
        assert row.year == "2004"
        assert row.name == "Dow"
        assert row.city == "Allyn's Point"
        assert row.state == "CT"
        assert row.railroad == "P&W"
        assert row.direction == "S"
        assert row.commodity == "latex, plastic pellets"
        assert row.notes == "butadiene prod.mfg"
        assert row.car_types == ["CH", "T"]
        assert row.source_ref == ""

    def test_full_jbritton_style_row(self):
        line = ["1945", "Standard Novelty Works", "Duncannon", "PA", "PRR", "S", "Sleds",
                "", "Middle Division - Main Line - 208", "pennsyrr.com PRR CT1000"]
        row = parse_tab_line(line, notes_col=8, source_ref_col=9, car_types_col=None)
        assert row is not None
        assert row.notes == "Middle Division - Main Line - 208"
        assert row.source_ref == "pennsyrr.com PRR CT1000"
        assert row.car_types == []

    def test_blank_name_returns_none(self):
        line = ["2004", "", "City", "PA", "PRR", "S", "coal", "", "", ""]
        assert parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9) is None

    def test_short_line_padded_to_10(self):
        line = ["2004", "Acme", "Reading", "PA", "PRR", "S", "coal"]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        assert row is not None
        assert row.car_types == []

    def test_blank_car_types_column(self):
        line = ["2004", "Mill", "City", "PA", "PRR", "R", "coal", "", "", ""]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        assert row.car_types == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'waybill_generator.converters.base'`

- [ ] **Step 4: Implement `parse_tab_line` and `RawRow`**

Create `waybill_generator/converters/base.py`:

```python
from dataclasses import dataclass


@dataclass
class RawRow:
    year: str
    name: str
    city: str
    state: str
    railroad: str
    direction: str        # "S", "R", or ""
    commodity: str
    notes: str
    car_types: list[str]  # raw source codes; empty when the format has no car-type column
    source_ref: str


def parse_tab_line(
    line: list[str],
    *,
    notes_col: int,
    source_ref_col: int | None,
    car_types_col: int | None,
) -> RawRow | None:
    while len(line) < 10:
        line.append("")

    name = line[1].strip()
    if not name:
        return None

    car_types = []
    if car_types_col is not None:
        car_types = [c.strip() for c in line[car_types_col].split(",") if c.strip()]

    source_ref = line[source_ref_col].strip() if source_ref_col is not None else ""

    return RawRow(
        year=line[0].strip(),
        name=name,
        city=line[2].strip(),
        state=line[3].strip(),
        railroad=line[4].strip(),
        direction=line[5].strip(),
        commodity=line[6].strip(),
        notes=line[notes_col].strip(),
        car_types=car_types,
        source_ref=source_ref,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Write failing tests for `group_by_industry`**

Append to `tests/test_converters.py`:

```python
def _row(
    name="Acme Corp", city="Reading", state="PA", railroad="PRR", year="1945",
    direction="S", commodity="coal", notes="", car_types=None, source_ref="",
) -> RawRow:
    return RawRow(
        year=year, name=name, city=city, state=state, railroad=railroad,
        direction=direction, commodity=commodity, notes=notes,
        car_types=car_types or [], source_ref=source_ref,
    )


class TestGroupByIndustry:
    def test_single_row_ships(self):
        groups = group_by_industry([_row(direction="S", commodity="coal")])
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == []

    def test_single_row_receives(self):
        groups = group_by_industry([_row(direction="R", commodity="lumber")])
        assert groups[0]["receives"] == ["lumber"]
        assert groups[0]["ships"] == []

    def test_blank_direction_non_empty_commodity_goes_to_both(self):
        groups = group_by_industry([_row(direction="", commodity="freight")])
        assert "freight" in groups[0]["ships"]
        assert "freight" in groups[0]["receives"]

    def test_blank_direction_blank_commodity_ignored(self):
        groups = group_by_industry([_row(direction="", commodity="")])
        assert groups[0]["ships"] == []
        assert groups[0]["receives"] == []

    def test_multiple_rows_same_industry_grouped(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="R", commodity="lumber")]
        groups = group_by_industry(rows)
        assert len(groups) == 1
        assert groups[0]["ships"] == ["coal"]
        assert groups[0]["receives"] == ["lumber"]

    def test_duplicate_commodity_deduplicated(self):
        rows = [_row(direction="S", commodity="coal"), _row(direction="S", commodity="coal")]
        groups = group_by_industry(rows)
        assert groups[0]["ships"].count("coal") == 1

    def test_different_industries_produce_separate_groups(self):
        rows = [_row(name="A Corp"), _row(name="B Corp")]
        groups = group_by_industry(rows)
        assert len(groups) == 2

    def test_notes_taken_from_first_non_empty(self):
        rows = [_row(notes=""), _row(notes="Main Line - 220"), _row(notes="Different note")]
        groups = group_by_industry(rows)
        assert groups[0]["notes"] == "Main Line - 220"

    def test_source_ref_taken_from_first_non_empty(self):
        rows = [_row(source_ref=""), _row(source_ref="pennsyrr.com")]
        groups = group_by_industry(rows)
        assert groups[0]["source_ref"] == "pennsyrr.com"

    def test_year_taken_from_first_row(self):
        rows = [_row(year="1945"), _row(year="1946")]
        groups = group_by_industry(rows)
        assert groups[0]["year"] == "1945"

    def test_car_types_merged_and_deduplicated(self):
        rows = [
            _row(car_types=["HM", "GB"]),
            _row(direction="R", commodity="ore", car_types=["GB", "XM"]),
        ]
        groups = group_by_industry(rows)
        assert set(groups[0]["car_types"]) == {"HM", "GB", "XM"}
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py -v`
Expected: FAIL with `ImportError: cannot import name 'group_by_industry'`

- [ ] **Step 8: Implement `group_by_industry`**

Append to `waybill_generator/converters/base.py`:

```python
def group_by_industry(rows: list[RawRow]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for row in rows:
        key = (row.name.strip(), row.city.strip(), row.state.strip(), row.railroad.strip())
        if key not in groups:
            groups[key] = {
                "name": row.name.strip(),
                "city": row.city.strip(),
                "state": row.state.strip(),
                "railroad": row.railroad.strip(),
                "year": row.year.strip(),
                "ships": [],
                "receives": [],
                "notes": "",
                "car_types": [],
                "source_ref": "",
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
        if not g["source_ref"] and row.source_ref.strip():
            g["source_ref"] = row.source_ref.strip()

        for ct in row.car_types:
            ct = ct.strip()
            if ct and ct not in g["car_types"]:
                g["car_types"].append(ct)

    return list(groups.values())
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py -v`
Expected: PASS (all `TestGroupByIndustry` tests)

- [ ] **Step 10: Write failing test for `to_json_records`**

Append to `tests/test_converters.py`:

```python
class TestToJsonRecords:
    def test_stamps_source_and_source_file(self):
        groups = group_by_industry([_row(direction="S", commodity="coal")])
        records = to_json_records(groups, source="opsig", source_file="coal-mines-pa.csv")
        assert len(records) == 1
        r = records[0]
        assert r["source"] == "opsig"
        assert r["source_file"] == "coal-mines-pa.csv"
        assert r["name"] == "Acme Corp"
        assert r["ships"] == ["coal"]
        assert r["receives"] == []
        assert r["car_types"] == []
        assert r["source_ref"] == ""
        assert r["notes"] == ""
        assert r["year"] == "1945"
```

- [ ] **Step 11: Run test to verify it fails**

Run: `uv run pytest tests/test_converters.py -v`
Expected: FAIL with `ImportError: cannot import name 'to_json_records'`

- [ ] **Step 12: Implement `to_json_records`**

Append to `waybill_generator/converters/base.py`:

```python
def to_json_records(groups: list[dict], source: str, source_file: str) -> list[dict]:
    records = []
    for g in groups:
        records.append({
            "name": g["name"],
            "city": g["city"],
            "state": g["state"],
            "railroad": g["railroad"],
            "year": g["year"],
            "ships": g["ships"],
            "receives": g["receives"],
            "car_types": g["car_types"],
            "source_ref": g["source_ref"],
            "notes": g["notes"],
            "source": source,
            "source_file": source_file,
        })
    return records
```

- [ ] **Step 13: Run full test file to verify everything passes**

Run: `uv run pytest tests/test_converters.py -v`
Expected: PASS (all tests)

- [ ] **Step 14: Commit**

```bash
git add waybill_generator/converters/__init__.py waybill_generator/converters/base.py tests/test_converters.py
git commit -m "feat: add shared row parsing and grouping for industry_database converters"
```

---

### Task 2: OpSIG parser (`converters/opsig.py`)

**Files:**
- Create: `waybill_generator/converters/opsig.py`
- Modify: `pyproject.toml` (reintroduce `xlrd` dependency)
- Test: `tests/test_converters.py`

**Interfaces:**
- Consumes: `RawRow`, `parse_tab_line` from `waybill_generator.converters.base` (Task 1)
- Produces: `parse_opsig(filepath: Path) -> tuple[list[RawRow], int]` — returns `(rows, skipped_count)`

- [ ] **Step 1: Reintroduce the `xlrd` dependency**

Edit `pyproject.toml`, in the `dependencies` list (currently ending `"openpyxl>=3",`), add `xlrd` back:

```toml
dependencies = [
    "click>=8",
    "pydantic>=2",
    "reportlab>=4",
    "pyyaml>=6",
    "openpyxl>=3",
    "xlrd>=2",
]
```

Then run:

```bash
uv sync --extra dev
```

- [ ] **Step 2: Write failing tests for `.txt` and `.xls` parsing**

Append to `tests/test_converters.py`:

```python
from waybill_generator.converters.opsig import parse_opsig


class TestParseOpSIGFile:
    def test_parses_txt_rows(self, tmp_path):
        content = (
            "2004\tDow\tAllyn's Point\tCT\tP&W\tS\tlatex\tbutadiene\tVH\tCH,T\r\n"
            "2004\tPeter Paul\tBeacon Falls\tCT\tGRS\tR\tcorn syrup\tcandy mfg\tH\tT\r\n"
        )
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, skipped = parse_opsig(p)
        assert len(rows) == 2
        assert rows[0].name == "Dow"
        assert rows[1].name == "Peter Paul"
        assert skipped == 0

    def test_skips_blank_name_rows_and_counts_them(self, tmp_path):
        content = "\t\t\t\t\t\t\t\t\t\r\n2004\tAcme\tCity\tPA\tPRR\tS\tcoal\t\t\tH\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Acme"
        assert skipped == 1


class _FakeSheet:
    def __init__(self, rows: list[list[str]]):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = 10

    def cell_value(self, row, col):
        return self._rows[row][col]


class _FakeWorkbook:
    def __init__(self, rows: list[list[str]]):
        self._sheet = _FakeSheet(rows)

    def sheet_by_index(self, index):
        return self._sheet


class TestParseOpSIGXls:
    def test_parses_xls_via_xlrd(self, monkeypatch, tmp_path):
        rows_data = [
            ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S", "latex", "butadiene", "", "CH,T"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Dow"
        assert rows[0].car_types == ["CH", "T"]
        assert skipped == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py -v -k "OpSIG or Xls"`
Expected: FAIL with `ModuleNotFoundError: No module named 'waybill_generator.converters.opsig'`

- [ ] **Step 4: Implement `parse_opsig`**

Create `waybill_generator/converters/opsig.py`:

```python
import csv
from pathlib import Path
from waybill_generator.converters.base import RawRow, parse_tab_line


def parse_opsig(filepath: Path) -> tuple[list[RawRow], int]:
    if filepath.suffix.lower() == ".xls":
        return _parse_xls(filepath)
    return _parse_txt(filepath)


def _parse_txt(filepath: Path) -> tuple[list[RawRow], int]:
    rows = []
    skipped = 0
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
            if row:
                rows.append(row)
            else:
                skipped += 1
    return rows, skipped


def _parse_xls(filepath: Path) -> tuple[list[RawRow], int]:
    import xlrd
    wb = xlrd.open_workbook(str(filepath))
    ws = wb.sheet_by_index(0)
    rows = []
    skipped = 0
    for i in range(ws.nrows):
        line = [str(ws.cell_value(i, j)).strip() if j < ws.ncols else "" for j in range(10)]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        if row:
            rows.append(row)
        else:
            skipped += 1
    return rows, skipped
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py -v -k "OpSIG or Xls"`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock waybill_generator/converters/opsig.py tests/test_converters.py
git commit -m "feat: add OpSIG source file parser"
```

---

### Task 3: JBritton parser (`converters/jbritton.py`)

**Files:**
- Create: `waybill_generator/converters/jbritton.py`
- Test: `tests/test_converters.py`

**Interfaces:**
- Consumes: `RawRow`, `parse_tab_line` from `waybill_generator.converters.base` (Task 1)
- Produces: `parse_jbritton(filepath: Path) -> tuple[list[RawRow], int]`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_converters.py`:

```python
from waybill_generator.converters.jbritton import parse_jbritton


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
        rows, skipped = parse_jbritton(p)
        assert len(rows) == 3
        assert rows[0].direction == "S"
        assert rows[1].direction == "R"
        assert rows[2].direction == ""
        assert skipped == 0

    def test_no_car_types(self, tmp_path):
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tsource{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, _ = parse_jbritton(p)
        assert rows[0].car_types == []

    def test_source_ref_captured(self, tmp_path):
        tabs = "\t" * 246
        content = f"1945\tAcme\tCity\tPA\tPRR\tS\tCoal\t\tMain Line\tpennsyrr.com CT1000{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, _ = parse_jbritton(p)
        assert rows[0].source_ref == "pennsyrr.com CT1000"

    def test_blank_name_row_skipped_and_counted(self, tmp_path):
        tabs = "\t" * 247
        content = f"1945\t\tCity\tPA\tPRR{tabs}\r\n"
        p = tmp_path / "test.txt"
        p.write_bytes(content.encode("latin-1"))
        rows, skipped = parse_jbritton(p)
        assert len(rows) == 0
        assert skipped == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py -v -k JBritton`
Expected: FAIL with `ModuleNotFoundError: No module named 'waybill_generator.converters.jbritton'`

- [ ] **Step 3: Implement `parse_jbritton`**

Create `waybill_generator/converters/jbritton.py`:

```python
import csv
from pathlib import Path
from waybill_generator.converters.base import RawRow, parse_tab_line


def parse_jbritton(filepath: Path) -> tuple[list[RawRow], int]:
    rows = []
    skipped = 0
    with open(filepath, encoding="latin-1", newline="") as f:
        for line in csv.reader(f, delimiter="\t"):
            row = parse_tab_line(line, notes_col=8, source_ref_col=9, car_types_col=None)
            if row:
                rows.append(row)
            else:
                skipped += 1
    return rows, skipped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py -v -k JBritton`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full converters test file**

Run: `uv run pytest tests/test_converters.py -v`
Expected: PASS (all tests from Tasks 1-3)

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/converters/jbritton.py tests/test_converters.py
git commit -m "feat: add JBritton source file parser"
```

---

### Task 4: `convert-industry-db` CLI command

**Files:**
- Modify: `waybill_generator/cli.py`
- Test: `tests/test_converters.py`

**Interfaces:**
- Consumes: `parse_opsig` (Task 2), `parse_jbritton` (Task 3), `group_by_industry`, `to_json_records` (Task 1)
- Produces: `convert-industry-db` Click command registered on `main`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_converters.py`:

```python
import json
from click.testing import CliRunner
from waybill_generator.cli import main


class TestConvertIndustryDbCommand:
    def _make_opsig_txt(self, industry_db: Path) -> Path:
        opsig_dir = industry_db / "opsig"
        opsig_dir.mkdir(parents=True)
        p = opsig_dir / "sample.txt"
        p.write_bytes(
            "2004\tDow\tAllyn's Point\tCT\tP&W\tS\tlatex\tbutadiene\tVH\tCH,T\r\n".encode("latin-1")
        )
        return opsig_dir

    def _make_jbritton_txt(self, industry_db: Path) -> Path:
        jbritton_dir = industry_db / "jbritton"
        jbritton_dir.mkdir(parents=True)
        tabs = "\t" * 246
        p = jbritton_dir / "sample.txt"
        p.write_bytes(
            f"1945\tStandard Novelty Works\tDuncannon\tPA\tPRR\tS\tSleds\t\tMain Line\tpennsyrr.com{tabs}\r\n".encode("latin-1")
        )
        return jbritton_dir

    def test_writes_json_for_opsig_and_jbritton(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        self._make_opsig_txt(industry_db)
        self._make_jbritton_txt(industry_db)

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output

        opsig_json = json.loads((industry_db / "opsig" / "json" / "sample.json").read_text())
        assert len(opsig_json) == 1
        assert opsig_json[0]["name"] == "Dow"
        assert opsig_json[0]["source"] == "opsig"
        assert opsig_json[0]["source_file"] == "sample.txt"

        jbritton_json = json.loads((industry_db / "jbritton" / "json" / "sample.json").read_text())
        assert len(jbritton_json) == 1
        assert jbritton_json[0]["name"] == "Standard Novelty Works"
        assert jbritton_json[0]["source"] == "jbritton"

    def test_prints_summary_with_skipped_count(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        opsig_dir = self._make_opsig_txt(industry_db)
        blank_line = "\t" * 9 + "\r\n"
        with open(opsig_dir / "sample.txt", "ab") as f:
            f.write(blank_line.encode("latin-1"))

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output
        assert "sample.txt" in result.output
        assert "1 rows skipped" in result.output

    def test_unrecognized_extension_warned_not_errored(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        opsig_dir = self._make_opsig_txt(industry_db)
        (opsig_dir / "notes.pdf").write_bytes(b"not a real pdf")

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output
        assert "notes.pdf" in result.output

    def test_missing_source_subfolder_skipped_silently(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        self._make_opsig_txt(industry_db)  # no jbritton/ folder created

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output

    def test_unparseable_file_reported_but_run_continues(self, tmp_path):
        industry_db = tmp_path / "industry_database"
        opsig_dir = self._make_opsig_txt(industry_db)
        (opsig_dir / "corrupt.xls").write_bytes(b"not a real xls file")

        runner = CliRunner()
        result = runner.invoke(main, ["convert-industry-db", "--industry-db", str(industry_db)])

        assert result.exit_code == 0, result.output
        assert "ERROR" in result.output
        assert "corrupt.xls" in result.output
        # the good file in the same folder is still converted
        assert (opsig_dir / "json" / "sample.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py -v -k ConvertIndustryDb`
Expected: FAIL — `Error: No such command 'convert-industry-db'`

- [ ] **Step 3: Implement the CLI command**

In `waybill_generator/cli.py`, add near the end of the file (after the `import_roster` command):

```python
@main.command("convert-industry-db")
@click.option("--industry-db", default="./industry_database", show_default=True,
              type=click.Path(exists=True, file_okay=False),
              help="Path to industry_database directory")
def convert_industry_db(industry_db):
    """Convert raw OpSIG/JBritton source files into structured JSON."""
    import json
    from waybill_generator.converters.base import group_by_industry, to_json_records
    from waybill_generator.converters.opsig import parse_opsig
    from waybill_generator.converters.jbritton import parse_jbritton

    db_path = Path(industry_db)
    sources = [
        ("opsig", db_path / "opsig", (".xls", ".txt"), parse_opsig),
        ("jbritton", db_path / "jbritton", (".txt",), parse_jbritton),
    ]

    for source, source_dir, extensions, parse_fn in sources:
        if not source_dir.is_dir():
            continue
        json_dir = source_dir / "json"
        json_dir.mkdir(exist_ok=True)

        for filepath in sorted(source_dir.iterdir()):
            if not filepath.is_file():
                continue
            if filepath.suffix.lower() not in extensions:
                click.echo(f"Skipping unrecognized file: {filepath}")
                continue

            try:
                rows, skipped = parse_fn(filepath)
            except Exception as exc:
                click.echo(f"ERROR parsing {filepath}: {exc}")
                continue

            groups = group_by_industry(rows)
            records = to_json_records(groups, source, filepath.name)
            out_path = json_dir / f"{filepath.stem}.json"
            out_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")

            click.echo(
                f"{filepath.name}: {len(rows)} rows parsed, {len(groups)} industries grouped, "
                f"{skipped} rows skipped -> {out_path}"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py -v -k ConvertIndustryDb`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full converters test file**

Run: `uv run pytest tests/test_converters.py -v`
Expected: PASS (all tests from Tasks 1-4)

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/cli.py tests/test_converters.py
git commit -m "feat: add convert-industry-db CLI command"
```

---

### Task 5: Convert the real source files and verify end-to-end

**Files:**
- No new files — this task runs the command against the real `industry_database/` data checked out in the working tree and reviews the output.

**Interfaces:**
- Consumes: `convert-industry-db` command (Task 4)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS for all `test_converters.py` tests. (The 5 pre-existing failures in `tests/test_layouts.py`, unrelated to this feature, are expected to remain — do not attempt to fix them here.)

- [ ] **Step 2: Run ruff**

Run: `uv run ruff check waybill_generator/converters/ waybill_generator/cli.py tests/test_converters.py`
Expected: No errors. Fix any lint issues found before proceeding.

- [ ] **Step 3: Run the command against the real data**

Run: `uv run waybill convert-industry-db`
Expected: Output lines for every file in `industry_database/opsig/` and `industry_database/jbritton/`, each showing rows parsed / industries grouped / rows skipped, with no unhandled exceptions. The `.DS_Store` inside `industry_database/` itself is outside both source folders and won't be touched; if any stray non-source file exists inside `opsig/` or `jbritton/`, confirm it's reported as "Skipping unrecognized file" rather than erroring.

- [ ] **Step 4: Spot-check the generated JSON**

Run: `cat industry_database/opsig/json/OpSigCANADA.json | head -30` (or any generated file) and confirm the records look like the schema in the spec: `name`, `city`, `state`, `railroad`, `year`, `ships`, `receives`, `car_types`, `source_ref`, `notes`, `source`, `source_file` all present.

- [ ] **Step 5: Decide on ignoring or committing the generated JSON**

The generated `industry_database/*/json/` folders are derived output, regenerable at any time by re-running the command. Ask the user whether to gitignore them or commit them before finishing this task — do not decide unilaterally.

- [ ] **Step 6: Commit** (only the outcome of Step 5's decision; no code changes)

If gitignoring:
```bash
echo "industry_database/*/json/" >> .gitignore
git add .gitignore
git commit -m "chore: ignore generated industry_database JSON output"
```

If committing the generated JSON:
```bash
git add industry_database/opsig/json/ industry_database/jbritton/json/
git commit -m "data: generate JSON conversion of industry_database source files"
```

---

### Task 6: Fix real `.xls` header rows and DH-file column layout

**Added after Task 5's real-data verification surfaced this — not in the original spec, ruled on directly with the user (see ledger).**

Running `convert-industry-db` against the real files in `industry_database/opsig/` revealed two problems `_parse_xls` (Task 2) didn't anticipate, because the spec's column table was inherited from the original (reverted) importer without validating it against these actual files:

1. **All 4 real `.xls` files have a header row at index 0** (e.g. `OpSigCANADA.xls` row 0 is literally `["ERA", "INDUSTRY/COMPANY NAME", "CITY", ...]`), which `_parse_xls` currently parses as a bogus data record.
2. **`DHCanada.xls` and `DHWest.xls` have 11 columns, not 10** — confirmed via direct `xlrd` inspection: header is `["List", "Era", "Ind", "City", "St", "RR", "SR", "Comm", "STCC", "Recip", "Contrib"]`. The extra leading `List` column (values are only ever `"C"` or `"W"` — a region/list tag) shifts every other field right by one relative to the 10-column layout `OpSigCANADA.xls`/`OpSigWEST.xls` use, so parsing them with the fixed 10-column offset puts real year values in the `name` field, real names in `city`, etc.

**Ruling (made with the user, not unilaterally):** fix both problems now, minimally. Skip the header row unconditionally in `.xls` files. Auto-detect the 11-vs-10 column layout via `ws.ncols`, and for 11-column files shift the standard field extraction right by one column, folding the extra `List` value into the `notes` field as a `[list: C]`/`[list: W]` prefix so it's preserved rather than silently dropped — without expanding the JSON schema. Leave the separate, lower-severity finding that OpSIG's own columns 7/9 are actually `STTC`/`CONTRIBUTOR` rather than true `notes`/`car_types` as a **documented known caveat**, not fixed in this task — the user asked to assume the best interpretation for now and revisit later.

**Files:**
- Modify: `waybill_generator/converters/opsig.py`
- Modify: `tests/test_converters.py` (update `_FakeSheet.ncols` to reflect actual row width instead of a hardcoded `10`, update the two existing `TestParseOpSIGXls` tests to include a header row since row 0 is now always skipped, add two new tests)

**Interfaces:**
- Consumes: `parse_tab_line`, `RawRow` from `waybill_generator.converters.base` (unchanged)
- Produces: `parse_opsig(filepath) -> tuple[list[RawRow], int]` — same signature, corrected `.xls` behavior. No change to `parse_opsig`'s public contract; Task 4's CLI command needs no changes.

- [ ] **Step 1: Update `_FakeSheet` to compute `ncols` from the row data instead of hardcoding it**

In `tests/test_converters.py`, change:

```python
class _FakeSheet:
    def __init__(self, rows: list[list[str]]):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = 10

    def cell_value(self, row, col):
        return self._rows[row][col]
```

to:

```python
class _FakeSheet:
    def __init__(self, rows: list[list[str]]):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = len(rows[0]) if rows else 10

    def cell_value(self, row, col):
        return self._rows[row][col]
```

- [ ] **Step 2: Update the existing `TestParseOpSIGXls` tests to include a header row, and write two new failing tests**

Replace the `TestParseOpSIGXls` class in `tests/test_converters.py` (it currently has `test_parses_xls_via_xlrd` and `test_xls_integer_float_year_stringified_without_decimal`) with:

```python
class TestParseOpSIGXls:
    def test_parses_xls_via_xlrd(self, monkeypatch, tmp_path):
        rows_data = [
            ["ERA", "NAME", "CITY", "ST", "RR", "S/R", "COMMODITY", "STTC", "RECIP", "CONTRIB"],
            ["2004", "Dow", "Allyn's Point", "CT", "P&W", "S", "latex", "butadiene", "", "CH,T"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Dow"
        assert rows[0].car_types == ["CH", "T"]
        assert skipped == 0

    def test_xls_integer_float_year_stringified_without_decimal(self, monkeypatch, tmp_path):
        rows_data = [
            ["ERA", "NAME", "CITY", "ST", "RR", "S/R", "COMMODITY", "STTC", "RECIP", "CONTRIB"],
            [2004.0, "Dow", "Allyn's Point", "CT", "P&W", "S", "latex", "butadiene", "", "CH,T"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert rows[0].year == "2004"

    def test_header_row_not_parsed_as_data(self, monkeypatch, tmp_path):
        rows_data = [
            ["ERA", "INDUSTRY/COMPANY NAME", "CITY", "ST", "SERVING RAILROADS", "S/R",
             "COMMODITY", "STTC", "RECIP. SWITCH.", "CONTRIBUTOR"],
            ["90", "Conagra Fertilizer", "Beamer", "AB", "CN", "S", "Ammonium nitrate", "", "", "butts"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        assert rows[0].name == "Conagra Fertilizer"
        assert all(r.name != "INDUSTRY/COMPANY NAME" for r in rows)

    def test_11_column_dh_layout_shifts_and_tags_notes(self, monkeypatch, tmp_path):
        rows_data = [
            ["List", "Era", "Ind", "City", "St", "RR", "SR", "Comm", "STCC", "Recip", "Contrib"],
            ["C", "1996", "Sherridan Fertilizer", "Beamer", "AB", "CN", "", "Ammonium nitrate",
             "4918311", "", "spwayb"],
        ]
        monkeypatch.setattr("xlrd.open_workbook", lambda path: _FakeWorkbook(rows_data))
        p = tmp_path / "test.xls"
        p.write_bytes(b"")
        rows, skipped = parse_opsig(p)
        assert len(rows) == 1
        row = rows[0]
        assert row.year == "1996"
        assert row.name == "Sherridan Fertilizer"
        assert row.city == "Beamer"
        assert row.state == "AB"
        assert row.railroad == "CN"
        assert row.notes == "[list: C] 4918311"
        assert row.car_types == ["spwayb"]
        assert skipped == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py -v -k Xls`
Expected: FAIL — the two updated tests now fail because the header row is being parsed as data (wrong `rows[0]`), and the two new tests fail because `_parse_xls` doesn't yet skip headers or handle 11-column files.

- [ ] **Step 4: Implement the fix in `_parse_xls`**

In `waybill_generator/converters/opsig.py`, replace:

```python
def _parse_xls(filepath: Path) -> tuple[list[RawRow], int]:
    import xlrd
    wb = xlrd.open_workbook(str(filepath))
    ws = wb.sheet_by_index(0)
    rows = []
    skipped = 0
    for i in range(ws.nrows):
        line = [_cell_to_str(ws.cell_value(i, j)) if j < ws.ncols else "" for j in range(10)]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        if row:
            rows.append(row)
        else:
            skipped += 1
    return rows, skipped
```

with:

```python
def _parse_xls(filepath: Path) -> tuple[list[RawRow], int]:
    import xlrd
    wb = xlrd.open_workbook(str(filepath))
    ws = wb.sheet_by_index(0)
    rows = []
    skipped = 0
    has_list_column = ws.ncols >= 11
    col_offset = 1 if has_list_column else 0
    for i in range(1, ws.nrows):  # row 0 is a header in every real .xls source file
        list_tag = _cell_to_str(ws.cell_value(i, 0)) if has_list_column else ""
        line = [
            _cell_to_str(ws.cell_value(i, col_offset + j)) if (col_offset + j) < ws.ncols else ""
            for j in range(10)
        ]
        row = parse_tab_line(line, notes_col=7, source_ref_col=None, car_types_col=9)
        if row is None:
            skipped += 1
            continue
        if list_tag:
            row.notes = f"[list: {list_tag}] {row.notes}".strip()
        rows.append(row)
    return rows, skipped
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py -v -k Xls`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the full converters test file**

Run: `uv run pytest tests/test_converters.py -v`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/converters/opsig.py tests/test_converters.py
git commit -m "fix: skip xls header rows and handle DH files' 11-column layout"
```

- [ ] **Step 8: Regenerate the real JSON output and spot-check**

Run: `uv run waybill convert-industry-db`

Then check `industry_database/opsig/json/OpSigCANADA.json` — record 0 should now be a real industry (not a header row). Check `industry_database/opsig/json/DHCanada.json` — spot-check a few records' `year`/`name`/`city` fields against the raw file to confirm they're no longer shifted, and confirm some records show a `[list: C]` or `[list: W]` prefix in `notes`.
