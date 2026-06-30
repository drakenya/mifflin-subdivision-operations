# Industry Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the Location model and add a searchable industry reference catalog with `waybill search` and `waybill add-industry` CLI commands.

**Architecture:** The catalog lives in `data/industry_catalog.yaml` and is served by a new `CatalogRepository` that is entirely separate from `BaseRepository` — it never participates in waybill generation. Two new top-level CLI commands (`search`, `add-industry`) read from the catalog; `add-industry` writes back to `locations.yaml` after a preview + confirm flow.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, Click — all already in use.

## Global Constraints

- Python 3.11+ only — use `str | None` union syntax, not `Optional[str]`
- Pydantic v2 — use `model_copy(update=...)`, not `.copy()`
- PyYAML already installed — no new dependencies required
- All tests run with `pytest tests/ -v` from the repo root with the venv active
- Test fixtures live in `tests/fixtures/`
- TDD: write failing test → confirm failure → implement → confirm pass → commit

---

### Task 1: Location Model Cleanup

Remove `subdivision` from the `Location` model; add `railroad_id` and `on_layout`. Update all data files and tests to match.

**Files:**
- Modify: `waybill_generator/models/location.py`
- Modify: `data/locations.yaml`
- Modify: `tests/fixtures/locations.yaml`
- Modify: `tests/test_models.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces: `Location(id, name, state, railroad_id, on_layout, industries)` — consumed by Tasks 3, 4, 5 indirectly via `YamlRepository`

- [ ] **Step 1: Write failing tests for updated Location model**

In `tests/test_models.py`, replace the entire `TestLocation` class:

```python
class TestLocation:
    def test_location_with_industries(self):
        loc = Location(
            id="LEW", name="Lewistown", on_layout=True,
            industries=[
                Industry(id="LEW-GRAIN", name="Grain Elevator", location_id="LEW", ships=["grain"])
            ],
        )
        assert len(loc.industries) == 1
        assert loc.industries[0].ships == ["grain"]
        assert loc.on_layout is True

    def test_location_defaults(self):
        loc = Location(id="ALT", name="Altoona")
        assert loc.industries == []
        assert loc.railroad_id is None
        assert loc.on_layout is False

    def test_foreign_railroad(self):
        loc = Location(id="NYC-TERM", name="New York Terminal", railroad_id="NYC")
        assert loc.railroad_id == "NYC"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py::TestLocation -v
```

Expected: FAIL — `Location` still has `subdivision`, not `on_layout` or `railroad_id`.

- [ ] **Step 3: Update the Location model**

Replace `waybill_generator/models/location.py` entirely:

```python
from pydantic import BaseModel


class Industry(BaseModel):
    id: str
    name: str
    location_id: str
    track: str | None = None
    car_capacity: int | None = None
    ships: list[str] = []
    receives: list[str] = []


class Location(BaseModel):
    id: str
    name: str
    state: str = "PA"
    railroad_id: str | None = None
    on_layout: bool = False
    industries: list[Industry] = []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py::TestLocation -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Update `tests/fixtures/locations.yaml`**

Replace the file entirely:

```yaml
- id: LEW
  name: Lewistown
  on_layout: true
  industries:
    - id: LEW-GRAIN
      name: Lewistown Grain Elevator
      location_id: LEW
      track: "1"
      car_capacity: 3
      ships:
        - grain
      receives: []

- id: ALT
  name: Altoona
  industries:
    - id: ALT-SHOP
      name: Altoona Shops
      location_id: ALT
      track: shop
      car_capacity: 10
      ships: []
      receives: []
```

- [ ] **Step 6: Run the full test suite to verify no regressions**

```bash
pytest tests/ -v
```

Expected: All tests pass. Fix any failures caused by the fixture change before proceeding.

- [ ] **Step 7: Update `data/locations.yaml`**

For each of the 9 locations, remove the `subdivision:` line. Then add `on_layout: true` to the 6 Mifflin Subdivision locations (BRN, MCV, MIF, MFT, LEW, LJ). The 3 off-layout locations (ALT, HBG, PGH) get no `on_layout` field (defaults to false).

Example of what BRN should look like after the change:

```yaml
- id: BRN
  name: Burnham
  on_layout: true
  industries:
    - id: BRN-SSW
      ...
```

