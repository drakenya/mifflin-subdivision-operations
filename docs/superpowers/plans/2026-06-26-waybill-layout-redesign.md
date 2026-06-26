# Waybill Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Railroad` entity, restructure the card into 3 zones (origination band / car / waybill), and redesign `StandardPrrLayout` with period-accurate serif typography and ruled form layouts.

**Architecture:** `Railroad` becomes a first-class entity loaded by the repository and resolved by the CLI. The rendering pipeline changes from `(Car, Waybill)` pairs to `(Car, Waybill, Railroad)` triples. `BaseLayout.draw_card()` gains a `Railroad` parameter and dispatches to a new `draw_origination_section()` method. `StandardPrrLayout` is fully redesigned with Times fonts, horizontal rules, and two-column field grids.

**Tech Stack:** Python 3.11+, Pydantic v2, ReportLab, PyYAML, Click, pytest

## Global Constraints

- Python 3.11+ required (`match` statements, `tomllib` from stdlib)
- Pydantic v2 — use `model_config`, `TypeAdapter`, `Literal[...]` discriminators
- ReportLab origin is bottom-left; y increases upward; units are points (1 pt = 1/72 inch)
- Card size: 2.5" × 3.5" = 180pt × 252pt, 9 per page (3×3 on 612pt × 792pt)
- Zone heights (outer): origination 35pt, car 65pt, waybill 152pt (total 252pt)
- Content inset: 4pt at external card edges only; not between zones
- No mocking of filesystem — use `tmp_path` and real file I/O
- All tests in `tests/`, mirroring source structure
- Fonts available in ReportLab without registration: `Times-Roman`, `Times-Bold`, `Times-Italic`, `Helvetica`, `Helvetica-Bold`

---

## File Map

| File | Change |
|---|---|
| `waybill_generator/models/railroad.py` | **New** — `Railroad` Pydantic model |
| `waybill_generator/models/__init__.py` | Export `Railroad` |
| `waybill_generator/models/waybill.py` | Add `originating_railroad_id` to `WaybillBase`; add `spot`, `shipper_ordered_by` to `EmptyWaybill` |
| `waybill_generator/repository/base.py` | Add `get_railroad()` / `get_railroads()` abstract methods |
| `waybill_generator/repository/yaml_repo.py` | Implement railroad loading from `railroads.yaml` |
| `waybill_generator/layouts/base.py` | Replace `car_section_fraction` with `origination_height_pt` + `car_height_pt`; add `draw_origination_section()` abstract method; update `draw_card()` |
| `waybill_generator/layouts/standard_prr.py` | Full visual redesign: Times fonts, ruled sections, origination band, 6 waybill type renderers |
| `waybill_generator/renderer/pdf.py` | Pairs → triples (`list[tuple[Car, WaybillBase, Railroad]]`) |
| `waybill_generator/cli.py` | Resolve `Railroad` from repo; pass triples to `render_pdf()`; add railroads to `validate` |
| `data/railroads.yaml` | **New** — PRR entry (and any road IDs referenced by existing waybills) |
| `data/waybills.yaml` | Add `originating_railroad_id: PRR` to all entries |
| `tests/fixtures/railroads.yaml` | **New** — PRR test fixture |
| `tests/fixtures/waybills.yaml` | Add `originating_railroad_id: PRR` to all entries |
| `tests/test_models.py` | Add `Railroad` tests; add `originating_railroad_id` to all waybill test data |
| `tests/test_repository.py` | Add railroad repo tests |
| `tests/test_layouts.py` | Add `Railroad` param; update `draw_card()` calls |
| `tests/test_renderer.py` | Update to triples |
| `tests/test_cli.py` | Update `validate` test; add `fixtures/railroads.yaml` to fixture set |

---

## Task 1: Railroad Entity

Adds the `Railroad` model, test fixture, data file, and repository support. No breaking changes to existing tests.

**Files:**
- Create: `waybill_generator/models/railroad.py`
- Modify: `waybill_generator/models/__init__.py`
- Create: `data/railroads.yaml`
- Create: `tests/fixtures/railroads.yaml`
- Modify: `waybill_generator/repository/base.py`
- Modify: `waybill_generator/repository/yaml_repo.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces: `Railroad` from `waybill_generator.models.railroad` with fields `id: str`, `name: str`, `form_number: str`, `icon: str | None = None`
- Produces: `BaseRepository.get_railroad(id: str) -> Railroad`, `BaseRepository.get_railroads() -> list[Railroad]`
- Produces: `YamlRepository.get_railroad()`, `YamlRepository.get_railroads()` — reads `railroads.yaml`

- [ ] **Step 1: Write failing Railroad model tests**

Add to `tests/test_models.py` (after existing imports and classes):

```python
from waybill_generator.models.railroad import Railroad

class TestRailroad:
    def test_basic_construction(self):
        r = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")
        assert r.id == "PRR"
        assert r.name == "Pennsylvania Railroad"
        assert r.form_number == "Form 1304"
        assert r.icon is None

    def test_with_icon(self):
        r = Railroad(id="NYC", name="New York Central", form_number="Form 200", icon="assets/nyc.png")
        assert r.icon == "assets/nyc.png"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Railroad(id="PRR", name="Pennsylvania Railroad")
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/krolla/code/mifflin-subdivision-operations && source .venv/bin/activate && pytest tests/test_models.py::TestRailroad -v
```

Expected: `ModuleNotFoundError: No module named 'waybill_generator.models.railroad'`

- [ ] **Step 3: Write `waybill_generator/models/railroad.py`**

```python
from pydantic import BaseModel


class Railroad(BaseModel):
    id: str
    name: str
    form_number: str
    icon: str | None = None
```

- [ ] **Step 4: Run to confirm model tests pass**

```bash
pytest tests/test_models.py::TestRailroad -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Write test fixture `tests/fixtures/railroads.yaml`**

```yaml
- id: PRR
  name: Pennsylvania Railroad
  form_number: "Form 1304"
  icon: null
```

- [ ] **Step 6: Write failing railroad repository tests**

Add to `tests/test_repository.py` (after existing imports, add `Railroad`):

```python
from waybill_generator.models.railroad import Railroad
```