Example of what ALT should look like after the change:

```yaml
- id: ALT
  name: Altoona
  industries:
    - id: ALT-SHOP
      ...
```

- [ ] **Step 8: Verify the data file loads cleanly**

```bash
waybill --data-path data validate
```

Expected: `Locations: 9 loaded` (or whatever count is in the file) with no errors.

- [ ] **Step 9: Commit**

```bash
git add waybill_generator/models/location.py data/locations.yaml tests/fixtures/locations.yaml tests/test_models.py
git commit -m "refactor: remove subdivision from Location, add railroad_id + on_layout"
```

---

### Task 2: CatalogIndustry Model and Fixture Data

Create the `CatalogIndustry` Pydantic model, a starter `data/industry_catalog.yaml`, a test fixture with 3 entries, and model-level tests.

**Files:**
- Create: `waybill_generator/models/catalog.py`
- Create: `data/industry_catalog.yaml`
- Create: `tests/fixtures/industry_catalog.yaml`
- Create: `tests/test_catalog.py`

**Interfaces:**
- Produces: `CatalogIndustry(id, name, city, state, railroad_id, source, source_file, source_ref, ships, receives, car_types, notes)` — consumed by Task 3

- [ ] **Step 1: Write failing model tests**

Create `tests/test_catalog.py`:

```python
import pytest
from pydantic import ValidationError
from waybill_generator.models.catalog import CatalogIndustry


class TestCatalogIndustry:
    def test_basic_construction(self):
        entry = CatalogIndustry(
            id="cat-001",
            name="Clearfield Coal & Coke Co.",
            city="Clearfield",
            source="opsig",
            source_file="coal-mines-pa.csv",
            source_ref="OPSIG-4872",
            ships=["coal"],
            car_types=["HM", "HT"],
        )
        assert entry.state == "PA"
        assert entry.receives == []
        assert entry.notes is None
        assert entry.railroad_id is None

    def test_all_optional_fields(self):
        entry = CatalogIndustry(
            id="cat-x", name="Test Industry", city="Testville",
            source="manual", source_file="manual",
        )
        assert entry.state == "PA"
        assert entry.railroad_id is None
        assert entry.source_ref is None
        assert entry.ships == []
        assert entry.receives == []
        assert entry.car_types == []
        assert entry.notes is None

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            # missing source and source_file
            CatalogIndustry(id="x", name="Test", city="Testville")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_catalog.py::TestCatalogIndustry -v
```

Expected: FAIL — `waybill_generator.models.catalog` does not exist.

- [ ] **Step 3: Create the CatalogIndustry model**

Create `waybill_generator/models/catalog.py`:

```python
from pydantic import BaseModel


class CatalogIndustry(BaseModel):
    id: str
    name: str
    city: str
    state: str = "PA"
    railroad_id: str | None = None
    source: str
    source_file: str
    source_ref: str | None = None
    ships: list[str] = []
    receives: list[str] = []
    car_types: list[str] = []
    notes: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_catalog.py::TestCatalogIndustry -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Create the test fixture**

Create `tests/fixtures/industry_catalog.yaml`:

```yaml
- id: cat-001
  name: Clearfield Coal & Coke Co.
  city: Clearfield
  state: PA
  railroad_id: PRR
  source: opsig
  source_file: coal-mines-pa.csv
  source_ref: "OPSIG-4872"
  ships:
    - coal
  receives: []
  car_types:
    - HM
    - HT
  notes: Bituminous coal, Clearfield County

- id: cat-002
  name: Sunbury Lumber Co.
  city: Sunbury
  state: PA
  railroad_id: PRR
  source: jbritton
  source_file: model-railroad-waybills-prr-industry-data
  ships:
    - lumber
  receives: []
  car_types:
    - FM
    - FL

- id: cat-003
  name: Baldwin Locomotive Works
  city: Eddystone
  state: PA
  railroad_id: PRR
  source: manual
  source_file: manual
  ships:
    - machinery
  receives:
    - steel
    - coal
  car_types:
    - FM
    - XM
  notes: Major locomotive builder, PRR connection