Add a new test class after the existing ones:

```python
class TestYamlRepositoryRailroads:
    def test_get_railroads_returns_all(self, repo):
        railroads = repo.get_railroads()
        assert len(railroads) == 1

    def test_get_railroad_by_id(self, repo):
        r = repo.get_railroad("PRR")
        assert r.name == "Pennsylvania Railroad"
        assert r.form_number == "Form 1304"
        assert r.icon is None

    def test_get_railroad_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_railroad("MISSING")
```

- [ ] **Step 7: Run to confirm failure**

```bash
pytest tests/test_repository.py::TestYamlRepositoryRailroads -v
```

Expected: `AttributeError: 'YamlRepository' object has no attribute 'get_railroads'`

- [ ] **Step 8: Update `waybill_generator/repository/base.py`**

Add import and two abstract methods:

```python
from abc import ABC, abstractmethod
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import WaybillBase
from waybill_generator.models.railroad import Railroad


class BaseRepository(ABC):
    @abstractmethod
    def get_cars(self) -> list[Car]: ...

    @abstractmethod
    def get_car(self, id: str) -> Car: ...

    @abstractmethod
    def get_locations(self) -> list[Location]: ...

    @abstractmethod
    def get_location(self, id: str) -> Location: ...

    @abstractmethod
    def get_commodities(self) -> list[Commodity]: ...

    @abstractmethod
    def get_commodity(self, id: str) -> Commodity: ...

    @abstractmethod
    def get_waybills(self) -> list[WaybillBase]: ...

    @abstractmethod
    def get_waybill(self, id: str) -> WaybillBase: ...

    @abstractmethod
    def get_railroads(self) -> list[Railroad]: ...

    @abstractmethod
    def get_railroad(self, id: str) -> Railroad: ...
```

- [ ] **Step 9: Update `waybill_generator/repository/yaml_repo.py`**

Add import and railroad loading. Add after the existing imports:

```python
from waybill_generator.models.railroad import Railroad
```

Add `_railroads` cache attribute in `__init__`:

```python
def __init__(self, data_path: str | Path) -> None:
    self._path = Path(data_path)
    self._cars: dict[str, Car] | None = None
    self._locations: dict[str, Location] | None = None
    self._commodities: dict[str, Commodity] | None = None
    self._waybills: dict[str, WaybillBase] | None = None
    self._railroads: dict[str, Railroad] | None = None
```

Add these methods at the end of the class:

```python
def _ensure_railroads(self) -> dict[str, Railroad]:
    if self._railroads is None:
        self._railroads = {
            r.id: r for r in [Railroad(**row) for row in self._load("railroads.yaml")]
        }
    return self._railroads

def get_railroads(self) -> list[Railroad]:
    return list(self._ensure_railroads().values())

def get_railroad(self, id: str) -> Railroad:
    railroads = self._ensure_railroads()
    if id not in railroads:
        raise KeyError(f"Railroad not found: {id!r}")
    return railroads[id]
```

- [ ] **Step 10: Write `data/railroads.yaml`**

```yaml
- id: PRR
  name: Pennsylvania Railroad
  form_number: "Form 1304"
  icon: null
```

- [ ] **Step 11: Run all repository tests**

```bash
pytest tests/test_repository.py -v
```

Expected: all existing tests PASS, 3 new railroad tests PASS.

- [ ] **Step 12: Run full suite to confirm no regressions**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 13: Commit**

```bash
git add waybill_generator/models/railroad.py waybill_generator/repository/base.py \
        waybill_generator/repository/yaml_repo.py data/railroads.yaml \
        tests/fixtures/railroads.yaml tests/test_models.py tests/test_repository.py
git commit -m "feat: Railroad entity, repository support, PRR seed data"
```

---

## Task 2: Waybill Model Updates + Data Files

Adds `originating_railroad_id` (required) to `WaybillBase` and `spot`/`shipper_ordered_by` (optional) to `EmptyWaybill`. Updates all test fixtures, data files, and tests to provide the new required field.

**Files:**
- Modify: `waybill_generator/models/waybill.py`
- Modify: `tests/fixtures/waybills.yaml`
- Modify: `data/waybills.yaml`
- Modify: `tests/test_models.py`
- Modify: `tests/test_layouts.py`
- Modify: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `Railroad.id` string
- Produces: `WaybillBase.originating_railroad_id: str` (required), `EmptyWaybill.spot: str | None`, `EmptyWaybill.shipper_ordered_by: str | None`

- [ ] **Step 1: Update `waybill_generator/models/waybill.py`**

```python
from enum import Enum
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class WaybillType(str, Enum):
    LOADED = "LOADED"
    EMPTY = "EMPTY"
    DEADHEAD = "DEADHEAD"
    MOW = "MOW"
    HOLD = "HOLD"
    BAD_ORDER = "BAD_ORDER"


class WaybillBase(BaseModel):
    id: str
    waybill_type: WaybillType
    originating_railroad_id: str
    notes: str | None = None


class LoadedWaybill(WaybillBase):
    waybill_type: Literal["LOADED"] = "LOADED"
    commodity_id: str
    shipper_id: str
    consignee_id: str
    routing: list[str] = []


class EmptyWaybill(WaybillBase):
    waybill_type: Literal["EMPTY"] = "EMPTY"
    from_location_id: str
    to_location_id: str
    spot: str | None = None
    shipper_ordered_by: str | None = None


class DeadheadWaybill(WaybillBase):
    waybill_type: Literal["DEADHEAD"] = "DEADHEAD"
    from_location_id: str
    to_location_id: str
    consist_note: str | None = None


class MoWWaybill(WaybillBase):
    waybill_type: Literal["MOW"] = "MOW"
    commodity_desc: str
    from_location_id: str
    to_location_id: str
    project: str | None = None


class HoldWaybill(WaybillBase):
    waybill_type: Literal["HOLD"] = "HOLD"
    industry_id: str
    waiting_for: str


class BadOrderWaybill(WaybillBase):
    waybill_type: Literal["BAD_ORDER"] = "BAD_ORDER"
    from_location_id: str
    shop_location_id: str
    defect: str | None = None


Waybill = Annotated[
    Union[
        LoadedWaybill, EmptyWaybill, DeadheadWaybill,
        MoWWaybill, HoldWaybill, BadOrderWaybill,
    ],
    Field(discriminator="waybill_type"),
]
```