```

- [ ] **Step 6: Create a starter `data/industry_catalog.yaml`**

Create `data/industry_catalog.yaml` with the same three entries as the fixture (serves as your starting real catalog):

```yaml
- id: cat-001
  name: Clearfield Coal & Coke Co.
  city: Clearfield
  state: PA
  railroad_id: PRR
  source: opsig
  source_file: coal-mines-pa.csv
  source_ref: "OPSIG-4872"
  ships:
    - coal
  receives: []
  car_types:
    - HM
    - HT
  notes: Bituminous coal, Clearfield County

- id: cat-002
  name: Sunbury Lumber Co.
  city: Sunbury
  state: PA
  railroad_id: PRR
  source: jbritton
  source_file: model-railroad-waybills-prr-industry-data
  ships:
    - lumber
  receives: []
  car_types:
    - FM
    - FL

- id: cat-003
  name: Baldwin Locomotive Works
  city: Eddystone
  state: PA
  railroad_id: PRR
  source: manual
  source_file: manual
  ships:
    - machinery
  receives:
    - steel
    - coal
  car_types:
    - FM
    - XM
  notes: Major locomotive builder, PRR connection
```

- [ ] **Step 7: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add waybill_generator/models/catalog.py data/industry_catalog.yaml tests/fixtures/industry_catalog.yaml tests/test_catalog.py
git commit -m "feat: add CatalogIndustry model and starter industry catalog"
```

---

### Task 3: CatalogRepository

Implement `CatalogRepository` with `get()` and `search()` (keyword, commodity, car_type, railroad, ships/receives direction, source, limit).

**Files:**
- Create: `waybill_generator/repository/catalog_repo.py`
- Modify: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `CatalogIndustry` from `waybill_generator.models.catalog`
- Consumes: `tests/fixtures/industry_catalog.yaml` (3 entries: cat-001 ships coal, cat-002 ships lumber, cat-003 ships machinery + receives steel+coal)
- Produces:
  - `CatalogRepository(catalog_path: str | Path)`
  - `CatalogRepository.get(id: str) -> CatalogIndustry` — raises `KeyError` if not found
  - `CatalogRepository.search(keyword, commodity, car_type, railroad, ships, receives, source, limit) -> list[CatalogIndustry]`

- [ ] **Step 1: Write failing repository tests**

Append to `tests/test_catalog.py`:

```python
from pathlib import Path
from waybill_generator.repository.catalog_repo import CatalogRepository

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def catalog_repo():
    return CatalogRepository(FIXTURES / "industry_catalog.yaml")


class TestCatalogRepository:
    def test_get_by_id(self, catalog_repo):
        entry = catalog_repo.get("cat-001")
        assert entry.name == "Clearfield Coal & Coke Co."

    def test_get_missing_raises(self, catalog_repo):
        with pytest.raises(KeyError):
            catalog_repo.get("MISSING")

    def test_search_no_filters_returns_all(self, catalog_repo):
        results = catalog_repo.search()
        assert len(results) == 3

    def test_search_keyword_name(self, catalog_repo):
        results = catalog_repo.search(keyword="clearfield")
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_keyword_city(self, catalog_repo):
        results = catalog_repo.search(keyword="sunbury")
        assert len(results) == 1
        assert results[0].id == "cat-002"

    def test_search_keyword_notes(self, catalog_repo):
        results = catalog_repo.search(keyword="locomotive")
        assert len(results) == 1
        assert results[0].id == "cat-003"

    def test_search_commodity_ships(self, catalog_repo):
        results = catalog_repo.search(commodity="coal", ships=True)
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_commodity_receives(self, catalog_repo):
        results = catalog_repo.search(commodity="coal", receives=True)
        assert len(results) == 1
        assert results[0].id == "cat-003"

    def test_search_commodity_both_directions(self, catalog_repo):
        results = catalog_repo.search(commodity="coal")
        ids = {e.id for e in results}
        assert "cat-001" in ids
        assert "cat-003" in ids

    def test_search_car_type(self, catalog_repo):
        results = catalog_repo.search(car_type="HM")
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_car_type_case_insensitive(self, catalog_repo):
        results = catalog_repo.search(car_type="hm")
        assert len(results) == 1

    def test_search_railroad(self, catalog_repo):
        results = catalog_repo.search(railroad="PRR")
        assert len(results) == 3

    def test_search_source(self, catalog_repo):
        results = catalog_repo.search(source="opsig")
        assert len(results) == 1
        assert results[0].id == "cat-001"

    def test_search_limit(self, catalog_repo):
        results = catalog_repo.search(limit=2)
        assert len(results) == 2

    def test_search_no_match_returns_empty(self, catalog_repo):
        results = catalog_repo.search(keyword="xyznotfound")
        assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_catalog.py::TestCatalogRepository -v
```