- [ ] **Step 2: Run tests to see failures from missing required field**

```bash
pytest tests/test_models.py tests/test_repository.py -v 2>&1 | head -40
```

Expected: `ValidationError` failures — `originating_railroad_id` is required but missing from test data.

- [ ] **Step 3: Update `tests/fixtures/waybills.yaml`**

```yaml
- id: waybill-1
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: grain
  shipper_id: LEW-GRAIN
  consignee_id: ALT-SHOP

- id: empty-1
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: ALT
  to_location_id: LEW

- id: badorder-1
  waybill_type: BAD_ORDER
  originating_railroad_id: PRR
  from_location_id: LEW
  shop_location_id: ALT
  defect: Broken coupler

- id: deadhead-1
  waybill_type: DEADHEAD
  originating_railroad_id: PRR
  from_location_id: PHL
  to_location_id: PGH
  consist_note: PRR 4100 combine

- id: mow-1
  waybill_type: MOW
  originating_railroad_id: PRR
  commodity_desc: Ballast
  from_location_id: ALT
  to_location_id: LEW

- id: hold-1
  waybill_type: HOLD
  originating_railroad_id: PRR
  industry_id: LEW-GRAIN
  waiting_for: Load order
```

- [ ] **Step 4: Update `tests/test_models.py` waybill test data**

Replace all `_waybill_adapter.validate_python({...})` calls in `TestWaybillDiscrimination` to include `"originating_railroad_id": "PRR"`:

```python
class TestWaybillDiscrimination:
    def test_loaded_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "w-1", "waybill_type": "LOADED", "originating_railroad_id": "PRR",
            "commodity_id": "grain", "shipper_id": "LEW-GRAIN", "consignee_id": "ALT-MILL",
        })
        assert isinstance(w, LoadedWaybill)
        assert w.routing == []
        assert w.originating_railroad_id == "PRR"

    def test_empty_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "e-1", "waybill_type": "EMPTY", "originating_railroad_id": "PRR",
            "from_location_id": "ALT", "to_location_id": "LEW",
        })
        assert isinstance(w, EmptyWaybill)
        assert w.spot is None
        assert w.shipper_ordered_by is None

    def test_empty_waybill_optional_fields(self):
        w = _waybill_adapter.validate_python({
            "id": "e-2", "waybill_type": "EMPTY", "originating_railroad_id": "PRR",
            "from_location_id": "ALT", "to_location_id": "LEW",
            "spot": "Track 4", "shipper_ordered_by": "Standard Oil",
        })
        assert w.spot == "Track 4"
        assert w.shipper_ordered_by == "Standard Oil"

    def test_deadhead_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "d-1", "waybill_type": "DEADHEAD", "originating_railroad_id": "PRR",
            "from_location_id": "PHL", "to_location_id": "PGH",
            "consist_note": "PRR 4100",
        })
        assert isinstance(w, DeadheadWaybill)

    def test_mow_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "m-1", "waybill_type": "MOW", "originating_railroad_id": "PRR",
            "commodity_desc": "Ballast", "from_location_id": "ALT", "to_location_id": "LEW",
        })
        assert isinstance(w, MoWWaybill)

    def test_hold_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "h-1", "waybill_type": "HOLD", "originating_railroad_id": "PRR",
            "industry_id": "LEW-GRAIN", "waiting_for": "Load order",
        })
        assert isinstance(w, HoldWaybill)

    def test_bad_order_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "b-1", "waybill_type": "BAD_ORDER", "originating_railroad_id": "PRR",
            "from_location_id": "LEW", "shop_location_id": "ALT",
        })
        assert isinstance(w, BadOrderWaybill)
        assert w.defect is None

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            _waybill_adapter.validate_python({
                "id": "x-1", "waybill_type": "UNKNOWN", "originating_railroad_id": "PRR",
            })
```

- [ ] **Step 5: Update `tests/test_layouts.py` waybill constructions**

Replace the `WAYBILLS` list to include `originating_railroad_id="PRR"` on every entry:

```python
WAYBILLS = [
    LoadedWaybill(id="w-1", originating_railroad_id="PRR",
                  commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP"),
    EmptyWaybill(id="e-1", originating_railroad_id="PRR",
                 from_location_id="ALT", to_location_id="LEW"),
    DeadheadWaybill(id="d-1", originating_railroad_id="PRR",
                    from_location_id="PHL", to_location_id="PGH"),
    MoWWaybill(id="m-1", originating_railroad_id="PRR",
               commodity_desc="Ballast", from_location_id="ALT", to_location_id="LEW"),
    HoldWaybill(id="h-1", originating_railroad_id="PRR",
                industry_id="LEW-GRAIN", waiting_for="Load order"),
    BadOrderWaybill(id="b-1", originating_railroad_id="PRR",
                    from_location_id="LEW", shop_location_id="ALT"),
]
```

- [ ] **Step 6: Update `tests/test_renderer.py` waybill constructions**

```python
LOADED = LoadedWaybill(id="w-1", originating_railroad_id="PRR",
                       commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP")
EMPTY = EmptyWaybill(id="e-1", originating_railroad_id="PRR",
                     from_location_id="ALT", to_location_id="LEW")
```

- [ ] **Step 7: Update `data/waybills.yaml`**

Add `originating_railroad_id: PRR` as the third field (after `id` and `waybill_type`) on every entry. The full file:

```yaml
# ── LOADED ──────────────────────────────────────────────────────────────────

- id: waybill-1
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: grain
  shipper_id: LEW-GRAIN
  consignee_id: HBG-FREIGHT
  notes: Forward to eastern connections if required

- id: waybill-2
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: coal
  shipper_id: LJ-YARD
  consignee_id: BRN-SSW
  notes: Coal from clearfield branch via LJ

- id: waybill-3
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: iron-ore
  shipper_id: PGH-YARD
  consignee_id: BRN-SSW

- id: waybill-4
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: limestone
  shipper_id: MCV-LIME
  consignee_id: BRN-SSW

- id: waybill-5
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: limestone
  shipper_id: MCV-LIME
  consignee_id: LEW-CEMENT

- id: waybill-6
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: wheel-sets
  shipper_id: BRN-SSW
  consignee_id: ALT-SHOP
  notes: Wheel sets for Altoona Shops

- id: waybill-7
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: wheel-sets
  shipper_id: BRN-SSW
  consignee_id: PGH-STEEL
  routing:
    - LJ
    - ALT

- id: waybill-8
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: steel
  shipper_id: BRN-SSW
  consignee_id: PGH-STEEL

- id: waybill-9
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: flour
  shipper_id: LEW-GRAIN
  consignee_id: HBG-FREIGHT

- id: waybill-10
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: cement
  shipper_id: LEW-CEMENT
  consignee_id: MIF-FREIGHT

- id: waybill-11
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: lumber
  shipper_id: HBG-YARD
  consignee_id: LEW-FREIGHT

- id: waybill-12
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: canned-goods
  shipper_id: HBG-YARD
  consignee_id: MIF-FREIGHT

- id: waybill-13
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: general-merchandise
  shipper_id: HBG-FREIGHT
  consignee_id: LEW-FREIGHT

- id: waybill-14
  waybill_type: LOADED
  originating_railroad_id: PRR
  commodity_id: grain
  shipper_id: MIF-GRAIN
  consignee_id: HBG-FREIGHT

# ── EMPTY ────────────────────────────────────────────────────────────────────

- id: empty-1
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: ALT
  to_location_id: LEW

- id: empty-2
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: HBG
  to_location_id: BRN
  notes: Empty hopper to Standard Steel

- id: empty-3
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: PGH
  to_location_id: MCV
  notes: Empty gondola to quarry

- id: empty-4
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: BRN
  to_location_id: MCV
  notes: Empty after limestone delivery

- id: empty-5
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: ALT
  to_location_id: HBG

- id: empty-6
  waybill_type: EMPTY
  originating_railroad_id: PRR
  from_location_id: LEW
  to_location_id: PGH
  notes: Empty boxcar returning east

# ── DEADHEAD ─────────────────────────────────────────────────────────────────

- id: deadhead-1
  waybill_type: DEADHEAD
  originating_railroad_id: PRR
  from_location_id: PGH
  to_location_id: ALT
  consist_note: PRR 4100 combine

- id: deadhead-2
  waybill_type: DEADHEAD
  originating_railroad_id: PRR
  from_location_id: HBG
  to_location_id: ALT
  consist_note: PRR 3672 coach — Altoona for inspection

- id: deadhead-3
  waybill_type: DEADHEAD
  originating_railroad_id: PRR
  from_location_id: ALT
  to_location_id: PGH
  consist_note: PRR 5821 RPO — return after repair

# ── MAINTENANCE OF WAY ───────────────────────────────────────────────────────

- id: mow-1
  waybill_type: MOW
  originating_railroad_id: PRR
  commodity_desc: Ballast
  from_location_id: ALT
  to_location_id: LEW
  project: Track resurfacing MP 152-160

- id: mow-2
  waybill_type: MOW
  originating_railroad_id: PRR
  commodity_desc: Tie plates and spikes
  from_location_id: ALT
  to_location_id: MIF
  project: Crossover renewal at Mifflin

- id: mow-3
  waybill_type: MOW
  originating_railroad_id: PRR
  commodity_desc: 115 lb. relay rail
  from_location_id: LJ
  to_location_id: BRN
  project: Yard track renewal — Standard Steel lead

- id: mow-4
  waybill_type: MOW
  originating_railroad_id: PRR
  commodity_desc: Ballast
  from_location_id: ALT
  to_location_id: HBG
  project: Grade stabilization — Tuscarora cut

# ── HOLD ─────────────────────────────────────────────────────────────────────

- id: hold-1
  waybill_type: HOLD
  originating_railroad_id: PRR
  industry_id: LEW-GRAIN
  waiting_for: Load order from elevator

- id: hold-2
  waybill_type: HOLD
  originating_railroad_id: PRR
  industry_id: BRN-SSW
  waiting_for: Production cycle — next wheel set cast

- id: hold-3
  waybill_type: HOLD
  originating_railroad_id: PRR
  industry_id: MCV-LIME
  waiting_for: Car release from quarry tipple

- id: hold-4
  waybill_type: HOLD
  originating_railroad_id: PRR
  industry_id: LEW-FREIGHT
  waiting_for: Consignee pickup — Lewistown Hardware Co.

# ── BAD ORDER ────────────────────────────────────────────────────────────────

- id: badorder-1
  waybill_type: BAD_ORDER
  originating_railroad_id: PRR
  from_location_id: LEW
  shop_location_id: ALT
  defect: Broken coupler knuckle

- id: badorder-2
  waybill_type: BAD_ORDER
  originating_railroad_id: PRR
  from_location_id: BRN
  shop_location_id: ALT
  defect: Hotbox — journal bearing failure

- id: badorder-3
  waybill_type: BAD_ORDER
  originating_railroad_id: PRR
  from_location_id: HBG
  shop_location_id: ALT
  defect: Defective brake gear — hand brake inoperative

- id: badorder-4
  waybill_type: BAD_ORDER
  originating_railroad_id: PRR
  from_location_id: MIF
  shop_location_id: ALT
  defect: Cracked center sill — shop inspection required
```

- [ ] **Step 8: Run full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add waybill_generator/models/waybill.py data/waybills.yaml \
        tests/fixtures/waybills.yaml tests/test_models.py \
        tests/test_layouts.py tests/test_renderer.py
git commit -m "feat: add originating_railroad_id to WaybillBase, spot/shipper_ordered_by to EmptyWaybill"
```

---

## Task 3: Layout Interface + Renderer — 3 Zones, Triples

Restructures `BaseLayout` for 3 zones, updates `draw_card()` to accept a `Railroad`, and changes the rendering pipeline from pairs to triples. `StandardPrrLayout` gets a stub `draw_origination_section()` that just draws the band boundary — the full visual comes in Task 4.

**Files:**
- Modify: `waybill_generator/layouts/base.py`
- Modify: `waybill_generator/layouts/standard_prr.py`
- Modify: `waybill_generator/renderer/pdf.py`
- Modify: `tests/test_layouts.py`
- Modify: `tests/test_renderer.py`

**Interfaces:**
- Produces: `BaseLayout.origination_height_pt: float = 35.0`, `BaseLayout.car_height_pt: float = 65.0` (replaces `car_section_fraction`)
- Produces: `BaseLayout.draw_card(canvas, car, waybill, railroad, x, y)` — adds `railroad: Railroad` param
- Produces: `BaseLayout.draw_origination_section(canvas, railroad, waybill, x, y, w, h)` — new abstract method; receives both railroad AND waybill (waybill type determines the bill-type label)
- Produces: `render_pdf(triples: list[tuple[Car, WaybillBase, Railroad]], layout, output_path)`

- [ ] **Step 1: Update `tests/test_layouts.py` for new signatures**

Replace the full file:

```python
import io
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import (
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

CAR = Car(
    id="PRR-12345", road="PRR", car_number="12345",
    car_type="X29", aar_code="XM", capacity_tons=50,
)

RR = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")

WAYBILLS = [
    LoadedWaybill(id="w-1", originating_railroad_id="PRR",
                  commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP"),
    EmptyWaybill(id="e-1", originating_railroad_id="PRR",
                 from_location_id="ALT", to_location_id="LEW"),
    DeadheadWaybill(id="d-1", originating_railroad_id="PRR",
                    from_location_id="PHL", to_location_id="PGH"),
    MoWWaybill(id="m-1", originating_railroad_id="PRR",
               commodity_desc="Ballast", from_location_id="ALT", to_location_id="LEW"),
    HoldWaybill(id="h-1", originating_railroad_id="PRR",
                industry_id="LEW-GRAIN", waiting_for="Load order"),
    BadOrderWaybill(id="b-1", originating_railroad_id="PRR",
                    from_location_id="LEW", shop_location_id="ALT"),
]


def test_layout_constants():
    layout = StandardPrrLayout()
    assert layout.card_width_pt == 180.0
    assert layout.card_height_pt == 252.0
    assert layout.origination_height_pt == 35.0
    assert layout.car_height_pt == 65.0
    assert layout.gutter_pt == 9.0
    assert layout.content_inset_pt == 4.0


def test_draw_card_all_waybill_types():
    layout = StandardPrrLayout()
    for waybill in WAYBILLS:
        buf = io.BytesIO()
        canvas = Canvas(buf, pagesize=letter)
        layout.draw_card(canvas, CAR, waybill, RR, x=0, y=0)
        canvas.save()
        content = buf.getvalue()
        assert b"%PDF" in content
        assert len(content) > 500, f"Card for {waybill.waybill_type} produced suspiciously small PDF"
```

- [ ] **Step 2: Update `tests/test_renderer.py` for triples**

Replace the full file:

```python
from pathlib import Path
from waybill_generator.renderer.pdf import render_pdf
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import LoadedWaybill, EmptyWaybill

CAR_A = Car(id="PRR-1", road="PRR", car_number="1", car_type="X29", aar_code="XM", capacity_tons=50)
CAR_B = Car(id="PRR-2", road="PRR", car_number="2", car_type="H21a", aar_code="HM", capacity_tons=70)
RR = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")
LOADED = LoadedWaybill(id="w-1", originating_railroad_id="PRR",
                       commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP")
EMPTY = EmptyWaybill(id="e-1", originating_railroad_id="PRR",
                     from_location_id="ALT", to_location_id="LEW")


def test_render_creates_pdf(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED, RR)], StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_pdf_header(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED, RR)], StandardPrrLayout(), out)
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_multiple_triples(tmp_path):
    out = tmp_path / "multi.pdf"
    triples = [(CAR_A, LOADED, RR), (CAR_B, EMPTY, RR)] * 5  # 10 cards = 2 pages
    render_pdf(triples, StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_render_empty_list(tmp_path):
    out = tmp_path / "empty.pdf"
    render_pdf([], StandardPrrLayout(), out)
    assert out.exists()
```

- [ ] **Step 3: Run to confirm failures**

```bash
pytest tests/test_layouts.py tests/test_renderer.py -v 2>&1 | head -30
```

Expected: failures — `AttributeError` on missing `origination_height_pt`, wrong `draw_card` signature.

- [ ] **Step 4: Rewrite `waybill_generator/layouts/base.py`**

```python
from abc import ABC, abstractmethod
from reportlab.pdfgen.canvas import Canvas
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import WaybillBase


class BaseLayout(ABC):
    card_width_pt: float = 180.0
    card_height_pt: float = 252.0
    origination_height_pt: float = 35.0
    car_height_pt: float = 65.0
    gutter_pt: float = 9.0
    content_inset_pt: float = 4.0

    def draw_card(
        self,
        canvas: Canvas,
        car: Car,
        waybill: WaybillBase,
        railroad: Railroad,
        x: float,
        y: float,
    ) -> None:
        w = self.card_width_pt
        h = self.card_height_pt
        inset = self.content_inset_pt
        orig_h = self.origination_height_pt
        car_h = self.car_height_pt
        waybill_h = h - orig_h - car_h  # 152

        # Waybill zone (bottom): inset at bottom and sides only
        self.draw_waybill_section(
            canvas, waybill,
            x + inset, y + inset,
            w - 2 * inset, waybill_h - inset,
        )
        # Car zone (middle): bounded by zones above and below, inset sides only
        self.draw_car_section(
            canvas, car,
            x + inset, y + waybill_h,
            w - 2 * inset, car_h,
        )
        # Origination zone (top): inset at top and sides only
        self.draw_origination_section(
            canvas, railroad, waybill,
            x + inset, y + waybill_h + car_h,
            w - 2 * inset, orig_h - inset,
        )

    @abstractmethod
    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None: ...

    @abstractmethod
    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None: ...

    @abstractmethod
    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None: ...
```

- [ ] **Step 5: Add `draw_origination_section()` stub to `waybill_generator/layouts/standard_prr.py`**

Add this method at the top of the `StandardPrrLayout` class (before `draw_car_section`):

```python
from waybill_generator.models.railroad import Railroad

# Add to imports at top of file:
# from waybill_generator.models.railroad import Railroad

def draw_origination_section(
    self,
    canvas: Canvas,
    railroad: Railroad,
    waybill: WaybillBase,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    canvas.setStrokeColor(black)
    canvas.setLineWidth(0.5)
    canvas.line(x, y, x + w, y)  # bottom rule only — full design in Task 4
```

Also add `Railroad` to the import at the top of `standard_prr.py`:

```python
from waybill_generator.models.railroad import Railroad
```

- [ ] **Step 6: Update `waybill_generator/renderer/pdf.py`**

```python
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import WaybillBase

_COLS = 3
_ROWS = 3
_PER_PAGE = _COLS * _ROWS
_PAGE_W, _PAGE_H = letter  # 612, 792


def render_pdf(
    triples: list[tuple[Car, WaybillBase, Railroad]],
    layout: BaseLayout,
    output_path: str | Path,
) -> None:
    canvas = Canvas(str(output_path), pagesize=letter)

    if not triples:
        canvas.save()
        return

    g = layout.gutter_pt
    cw = layout.card_width_pt
    ch = layout.card_height_pt

    left_margin = (_PAGE_W - (_COLS * cw + (_COLS + 1) * g)) / 2
    bottom_margin = (_PAGE_H - (_ROWS * ch + (_ROWS + 1) * g)) / 2

    for page_idx, page_triples in enumerate(_chunks(triples, _PER_PAGE)):
        if page_idx > 0:
            canvas.showPage()

        for card_idx, (car, waybill, railroad) in enumerate(page_triples):
            col = card_idx % _COLS
            row = card_idx // _COLS

            x = left_margin + g + col * (cw + g)
            y = _PAGE_H - bottom_margin - g - (row + 1) * ch - row * g

            layout.draw_card(canvas, car, waybill, railroad, x, y)
            _draw_crop_marks(canvas, x, y, cw, ch, g)

    canvas.save()


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _draw_crop_marks(
    canvas: Canvas, x: float, y: float, w: float, h: float, gutter: float
) -> None:
    mark = min(gutter * 0.5, 4.5)
    canvas.setStrokeColorRGB(0.6, 0.6, 0.6)
    canvas.setLineWidth(0.25)

    canvas.line(x - mark, y, x, y)
    canvas.line(x, y - mark, x, y)
    canvas.line(x + w, y, x + w + mark, y)
    canvas.line(x + w, y - mark, x + w, y)
    canvas.line(x - mark, y + h, x, y + h)
    canvas.line(x, y + h, x, y + h + mark)
    canvas.line(x + w, y + h, x + w + mark, y + h)
    canvas.line(x + w, y + h, x + w, y + h + mark)
```

- [ ] **Step 7: Run layout and renderer tests**

```bash
pytest tests/test_layouts.py tests/test_renderer.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS (CLI tests still pass because `draw_card` internal changes don't affect the CLI's interface — wait, CLI calls `render_pdf` which now expects triples, so CLI test `test_generate_produces_pdf` will fail). Fix the CLI in the next step.

- [ ] **Step 9: Update `waybill_generator/cli.py` `generate` command to pass triples**

In the `generate` command, replace the pairs loop:

```python
@main.command()
@click.option("--session", required=True, type=click.Path(exists=True), help="Session YAML file")
@click.option("--output", default=None, help="Output PDF path")
@click.pass_context
def generate(ctx, session, output):
    """Generate a PDF from a session file."""
    session_data = yaml.safe_load(Path(session).read_text())
    repo = _get_repo(ctx)

    triples = []
    for card in session_data.get("cards", []):
        car = repo.get_car(card["car"])
        waybill = repo.get_waybill(card["waybill"])
        railroad = repo.get_railroad(waybill.originating_railroad_id)
        triples.append((car, waybill, railroad))

    layout_cls = _LAYOUTS.get(ctx.obj["layout"])
    if layout_cls is None:
        raise click.BadParameter(f"Unknown layout: {ctx.obj['layout']!r}")
    layout = layout_cls()

    if output is None:
        out_dir = Path(ctx.obj["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        output = str(out_dir / f"waybills-{date.today().isoformat()}.pdf")

    render_pdf(triples, layout, output)
    click.echo(f"Generated: {output}")
```

Also update the `validate` command to check railroads:

```python
@main.command()
@click.pass_context
def validate(ctx):
    """Validate all data files against schema."""
    repo = _get_repo(ctx)
    errors = []

    for label, loader in [
        ("Cars", repo.get_cars),
        ("Locations", repo.get_locations),
        ("Commodities", repo.get_commodities),
        ("Waybills", repo.get_waybills),
        ("Railroads", repo.get_railroads),
    ]:
        try:
            items = loader()
            click.echo(f"{label}: {len(items)} loaded")
        except Exception as e:
            errors.append(f"{label}: {e}")

    if errors:
        for err in errors:
            click.echo(f"ERROR: {err}", err=True)
        raise SystemExit(1)
    else:
        click.echo("All data files valid.")
```

- [ ] **Step 10: Update `tests/test_cli.py`**

Update the `validate` test to expect the new "Railroads" line, and ensure the fixture directory has `railroads.yaml` (it already does from Task 1):

```python
def test_validate_passes_with_valid_data():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "validate"])
    assert result.exit_code == 0
    assert "Cars: 2" in result.output
    assert "Waybills: 6" in result.output
    assert "Railroads: 1" in result.output
```

- [ ] **Step 11: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 12: Commit**

```bash
git add waybill_generator/layouts/base.py waybill_generator/layouts/standard_prr.py \
        waybill_generator/renderer/pdf.py waybill_generator/cli.py \
        tests/test_layouts.py tests/test_renderer.py tests/test_cli.py
git commit -m "feat: 3-zone card layout, Railroad param in draw_card, render_pdf pairs→triples"
```

---

## Task 4: StandardPrrLayout Visual Redesign

Replaces the Helvetica/badge-based layout with Times serif typography, horizontal rules, and two-column field grids matching the period freight form aesthetic.

**Files:**
- Modify: `waybill_generator/layouts/standard_prr.py`

**Interfaces:**
- Consumes: `BaseLayout.draw_origination_section(canvas, railroad, waybill, x, y, w, h)`, `BaseLayout.draw_car_section(canvas, car, x, y, w, h)`, `BaseLayout.draw_waybill_section(canvas, waybill, x, y, w, h)`
- Produces: complete visual redesign of all 3 sections, 6 waybill type renderers

- [ ] **Step 1: Run existing layout tests as baseline**

```bash
pytest tests/test_layouts.py -v
```

Expected: 2 tests PASS. (They test that draw_card doesn't crash — visual correctness is verified by generating a PDF.)

- [ ] **Step 2: Replace `waybill_generator/layouts/standard_prr.py`**

```python
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black, HexColor
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import (
    WaybillBase, WaybillType,
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

_PRR_TUSCAN = HexColor("#7B1113")
_WHITE = HexColor("#FFFFFF")

_BILL_TYPE_LABELS: dict[WaybillType, str] = {
    WaybillType.LOADED: "FREIGHT WAYBILL",
    WaybillType.EMPTY: "EMPTY CAR BILL",
    WaybillType.DEADHEAD: "DEADHEAD ORDER",
    WaybillType.MOW: "M-O-W SERVICE BILL",
    WaybillType.HOLD: "HOLD ORDER",
    WaybillType.BAD_ORDER: "BAD ORDER CARD",
}


class StandardPrrLayout(BaseLayout):

    # ── Origination Band ──────────────────────────────────────────────────────

    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)  # bottom rule

        # Herald icon — left-aligned if path exists
        icon_right = x
        if railroad.icon:
            icon_path = Path(railroad.icon)
            if icon_path.exists():
                icon_size = h - 4
                canvas.drawImage(
                    str(icon_path), x + 2, y + 2,
                    width=icon_size, height=icon_size,
                    preserveAspectRatio=True, mask="auto",
                )
                icon_right = x + icon_size + 4

        bill_label = _BILL_TYPE_LABELS[waybill.waybill_type]

        # Form number — top-left corner
        canvas.setFont("Times-Roman", 5)
        canvas.setFillColor(black)
        canvas.drawString(icon_right + 2, y + h - 7, railroad.form_number)

        # Railroad name — centered
        canvas.setFont("Times-Bold", 8)
        canvas.drawCentredString(x + w / 2, y + h / 2 + 1, railroad.name)

        # Bill type — centered below railroad name
        canvas.setFont("Times-Roman", 6)
        canvas.drawCentredString(x + w / 2, y + 4, bill_label)

    # ── Car Section ───────────────────────────────────────────────────────────

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setFillColor(_PRR_TUSCAN)
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.rect(x, y, w, h, fill=1)

        mid = x + w / 2
        canvas.setStrokeColor(_WHITE)
        canvas.setLineWidth(0.4)
        canvas.line(mid, y + 4, mid, y + h - 4)

        canvas.setFillColor(_WHITE)

        # Labels
        canvas.setFont("Times-Roman", 5)
        canvas.drawString(x + 3, y + h - 8, "CAR INITIAL")
        canvas.drawString(mid + 3, y + h - 8, "CAR NUMBER")

        # Values
        canvas.setFont("Times-Bold", 10)
        canvas.drawString(x + 3, y + h - 20, car.road)
        canvas.drawString(mid + 3, y + h - 20, car.car_number)

        # Car type / capacity — bottom
        canvas.setFont("Times-Roman", 6)
        cap = f"{car.car_type}  {car.aar_code}  {car.capacity_tons}T"
        if car.capacity_cuft:
            cap += f"  {car.capacity_cuft} cu ft"
        canvas.drawString(x + 3, y + 4, cap)

    # ── Waybill Section ───────────────────────────────────────────────────────

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.rect(x, y, w, h)

        match waybill.waybill_type:
            case WaybillType.LOADED:
                self._draw_loaded(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.EMPTY:
                self._draw_empty(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.DEADHEAD:
                self._draw_deadhead(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.MOW:
                self._draw_mow(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.HOLD:
                self._draw_hold(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.BAD_ORDER:
                self._draw_bad_order(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"Unhandled waybill type: {waybill.waybill_type}")

    # ── Shared drawing primitives ─────────────────────────────────────────────

    def _rule(self, canvas: Canvas, x: float, y: float, w: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)

    def _vcol(self, canvas: Canvas, x: float, y: float, h: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(x, y, x, y + h)

    def _label(self, canvas: Canvas, text: str, x: float, y: float) -> None:
        canvas.setFont("Times-Roman", 5)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value(self, canvas: Canvas, text: str, x: float, y: float, size: int = 9) -> None:
        canvas.setFont("Times-Bold", size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _section_header(self, canvas: Canvas, text: str, x: float, y: float, w: float) -> None:
        """Bold centered section header with double rules above and below."""
        canvas.setFont("Times-Bold", 8)
        canvas.setFillColor(black)
        canvas.drawCentredString(x + w / 2, y + 3, text)
        self._rule(canvas, x, y + 13, w)
        self._rule(canvas, x, y + 1, w)

    # ── Waybill type renderers ────────────────────────────────────────────────

    def _draw_loaded(
        self, canvas: Canvas, w: LoadedWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        mid = x + ww / 2
        cursor = y + h

        # Row 1: TO / FROM stations (consignee / shipper)
        cursor -= 2
        self._label(canvas, "TO (CONSIGNEE)", x + 2, cursor - 6)
        self._label(canvas, "FROM (SHIPPER)", mid + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.consignee_id, x + 2, cursor - 10, size=8)
        self._value(canvas, w.shipper_id, mid + 2, cursor - 10, size=8)
        self._vcol(canvas, mid, cursor - 12, 20)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        # Row 2: Commodity
        cursor -= 2
        self._label(canvas, "DESCRIPTION OF ARTICLES", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.commodity_id, x + 2, cursor - 10, size=9)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        # Row 3: Route (if present)
        if w.routing:
            cursor -= 2
            self._label(canvas, "ROUTE — SHOW IN ROUTE ORDER", x + 2, cursor - 6)
            cursor -= 8
            self._value(canvas, "  —  ".join(w.routing), x + 2, cursor - 9, size=7)
            cursor -= 12
            self._rule(canvas, x, cursor, ww)

        # Notes (if present)
        if w.notes:
            cursor -= 2
            self._label(canvas, "REMARKS", x + 2, cursor - 6)
            cursor -= 8
            canvas.setFont("Times-Italic", 6)
            canvas.setFillColor(black)
            canvas.drawString(x + 2, cursor - 8, w.notes[:60])

    def _draw_empty(
        self, canvas: Canvas, w: EmptyWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h

        # Section header
        cursor -= 16
        self._section_header(canvas, "FOR LOADING", x, cursor, ww)
        cursor -= 2

        # Billed from
        self._label(canvas, "BILLED FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        # To
        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.to_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        # Shipper / Spot (if present)
        if w.shipper_ordered_by or w.spot:
            mid = x + ww / 2
            cursor -= 2
            self._label(canvas, "SHIPPER", x + 2, cursor - 6)
            self._label(canvas, "SPOT", mid + 2, cursor - 6)
            cursor -= 8
            self._value(canvas, w.shipper_ordered_by or "", x + 2, cursor - 9, size=8)
            self._value(canvas, w.spot or "", mid + 2, cursor - 9, size=8)
            self._vcol(canvas, mid, cursor - 11, 19)
            cursor -= 12
            self._rule(canvas, x, cursor, ww)

        # Instruction text at bottom
        canvas.setFont("Times-Roman", 5)
        canvas.setFillColor(black)
        canvas.drawString(x + 2, y + 6,
            "This bill must accompany car to destination.")

    def _draw_deadhead(
        self, canvas: Canvas, w: DeadheadWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.to_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.consist_note:
            cursor -= 2
            self._label(canvas, "CONSIST", x + 2, cursor - 6)
            cursor -= 8
            self._value(canvas, w.consist_note, x + 2, cursor - 9, size=7)

    def _draw_mow(
        self, canvas: Canvas, w: MoWWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "MATERIAL", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.commodity_desc, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "TO", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.to_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.project:
            cursor -= 2
            self._label(canvas, "PROJECT", x + 2, cursor - 6)
            cursor -= 8
            self._value(canvas, w.project, x + 2, cursor - 9, size=6)

    def _draw_hold(
        self, canvas: Canvas, w: HoldWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "HOLD AT", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.industry_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "WAITING FOR", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.waiting_for, x + 2, cursor - 9, size=7)

    def _draw_bad_order(
        self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float
    ) -> None:
        cursor = y + h - 2

        self._label(canvas, "FROM", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.from_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        cursor -= 2
        self._label(canvas, "REPAIR SHOP", x + 2, cursor - 6)
        cursor -= 8
        self._value(canvas, w.shop_location_id, x + 2, cursor - 10)
        cursor -= 14
        self._rule(canvas, x, cursor, ww)

        if w.defect:
            cursor -= 2
            self._label(canvas, "DEFECT", x + 2, cursor - 6)
            cursor -= 8
            self._value(canvas, w.defect, x + 2, cursor - 9, size=7)
```

- [ ] **Step 3: Run layout tests**

```bash
pytest tests/test_layouts.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 4: Run full suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Generate a test PDF and visually inspect it**

```bash
source .venv/bin/activate
waybill generate --session sessions/test-9up.yaml --output output/test-redesign.pdf
open output/test-redesign.pdf
```

Verify: origination band at top (railroad name, bill type, form number), Tuscan Red car section in middle, ruled waybill fields at bottom. Adjust font sizes or coordinate offsets in `standard_prr.py` as needed to fit content cleanly. Re-run `pytest` after any adjustments.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/layouts/standard_prr.py
git commit -m "feat: StandardPrrLayout visual redesign — Times serif, ruled form layout, origination band"
```

---

## Self-Review

**Spec coverage:**
- Railroad entity (model, fixture, data file, repo methods) → Task 1 ✓
- `originating_railroad_id` required on `WaybillBase` → Task 2 ✓
- `spot` and `shipper_ordered_by` on `EmptyWaybill` → Task 2 ✓
- `BaseLayout` replaces `car_section_fraction` with `origination_height_pt` + `car_height_pt` → Task 3 ✓
- `draw_origination_section(canvas, railroad, waybill, x, y, w, h)` abstract method → Task 3 ✓
- Zone heights: origination 35pt, car 65pt, waybill 152pt → Task 3 ✓
- Renderer pairs → triples → Task 3 ✓
- CLI resolves railroad, passes triples → Task 3 ✓
- Origination band: railroad name, bill type label, form number, icon → Task 4 ✓
- Car section: CAR INITIAL / CAR NUMBER two-column, Times-Bold 10pt, capacity bottom → Task 4 ✓
- Waybill LOADED: two-column consignee/shipper, commodity, route → Task 4 ✓
- Waybill EMPTY: FOR LOADING header, from/to/shipper/spot fields, instruction text → Task 4 ✓
- Waybill DEADHEAD/MOW/HOLD/BAD ORDER: ruled field layout → Task 4 ✓
- All waybills Times fonts, 5pt ALL CAPS labels, 8–9pt Times-Bold values → Task 4 ✓
- `data/railroads.yaml` with PRR entry → Task 1 ✓
- `data/waybills.yaml` updated with `originating_railroad_id` → Task 2 ✓
- Validate command includes railroads → Task 3 ✓

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" references. All steps include complete code.

**Type consistency:**
- `Railroad` imported from `waybill_generator.models.railroad` throughout ✓
- `draw_card(canvas, car, waybill, railroad, x, y)` — consistent across BaseLayout, StandardPrrLayout (inherits), and renderer call ✓
- `draw_origination_section(canvas, railroad, waybill, x, y, w, h)` — waybill is second param after railroad, consistent with abstract definition ✓
- `render_pdf(triples, layout, output_path)` — `triples: list[tuple[Car, WaybillBase, Railroad]]` consistent in renderer and test ✓
- `_BILL_TYPE_LABELS[waybill.waybill_type]` — uses `WaybillType` enum keys matching all 6 waybill types ✓