Expected: FAIL — `waybill_generator.repository.catalog_repo` does not exist.

- [ ] **Step 3: Implement CatalogRepository**

Create `waybill_generator/repository/catalog_repo.py`:

```python
from pathlib import Path
import yaml
from waybill_generator.models.catalog import CatalogIndustry


class CatalogRepository:
    def __init__(self, catalog_path: str | Path) -> None:
        self._path = Path(catalog_path)
        self._entries: dict[str, CatalogIndustry] | None = None

    def _ensure_entries(self) -> dict[str, CatalogIndustry]:
        if self._entries is None:
            raw = yaml.safe_load(self._path.read_text()) or []
            self._entries = {e.id: e for e in [CatalogIndustry(**r) for r in raw]}
        return self._entries

    def get(self, id: str) -> CatalogIndustry:
        entries = self._ensure_entries()
        if id not in entries:
            raise KeyError(f"Catalog entry not found: {id!r}")
        return entries[id]

    def search(
        self,
        keyword: str | None = None,
        commodity: str | None = None,
        car_type: str | None = None,
        railroad: str | None = None,
        ships: bool = False,
        receives: bool = False,
        source: str | None = None,
        limit: int = 20,
    ) -> list[CatalogIndustry]:
        results = list(self._ensure_entries().values())

        if keyword:
            kw = keyword.lower()
            results = [
                e for e in results
                if kw in e.name.lower()
                or kw in e.city.lower()
                or (e.notes and kw in e.notes.lower())
            ]

        if commodity:
            comm = commodity.lower()
            if ships:
                results = [e for e in results if any(comm in s.lower() for s in e.ships)]
            elif receives:
                results = [e for e in results if any(comm in r.lower() for r in e.receives)]
            else:
                results = [
                    e for e in results
                    if any(comm in s.lower() for s in e.ships)
                    or any(comm in r.lower() for r in e.receives)
                ]

        if car_type:
            ct = car_type.upper()
            results = [e for e in results if ct in [c.upper() for c in e.car_types]]

        if railroad:
            rr = railroad.upper()
            results = [e for e in results if e.railroad_id and e.railroad_id.upper() == rr]

        if source:
            results = [e for e in results if e.source.lower() == source.lower()]

        return results[:limit]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_catalog.py -v
```

Expected: All catalog tests pass (model + repository).

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/repository/catalog_repo.py tests/test_catalog.py
git commit -m "feat: add CatalogRepository with search and get"
```

---

### Task 4: `waybill search` CLI Command

Add a `search` top-level command to the CLI that queries the catalog and prints a results table.

**Files:**
- Modify: `waybill_generator/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `CatalogRepository.search(...)` from Task 3
- Consumes: `ctx.obj["data_path"]` — expects `industry_catalog.yaml` in that directory
- Produces: `waybill search [--keyword] [--commodity] [--car-type] [--railroad] [--ships] [--receives] [--source] [--limit]`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
def test_search_returns_results():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--keyword", "clearfield"])
    assert result.exit_code == 0
    assert "cat-001" in result.output


def test_search_no_results():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--keyword", "xyznotfound"])
    assert result.exit_code == 0
    assert "No results" in result.output


def test_search_missing_catalog(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(tmp_path), "search", "--keyword", "coal"])
    assert result.exit_code != 0


def test_search_by_car_type():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--car-type", "HM"])
    assert result.exit_code == 0
    assert "cat-001" in result.output


def test_search_by_source():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "search", "--source", "opsig"])
    assert result.exit_code == 0
    assert "cat-001" in result.output
    assert "cat-002" not in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli.py::test_search_returns_results tests/test_cli.py::test_search_no_results tests/test_cli.py::test_search_missing_catalog tests/test_cli.py::test_search_by_car_type tests/test_cli.py::test_search_by_source -v
```

Expected: FAIL — `search` command does not exist on `main`.

- [ ] **Step 3: Add the search command to `waybill_generator/cli.py`**

Add the following import at the top of `cli.py` (after existing imports):

```python
from waybill_generator.repository.catalog_repo import CatalogRepository
```

Then add this command after the `validate` command:

```python
@main.command("search")
@click.option("--keyword", default=None, help="Search name, city, notes")
@click.option("--commodity", default=None, help="Commodity id or keyword")
@click.option("--car-type", default=None, help="AAR code (e.g. HM, XM, GB)")
@click.option("--railroad", default=None, help="Railroad id (e.g. PRR, NYC)")
@click.option("--ships", "direction", flag_value="ships", default=None,
              help="Match only industries that ship the commodity")
@click.option("--receives", "direction", flag_value="receives", default=None,
              help="Match only industries that receive the commodity")
@click.option("--source", default=None, help="Filter by source (opsig, jbritton, manual)")
@click.option("--limit", default=20, show_default=True, help="Max results")
@click.pass_context
def search(ctx, keyword, commodity, car_type, railroad, direction, source, limit):
    """Search the industry reference catalog."""
    catalog_path = Path(ctx.obj["data_path"]) / "industry_catalog.yaml"
    if not catalog_path.exists():
        click.echo("No industry_catalog.yaml found in data path.", err=True)
        raise SystemExit(1)
    repo = CatalogRepository(catalog_path)
    results = repo.search(
        keyword=keyword,
        commodity=commodity,
        car_type=car_type,
        railroad=railroad,
        ships=(direction == "ships"),
        receives=(direction == "receives"),
        source=source,
        limit=limit,
    )
    if not results:
        click.echo("No results found.")
        return
    click.echo(f"{'ID':<12} {'Name':<36} {'City':<15} {'RR':<6} {'Ships':<18} {'Receives':<18} Source")
    click.echo("-" * 112)
    for e in results:
        ships_str = ", ".join(e.ships[:2]) + ("…" if len(e.ships) > 2 else "")
        recv_str = ", ".join(e.receives[:2]) + ("…" if len(e.receives) > 2 else "")
        rr = e.railroad_id or ""
        src = f"{e.source}/{e.source_file}"[:28]
        click.echo(
            f"{e.id:<12} {e.name[:35]:<36} {e.city[:14]:<15} {rr:<6}"
            f" {ships_str:<18} {recv_str:<18} {src}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli.py::test_search_returns_results tests/test_cli.py::test_search_no_results tests/test_cli.py::test_search_missing_catalog tests/test_cli.py::test_search_by_car_type tests/test_cli.py::test_search_by_source -v
```

Expected: PASS (5 tests).

- [ ] **Step 5: Smoke-test the command manually**

```bash
waybill --data-path data search --keyword coal
waybill --data-path data search --car-type HM
waybill --data-path data search --source opsig
```

Expected: Table output with matching entries; no traceback.

- [ ] **Step 6: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/cli.py tests/test_cli.py
git commit -m "feat: add waybill search command for industry catalog"
```

---

### Task 5: `waybill add-industry` CLI Command

Add the `add-industry` command: look up a catalog entry, match against existing locations, show a YAML preview, and write to `locations.yaml` after confirmation.

**Files:**
- Modify: `waybill_generator/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `CatalogRepository.get(id)` from Task 3
- Consumes/modifies: `data/locations.yaml` (or whatever `--data-path` points to)
- Produces: `waybill add-industry <catalog-id> [--preview]`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_cli.py`:

```python
def _make_catalog(tmp_path):
    """Write a minimal industry_catalog.yaml to tmp_path."""
    (tmp_path / "industry_catalog.yaml").write_text(
        "- id: cat-001\n"
        "  name: Clearfield Coal Co.\n"
        "  city: Clearfield\n"
        "  state: PA\n"
        "  railroad_id: PRR\n"
        "  source: opsig\n"
        "  source_file: coal.csv\n"
        "  ships: [coal]\n"
        "  receives: []\n"
        "  car_types: [HM]\n"
    )


def _make_locations(tmp_path, content="- id: LEW\n  name: Lewistown\n  industries: []\n"):
    (tmp_path / "locations.yaml").write_text(content)


def test_add_industry_preview_shows_yaml(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001", "--preview"]
    )
    assert result.exit_code == 0
    assert "Clearfield Coal Co." in result.output
    assert "Proposed YAML" in result.output
    # File must be unchanged
    assert "Clearfield" not in (tmp_path / "locations.yaml").read_text()


def test_add_industry_new_location_writes_file(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001"], input="Y\n"
    )
    assert result.exit_code == 0
    content = (tmp_path / "locations.yaml").read_text()
    assert "Clearfield" in content
    assert "Clearfield Coal Co." in content


def test_add_industry_cancel_does_not_write(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    original = (tmp_path / "locations.yaml").read_text()
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001"], input="N\n"
    )
    assert result.exit_code == 0
    assert (tmp_path / "locations.yaml").read_text() == original


def test_add_industry_missing_catalog(tmp_path):
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(tmp_path), "add-industry", "cat-001"])
    assert result.exit_code != 0


def test_add_industry_missing_catalog_id(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-NOTFOUND"], input="Y\n"
    )
    assert result.exit_code != 0


def test_add_industry_existing_location(tmp_path):
    _make_catalog(tmp_path)
    _make_locations(
        tmp_path,
        "- id: CLR\n  name: Clearfield\n  state: PA\n  railroad_id: PRR\n  industries: []\n",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(tmp_path), "add-industry", "cat-001"], input="y\nY\n"
    )
    assert result.exit_code == 0
    import yaml
    locs = yaml.safe_load((tmp_path / "locations.yaml").read_text())
    clr = next(l for l in locs if l["id"] == "CLR")
    assert any(i["name"] == "Clearfield Coal Co." for i in clr.get("industries", []))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli.py::test_add_industry_preview_shows_yaml tests/test_cli.py::test_add_industry_new_location_writes_file tests/test_cli.py::test_add_industry_cancel_does_not_write tests/test_cli.py::test_add_industry_missing_catalog tests/test_cli.py::test_add_industry_missing_catalog_id tests/test_cli.py::test_add_industry_existing_location -v
```

Expected: FAIL — `add-industry` command does not exist.

- [ ] **Step 3: Add helper functions and the `add-industry` command to `waybill_generator/cli.py`**

Add these three helpers before the `search` command (after `_get_repo`):

```python
def _generate_location_id(city: str, existing_ids: set[str]) -> str:
    base = city[:3].upper().replace(" ", "")
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _generate_industry_id(loc_id: str, industry_name: str, existing_ids: set[str]) -> str:
    first_word = industry_name.split()[0].upper()[:6]
    base = f"{loc_id}-{first_word}"
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _display_catalog_entry(entry) -> None:
    click.echo(f"\nCatalog: {entry.id}")
    click.echo(f"  Name:     {entry.name}")
    click.echo(f"  Location: {entry.city}, {entry.state}")
    click.echo(f"  Railroad: {entry.railroad_id or '(unknown)'}")
    click.echo(f"  Source:   {entry.source} / {entry.source_file}")
    if entry.source_ref:
        click.echo(f"  Ref:      {entry.source_ref}")
    if entry.ships:
        click.echo(f"  Ships:    {', '.join(entry.ships)}")
    if entry.receives:
        click.echo(f"  Receives: {', '.join(entry.receives)}")
    if entry.car_types:
        click.echo(f"  Car types: {', '.join(entry.car_types)}")
    if entry.notes:
        click.echo(f"  Notes:    {entry.notes}")
    click.echo()
```

Then add the command after `search`:

```python
@main.command("add-industry")
@click.argument("catalog_id")
@click.option("--preview", is_flag=True, help="Show proposed YAML without writing")
@click.pass_context
def add_industry(ctx, catalog_id, preview):
    """Add a catalog industry entry to locations.yaml."""
    data_path = Path(ctx.obj["data_path"])
    catalog_path = data_path / "industry_catalog.yaml"
    locations_path = data_path / "locations.yaml"

    if not catalog_path.exists():
        click.echo("No industry_catalog.yaml found in data path.", err=True)
        raise SystemExit(1)

    repo = CatalogRepository(catalog_path)
    try:
        entry = repo.get(catalog_id)
    except KeyError:
        click.echo(f"Catalog entry not found: {catalog_id!r}", err=True)
        raise SystemExit(1)

    _display_catalog_entry(entry)

    raw_locations = yaml.safe_load(locations_path.read_text()) or []
    existing_loc_ids = {loc["id"] for loc in raw_locations}
    existing_ind_ids = {
        ind["id"]
        for loc in raw_locations
        for ind in loc.get("industries", [])
    }

    matches = [
        loc for loc in raw_locations
        if loc.get("name", "").lower() == entry.city.lower()
        and loc.get("state", "PA").upper() == entry.state.upper()
        and loc.get("railroad_id") == entry.railroad_id
    ]

    add_to_existing = False
    target_loc_id: str | None = None

    if len(matches) == 1:
        target_loc_id = matches[0]["id"]
        click.echo(f"Existing location found: {target_loc_id} ({matches[0]['name']})")
        if click.confirm("Add industry to this location?", default=True):
            add_to_existing = True
        else:
            target_loc_id = None
    elif len(matches) > 1:
        click.echo("Multiple matching locations:")
        for i, m in enumerate(matches, 1):
            click.echo(f"  [{i}] {m['id']} — {m['name']}")
        choice = click.prompt("Choose location number (0 = create new)", type=int, default=0)
        if 1 <= choice <= len(matches):
            target_loc_id = matches[choice - 1]["id"]
            add_to_existing = True

    if not add_to_existing:
        target_loc_id = _generate_location_id(entry.city, existing_loc_ids)

    ind_id = _generate_industry_id(target_loc_id, entry.name, existing_ind_ids)
    industry_dict = {
        "id": ind_id,
        "name": entry.name,
        "location_id": target_loc_id,
        "ships": entry.ships,
        "receives": entry.receives,
    }

    if add_to_existing:
        click.echo(f"Will add to location: {target_loc_id}")
        proposed_yaml = yaml.dump(industry_dict, default_flow_style=False, allow_unicode=True)
    else:
        new_loc: dict = {
            "id": target_loc_id,
            "name": entry.city,
            "state": entry.state,
            "industries": [industry_dict],
        }
        if entry.railroad_id:
            new_loc["railroad_id"] = entry.railroad_id
        click.echo(f"Will create new location: {target_loc_id}")
        proposed_yaml = yaml.dump([new_loc], default_flow_style=False, allow_unicode=True)

    click.echo("\nProposed YAML:\n---")
    click.echo(proposed_yaml.rstrip())
    click.echo("---\n")

    if preview:
        return

    action = click.prompt("Write to locations.yaml? [Y/e/N]", default="Y").strip().upper()

    if action == "N":
        click.echo("Cancelled.")
        return

    if action == "E":
        edited = click.edit(proposed_yaml, extension=".yaml")
        if edited is None:
            click.echo("No changes made. Cancelled.")
            return
        try:
            yaml.safe_load(edited)
        except yaml.YAMLError as exc:
            click.echo(f"Invalid YAML after editing: {exc}", err=True)
            raise SystemExit(1)
        proposed_yaml = edited

    if add_to_existing:
        parsed_industry = yaml.safe_load(proposed_yaml)
        locs = yaml.safe_load(locations_path.read_text()) or []
        for loc in locs:
            if loc["id"] == target_loc_id:
                loc.setdefault("industries", []).append(parsed_industry)
                break
        locations_path.write_text(yaml.dump(locs, default_flow_style=False, allow_unicode=True))
        click.echo(f"Added industry {ind_id} to {target_loc_id}.")
    else:
        with locations_path.open("a") as f:
            f.write("\n")
            f.write(proposed_yaml)
        click.echo(f"Added location {target_loc_id} with industry {ind_id} to locations.yaml.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli.py::test_add_industry_preview_shows_yaml tests/test_cli.py::test_add_industry_new_location_writes_file tests/test_cli.py::test_add_industry_cancel_does_not_write tests/test_cli.py::test_add_industry_missing_catalog tests/test_cli.py::test_add_industry_missing_catalog_id tests/test_cli.py::test_add_industry_existing_location -v
```

Expected: PASS (6 tests).

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 6: Smoke-test the command manually**

```bash
# Preview only — no file changes
waybill --data-path data add-industry cat-001 --preview

# Interactive add (creates new location CLR)
waybill --data-path data add-industry cat-001
```

Verify: `data/locations.yaml` gains a new `CLR` location entry with `Clearfield Coal Co.` after confirming with Y.

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/cli.py tests/test_cli.py
git commit -m "feat: add waybill add-industry command with preview and confirm flow"
```
