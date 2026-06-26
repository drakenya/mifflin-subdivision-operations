# Waybill Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a Python CLI tool that generates printable PRR car card + waybill PDFs from YAML data files and a session file.

**Architecture:** Data models (Pydantic) → YAML repository → Layout strategy (ReportLab) → Renderer (tiles 9 cards/page) → Click CLI. The CLI reads a session file listing `(car_id, waybill_id)` pairs, fetches records from YAML files, and renders a PDF. All layers are behind interfaces so backends and layouts are swappable.

**Tech Stack:** Python 3.11+, Pydantic v2, ReportLab, PyYAML, Click, tomllib (stdlib), pytest, ruff

## Global Constraints

- Python 3.11+ required (uses `tomllib` from stdlib, `match` statements)
- Pydantic v2 — use `model_config`, `TypeAdapter`, not v1 `Config` class
- ReportLab coordinate system: origin bottom-left, units in points (1 pt = 1/72 inch)
- Card size: 2.5" × 3.5" = 180pt × 252pt
- Page: 8.5" × 11" portrait = 612pt × 792pt, 9 cards per page (3×3)
- Gutter: 1/8" = 9pt between all card slots (including page edges)
- Content inset: 4pt from cut line on all sides
- Car `id` convention: `"{road}-{car_number}"`, e.g. `"PRR-12345"`
- No mocking of filesystem in tests — use `tmp_path` and real file I/O
- All tests in `tests/` directory, mirroring source structure

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Build config, dependencies, CLI entry point |
| `waybill.toml` | Run-time defaults |
| `CLAUDE.md` | Project context for future Claude Code sessions |
| `README.md` | Setup and usage docs |
| `waybill_generator/__init__.py` | Package root |
| `waybill_generator/config.py` | Load `waybill.toml` → `Config` dataclass |
| `waybill_generator/cli.py` | Click entry point, all commands |
| `waybill_generator/models/car.py` | `Car` Pydantic model |
| `waybill_generator/models/location.py` | `Location`, `Industry` Pydantic models |
| `waybill_generator/models/commodity.py` | `Commodity` Pydantic model |
| `waybill_generator/models/waybill.py` | `WaybillBase` + 6 subtypes, `Waybill` discriminated union |
| `waybill_generator/repository/base.py` | `BaseRepository` abstract class |
| `waybill_generator/repository/yaml_repo.py` | `YamlRepository` — reads from YAML files |
| `waybill_generator/layouts/base.py` | `BaseLayout` abstract class |
| `waybill_generator/layouts/standard_prr.py` | `StandardPrrLayout` — PRR visual style |
| `waybill_generator/renderer/pdf.py` | `render_pdf()` — tiles cards onto pages |
| `data/cars.yaml` | Sample car records |
| `data/locations.yaml` | Sample location + industry records |
| `data/commodities.yaml` | Sample commodity records |
| `data/waybills.yaml` | Sample waybill records |
| `tests/test_config.py` | Config loading tests |
| `tests/test_models.py` | Pydantic model tests |
| `tests/test_repository.py` | YamlRepository tests |
| `tests/test_layouts.py` | Layout smoke tests |
| `tests/test_renderer.py` | Renderer output tests |
| `tests/test_cli.py` | CLI command tests |
| `tests/fixtures/` | YAML fixture files for tests |

---

## Task 1: Project Scaffolding + Config

**Files:**
- Create: `pyproject.toml`
- Create: `waybill.toml`
- Create: `CLAUDE.md`
- Create: `README.md`
- Create: `waybill_generator/__init__.py` (empty)
- Create: `waybill_generator/models/__init__.py` (empty)
- Create: `waybill_generator/repository/__init__.py` (empty)
- Create: `waybill_generator/layouts/__init__.py` (empty)
- Create: `waybill_generator/renderer/__init__.py` (empty)
- Create: `waybill_generator/cli.py` (stub)
- Create: `waybill_generator/config.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_config.py`
- Create: `data/.gitkeep`
- Create: `output/.gitkeep`

**Interfaces:**
- Produces: `Config` dataclass with fields `layout: str`, `data_source: str`, `data_path: str`, `output_dir: str`
- Produces: `load_config(config_path) -> Config` in `waybill_generator.config`
- Produces: `waybill` CLI entry point (stub)

- [ ] **Step 1: Write `tests/test_config.py` (failing)**

```python
# tests/test_config.py
import tomllib
from pathlib import Path
from waybill_generator.config import Config, load_config


def test_load_config_defaults_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.layout == "standard_prr"
    assert cfg.data_source == "yaml"
    assert cfg.data_path == "./data"
    assert cfg.output_dir == "./output"


def test_load_config_from_toml(tmp_path):
    toml_file = tmp_path / "waybill.toml"
    toml_file.write_text(
        '[defaults]\nlayout = "custom"\ndata_path = "/my/data"\n'
    )
    cfg = load_config(toml_file)
    assert cfg.layout == "custom"
    assert cfg.data_path == "/my/data"
    assert cfg.output_dir == "./output"  # not in file, uses default


def test_load_config_ignores_unknown_keys(tmp_path):
    toml_file = tmp_path / "waybill.toml"
    toml_file.write_text('[defaults]\nunknown_key = "value"\nlayout = "standard_prr"\n')
    cfg = load_config(toml_file)
    assert cfg.layout == "standard_prr"
```

- [ ] **Step 2: Create the package structure**

```bash
mkdir -p waybill_generator/models waybill_generator/repository \
         waybill_generator/layouts waybill_generator/renderer \
         tests/fixtures data output
touch waybill_generator/__init__.py \
      waybill_generator/models/__init__.py \
      waybill_generator/repository/__init__.py \
      waybill_generator/layouts/__init__.py \
      waybill_generator/renderer/__init__.py \
      tests/__init__.py \
      data/.gitkeep output/.gitkeep
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "waybill-generator"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8",
    "pydantic>=2",
    "reportlab>=4",
    "pyyaml>=6",
]

[project.scripts]
waybill = "waybill_generator.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 4: Write `waybill_generator/config.py`**

```python
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    layout: str = "standard_prr"
    data_source: str = "yaml"
    data_path: str = "./data"
    output_dir: str = "./output"


_FIELDS = {f for f in Config.__dataclass_fields__}


def load_config(config_path: str | Path = "waybill.toml") -> Config:
    path = Path(config_path)
    if not path.exists():
        return Config()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    defaults = {k: v for k, v in data.get("defaults", {}).items() if k in _FIELDS}
    return Config(**defaults)
```

- [ ] **Step 5: Write stub `waybill_generator/cli.py`**

```python
import click


@click.group()
def main():
    pass
```

- [ ] **Step 6: Write `waybill.toml`**

```toml
[defaults]
layout = "standard_prr"
data_source = "yaml"
data_path = "./data"
output_dir = "./output"
```

- [ ] **Step 7: Write `CLAUDE.md`**

```markdown
# Mifflin Subdivision Operations — Waybill Generator

## Project Purpose
Python CLI tool generating printable PRR car card + waybill PDFs for model
railroad operations. Output is 2.5"×3.5" cards (9 per 8.5×11 page) cut
apart after printing. Each card: car identity on top (~1/3), waybill routing
on bottom (~2/3).

## Prototype
Pennsylvania Railroad, 1930s–1960s transition era. Accuracy-first, adjusted
for operational usability.

## Architecture
```
YAML files → YamlRepository → (Car, Waybill) pairs → StandardPrrLayout
→ render_pdf() → PDF output
```
- **Data:** `data/*.yaml` — cars, locations, commodities, waybills
- **Session file:** ephemeral YAML listing `(car_id, waybill_id)` pairs for a print job
- **Repository:** pluggable interface; YAML is the default backend
- **Layout:** Strategy pattern; `StandardPrrLayout` is the default
- **Renderer:** tiles cards 3×3 on portrait 8.5×11 pages with crop marks

## Waybill Types
LOADED, EMPTY, DEADHEAD, MOW, HOLD, BAD_ORDER

## Key Commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
waybill validate                         # check data files
waybill generate --session session.yaml  # produce PDF
waybill list cars
waybill list waybills [--type LOADED]
```

## Design Decisions
- YAML first; SQLite backend planned once schema stabilises
- No static assignments — session file is the mapping for each print job
- Car id convention: `{road}-{car_number}` e.g. `PRR-12345`
- Python 3.11+; Pydantic v2; ReportLab for PDF; Click for CLI
- Spec: `docs/superpowers/specs/2026-06-26-waybill-generator-design.md`
```

- [ ] **Step 8: Write `README.md`**

```markdown
# Waybill Generator

Generates printable car card + waybill PDFs for PRR model railroad operations.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
waybill --help
```

## Data Files

Edit files in `data/` to define your roster:

- `data/cars.yaml` — your car fleet
- `data/locations.yaml` — layout locations and industries
- `data/commodities.yaml` — freight types
- `data/waybills.yaml` — waybill definitions

## Printing Cards

1. Create a session file listing which car gets which waybill:

```yaml
# session.yaml
cards:
  - car: PRR-12345
    waybill: waybill-1
  - car: PRR-67890
    waybill: empty-1
```

2. Generate the PDF:

```bash
waybill generate --session session.yaml
```

Output lands in `./output/waybills-YYYY-MM-DD.pdf`. Print portrait,
cut on crop marks. Each page holds 9 cards (3×3).

## Validation

```bash
waybill validate
```

Reports any schema errors in your data files before you try to print.

## Development

```bash
pytest              # run tests
ruff check .        # lint
```
```

- [ ] **Step 9: Install the package**

```bash
pip install -e ".[dev]"
```

Expected output: `Successfully installed waybill-generator-0.1.0 ...`

- [ ] **Step 10: Run failing tests**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError` or similar (config.py exists but tests
may fail if there's an import issue; verify they fail for the right reason).

- [ ] **Step 11: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 12: Verify CLI entry point**

```bash
waybill --help
```

Expected: Shows `Usage: waybill [OPTIONS] COMMAND [ARGS]...`

- [ ] **Step 13: Commit**

```bash
git add pyproject.toml waybill.toml CLAUDE.md README.md \
        waybill_generator/ tests/test_config.py data/.gitkeep output/.gitkeep
git commit -m "feat: project scaffolding, config loader, stub CLI"
```

---

## Task 2: Data Models

**Files:**
- Create: `waybill_generator/models/car.py`
- Create: `waybill_generator/models/location.py`
- Create: `waybill_generator/models/commodity.py`
- Create: `waybill_generator/models/waybill.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing (pure Pydantic models)
- Produces:
  - `Car` from `waybill_generator.models.car`
  - `Location`, `Industry` from `waybill_generator.models.location`
  - `Commodity` from `waybill_generator.models.commodity`
  - `WaybillBase`, `LoadedWaybill`, `EmptyWaybill`, `DeadheadWaybill`, `MoWWaybill`, `HoldWaybill`, `BadOrderWaybill`, `WaybillType`, `Waybill` (TypeAlias) from `waybill_generator.models.waybill`

- [ ] **Step 1: Write `tests/test_models.py` (failing)**

```python
# tests/test_models.py
import pytest
from pydantic import ValidationError, TypeAdapter
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location, Industry
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import (
    WaybillType, LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill, Waybill,
)

_waybill_adapter = TypeAdapter(Waybill)


class TestCar:
    def test_basic_construction(self):
        car = Car(
            id="PRR-12345", road="PRR", car_number="12345",
            car_type="X29", aar_code="XM", capacity_tons=50,
        )
        assert car.id == "PRR-12345"
        assert car.active is True
        assert car.capacity_cuft is None

    def test_inactive_car(self):
        car = Car(
            id="NYC-99", road="NYC", car_number="99",
            car_type="H21a", aar_code="HM", capacity_tons=70,
            active=False,
        )
        assert car.active is False

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            Car(id="PRR-1", road="PRR", car_number="1", car_type="X29")


class TestLocation:
    def test_location_with_industries(self):
        loc = Location(
            id="LEW", name="Lewistown", subdivision="Mifflin",
            industries=[
                Industry(
                    id="LEW-GRAIN", name="Grain Elevator", location_id="LEW",
                    ships=["grain"],
                )
            ],
        )
        assert len(loc.industries) == 1
        assert loc.industries[0].ships == ["grain"]

    def test_location_defaults(self):
        loc = Location(id="ALT", name="Altoona")
        assert loc.industries == []
        assert loc.subdivision is None


class TestCommodity:
    def test_basic_construction(self):
        c = Commodity(id="grain", name="Grain", acceptable_car_types=["XM"])
        assert c.aar_code is None
        assert c.acceptable_car_types == ["XM"]


class TestWaybillDiscrimination:
    def test_loaded_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "w-1", "waybill_type": "LOADED",
            "commodity_id": "grain", "shipper_id": "LEW-GRAIN",
            "consignee_id": "ALT-MILL",
        })
        assert isinstance(w, LoadedWaybill)
        assert w.routing == []

    def test_empty_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "e-1", "waybill_type": "EMPTY",
            "from_location_id": "ALT", "to_location_id": "LEW",
        })
        assert isinstance(w, EmptyWaybill)

    def test_deadhead_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "d-1", "waybill_type": "DEADHEAD",
            "from_location_id": "PHL", "to_location_id": "PGH",
            "consist_note": "PRR 4100",
        })
        assert isinstance(w, DeadheadWaybill)

    def test_mow_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "m-1", "waybill_type": "MOW",
            "commodity_desc": "Ballast", "from_location_id": "ALT",
            "to_location_id": "LEW",
        })
        assert isinstance(w, MoWWaybill)

    def test_hold_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "h-1", "waybill_type": "HOLD",
            "industry_id": "LEW-GRAIN", "waiting_for": "Load order",
        })
        assert isinstance(w, HoldWaybill)

    def test_bad_order_waybill(self):
        w = _waybill_adapter.validate_python({
            "id": "b-1", "waybill_type": "BAD_ORDER",
            "from_location_id": "LEW", "shop_location_id": "ALT",
        })
        assert isinstance(w, BadOrderWaybill)
        assert w.defect is None

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            _waybill_adapter.validate_python({
                "id": "x-1", "waybill_type": "UNKNOWN",
            })
```

- [ ] **Step 2: Run tests to see them fail**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `waybill_generator/models/car.py`**

```python
from pydantic import BaseModel


class Car(BaseModel):
    id: str
    road: str
    car_number: str
    car_type: str
    aar_code: str
    capacity_tons: int
    capacity_cuft: int | None = None
    length_ft: int | None = None
    active: bool = True
    notes: str | None = None
```

- [ ] **Step 4: Write `waybill_generator/models/location.py`**

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
    subdivision: str | None = None
    industries: list[Industry] = []
```

- [ ] **Step 5: Write `waybill_generator/models/commodity.py`**

```python
from pydantic import BaseModel


class Commodity(BaseModel):
    id: str
    name: str
    aar_code: str | None = None
    acceptable_car_types: list[str] = []
```

- [ ] **Step 6: Write `waybill_generator/models/waybill.py`**

```python
from enum import Enum
from typing import Annotated, Union
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
    notes: str | None = None


class LoadedWaybill(WaybillBase):
    waybill_type: WaybillType = WaybillType.LOADED
    commodity_id: str
    shipper_id: str
    consignee_id: str
    routing: list[str] = []


class EmptyWaybill(WaybillBase):
    waybill_type: WaybillType = WaybillType.EMPTY
    from_location_id: str
    to_location_id: str


class DeadheadWaybill(WaybillBase):
    waybill_type: WaybillType = WaybillType.DEADHEAD
    from_location_id: str
    to_location_id: str
    consist_note: str | None = None


class MoWWaybill(WaybillBase):
    waybill_type: WaybillType = WaybillType.MOW
    commodity_desc: str
    from_location_id: str
    to_location_id: str
    project: str | None = None


class HoldWaybill(WaybillBase):
    waybill_type: WaybillType = WaybillType.HOLD
    industry_id: str
    waiting_for: str


class BadOrderWaybill(WaybillBase):
    waybill_type: WaybillType = WaybillType.BAD_ORDER
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

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 11 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add waybill_generator/models/ tests/test_models.py
git commit -m "feat: Pydantic data models for car, location, commodity, waybill"
```

---

## Task 3: YAML Repository + Sample Data

**Files:**
- Create: `waybill_generator/repository/base.py`
- Create: `waybill_generator/repository/yaml_repo.py`
- Create: `data/cars.yaml`
- Create: `data/locations.yaml`
- Create: `data/commodities.yaml`
- Create: `data/waybills.yaml`
- Create: `tests/fixtures/cars.yaml`
- Create: `tests/fixtures/locations.yaml`
- Create: `tests/fixtures/commodities.yaml`
- Create: `tests/fixtures/waybills.yaml`
- Create: `tests/test_repository.py`

**Interfaces:**
- Consumes: `Car`, `Location`, `Industry`, `Commodity`, `WaybillBase`, `Waybill`, `WaybillType`
- Produces:
  - `BaseRepository` from `waybill_generator.repository.base`
  - `YamlRepository(data_path: str | Path)` from `waybill_generator.repository.yaml_repo`
    - `.get_cars() -> list[Car]`
    - `.get_car(id: str) -> Car` — raises `KeyError` if not found
    - `.get_locations() -> list[Location]`
    - `.get_location(id: str) -> Location`
    - `.get_commodities() -> list[Commodity]`
    - `.get_commodity(id: str) -> Commodity`
    - `.get_waybills() -> list[WaybillBase]`
    - `.get_waybill(id: str) -> WaybillBase`

- [ ] **Step 1: Write fixture YAML files**

`tests/fixtures/cars.yaml`:
```yaml
- id: PRR-12345
  road: PRR
  car_number: "12345"
  car_type: X29
  aar_code: XM
  capacity_tons: 50
  capacity_cuft: 3020
  length_ft: 40
  active: true

- id: PRR-67890
  road: PRR
  car_number: "67890"
  car_type: H21a
  aar_code: HM
  capacity_tons: 70
  active: false
```

`tests/fixtures/locations.yaml`:
```yaml
- id: LEW
  name: Lewistown
  subdivision: Mifflin
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
  subdivision: Middle
  industries:
    - id: ALT-SHOP
      name: Altoona Shops
      location_id: ALT
      track: shop
      car_capacity: 10
      ships: []
      receives: []
```

`tests/fixtures/commodities.yaml`:
```yaml
- id: grain
  name: Grain
  aar_code: "01110"
  acceptable_car_types:
    - XM

- id: coal
  name: Bituminous Coal
  aar_code: "01210"
  acceptable_car_types:
    - HM
    - GB
```

`tests/fixtures/waybills.yaml`:
```yaml
- id: waybill-1
  waybill_type: LOADED
  commodity_id: grain
  shipper_id: LEW-GRAIN
  consignee_id: ALT-SHOP

- id: empty-1
  waybill_type: EMPTY
  from_location_id: ALT
  to_location_id: LEW

- id: badorder-1
  waybill_type: BAD_ORDER
  from_location_id: LEW
  shop_location_id: ALT
  defect: Broken coupler
```

- [ ] **Step 2: Write `tests/test_repository.py` (failing)**

```python
# tests/test_repository.py
import pytest
from pathlib import Path
from waybill_generator.repository.yaml_repo import YamlRepository
from waybill_generator.models.waybill import LoadedWaybill, EmptyWaybill, BadOrderWaybill

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo():
    return YamlRepository(FIXTURES)


class TestYamlRepositoryCars:
    def test_get_cars_returns_all(self, repo):
        cars = repo.get_cars()
        assert len(cars) == 2

    def test_get_car_by_id(self, repo):
        car = repo.get_car("PRR-12345")
        assert car.road == "PRR"
        assert car.car_type == "X29"
        assert car.capacity_tons == 50

    def test_get_car_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_car("MISSING-0")

    def test_inactive_car_included(self, repo):
        car = repo.get_car("PRR-67890")
        assert car.active is False


class TestYamlRepositoryLocations:
    def test_get_locations_returns_all(self, repo):
        locs = repo.get_locations()
        assert len(locs) == 2

    def test_get_location_with_industries(self, repo):
        loc = repo.get_location("LEW")
        assert loc.name == "Lewistown"
        assert len(loc.industries) == 1
        assert loc.industries[0].id == "LEW-GRAIN"

    def test_get_location_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_location("MISSING")


class TestYamlRepositoryCommodities:
    def test_get_commodities(self, repo):
        commodities = repo.get_commodities()
        assert len(commodities) == 2

    def test_get_commodity_by_id(self, repo):
        c = repo.get_commodity("grain")
        assert c.name == "Grain"


class TestYamlRepositoryWaybills:
    def test_get_waybills_returns_all(self, repo):
        waybills = repo.get_waybills()
        assert len(waybills) == 3

    def test_loaded_waybill_deserialized(self, repo):
        w = repo.get_waybill("waybill-1")
        assert isinstance(w, LoadedWaybill)
        assert w.commodity_id == "grain"

    def test_empty_waybill_deserialized(self, repo):
        w = repo.get_waybill("empty-1")
        assert isinstance(w, EmptyWaybill)

    def test_bad_order_waybill_deserialized(self, repo):
        w = repo.get_waybill("badorder-1")
        assert isinstance(w, BadOrderWaybill)
        assert w.defect == "Broken coupler"

    def test_get_waybill_missing_raises(self, repo):
        with pytest.raises(KeyError):
            repo.get_waybill("MISSING")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_repository.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write `waybill_generator/repository/base.py`**

```python
from abc import ABC, abstractmethod
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import WaybillBase


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
```

- [ ] **Step 5: Write `waybill_generator/repository/yaml_repo.py`**

```python
from pathlib import Path
import yaml
from pydantic import TypeAdapter
from waybill_generator.repository.base import BaseRepository
from waybill_generator.models.car import Car
from waybill_generator.models.location import Location
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.waybill import WaybillBase, Waybill

_waybill_adapter = TypeAdapter(Waybill)


class YamlRepository(BaseRepository):
    def __init__(self, data_path: str | Path) -> None:
        self._path = Path(data_path)
        self._cars: dict[str, Car] | None = None
        self._locations: dict[str, Location] | None = None
        self._commodities: dict[str, Commodity] | None = None
        self._waybills: dict[str, WaybillBase] | None = None

    def _load(self, filename: str) -> list[dict]:
        return yaml.safe_load((self._path / filename).read_text()) or []

    def _ensure_cars(self) -> dict[str, Car]:
        if self._cars is None:
            self._cars = {c.id: c for c in [Car(**r) for r in self._load("cars.yaml")]}
        return self._cars

    def _ensure_locations(self) -> dict[str, Location]:
        if self._locations is None:
            self._locations = {
                loc.id: loc for loc in [Location(**r) for r in self._load("locations.yaml")]
            }
        return self._locations

    def _ensure_commodities(self) -> dict[str, Commodity]:
        if self._commodities is None:
            self._commodities = {
                c.id: c for c in [Commodity(**r) for r in self._load("commodities.yaml")]
            }
        return self._commodities

    def _ensure_waybills(self) -> dict[str, WaybillBase]:
        if self._waybills is None:
            self._waybills = {
                w.id: w
                for w in [_waybill_adapter.validate_python(r) for r in self._load("waybills.yaml")]
            }
        return self._waybills

    def get_cars(self) -> list[Car]:
        return list(self._ensure_cars().values())

    def get_car(self, id: str) -> Car:
        cars = self._ensure_cars()
        if id not in cars:
            raise KeyError(f"Car not found: {id!r}")
        return cars[id]

    def get_locations(self) -> list[Location]:
        return list(self._ensure_locations().values())

    def get_location(self, id: str) -> Location:
        locs = self._ensure_locations()
        if id not in locs:
            raise KeyError(f"Location not found: {id!r}")
        return locs[id]

    def get_commodities(self) -> list[Commodity]:
        return list(self._ensure_commodities().values())

    def get_commodity(self, id: str) -> Commodity:
        commodities = self._ensure_commodities()
        if id not in commodities:
            raise KeyError(f"Commodity not found: {id!r}")
        return commodities[id]

    def get_waybills(self) -> list[WaybillBase]:
        return list(self._ensure_waybills().values())

    def get_waybill(self, id: str) -> WaybillBase:
        waybills = self._ensure_waybills()
        if id not in waybills:
            raise KeyError(f"Waybill not found: {id!r}")
        return waybills[id]
```

- [ ] **Step 6: Write sample `data/` YAML files**

`data/cars.yaml`:
```yaml
- id: PRR-12345
  road: PRR
  car_number: "12345"
  car_type: X29
  aar_code: XM
  capacity_tons: 50
  capacity_cuft: 3020
  length_ft: 40
  active: true
  notes: null

- id: PRR-67890
  road: PRR
  car_number: "67890"
  car_type: H21a
  aar_code: HM
  capacity_tons: 70
  active: true
```

`data/locations.yaml`:
```yaml
- id: LEW
  name: Lewistown
  subdivision: Mifflin
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
  subdivision: Middle
  industries:
    - id: ALT-SHOP
      name: Altoona Shops
      location_id: ALT
      track: shop
      car_capacity: 10
      ships: []
      receives: []

- id: PGH
  name: Pittsburgh
  subdivision: Pittsburgh
  industries: []
```

`data/commodities.yaml`:
```yaml
- id: grain
  name: Grain
  aar_code: "01110"
  acceptable_car_types:
    - XM

- id: coal
  name: Bituminous Coal
  aar_code: "01210"
  acceptable_car_types:
    - HM
    - GB

- id: steel
  name: Steel
  acceptable_car_types:
    - FM
    - FL
```

`data/waybills.yaml`:
```yaml
- id: waybill-1
  waybill_type: LOADED
  commodity_id: grain
  shipper_id: LEW-GRAIN
  consignee_id: ALT-SHOP

- id: empty-1
  waybill_type: EMPTY
  from_location_id: ALT
  to_location_id: LEW

- id: deadhead-1
  waybill_type: DEADHEAD
  from_location_id: PGH
  to_location_id: ALT
  consist_note: PRR 4100 combine

- id: mow-1
  waybill_type: MOW
  commodity_desc: Ballast
  from_location_id: ALT
  to_location_id: LEW
  project: Track resurfacing MP 152-160

- id: hold-1
  waybill_type: HOLD
  industry_id: LEW-GRAIN
  waiting_for: Load order from elevator

- id: badorder-1
  waybill_type: BAD_ORDER
  from_location_id: LEW
  shop_location_id: ALT
  defect: Broken coupler knuckle
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_repository.py -v
```

Expected: 13 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add waybill_generator/repository/ data/ tests/test_repository.py tests/fixtures/
git commit -m "feat: YAML repository and sample data files"
```

---

## Task 4: Layout System

**Files:**
- Create: `waybill_generator/layouts/base.py`
- Create: `waybill_generator/layouts/standard_prr.py`
- Create: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `Car`, `WaybillBase`, `WaybillType`, all waybill subclasses
- Produces:
  - `BaseLayout` from `waybill_generator.layouts.base`
    - Class attributes: `card_width_pt=180.0`, `card_height_pt=252.0`, `car_section_fraction=0.33`, `gutter_pt=9.0`, `content_inset_pt=4.0`
    - `draw_card(canvas, car: Car, waybill: WaybillBase, x: float, y: float) -> None` (concrete)
    - `draw_car_section(canvas, car, x, y, w, h) -> None` (abstract)
    - `draw_waybill_section(canvas, waybill, x, y, w, h) -> None` (abstract)
  - `StandardPrrLayout(BaseLayout)` from `waybill_generator.layouts.standard_prr`

- [ ] **Step 1: Write `tests/test_layouts.py` (failing)**

```python
# tests/test_layouts.py
import io
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import (
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

CAR = Car(
    id="PRR-12345", road="PRR", car_number="12345",
    car_type="X29", aar_code="XM", capacity_tons=50,
)

WAYBILLS = [
    LoadedWaybill(id="w-1", commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP"),
    EmptyWaybill(id="e-1", from_location_id="ALT", to_location_id="LEW"),
    DeadheadWaybill(id="d-1", from_location_id="PHL", to_location_id="PGH"),
    MoWWaybill(id="m-1", commodity_desc="Ballast", from_location_id="ALT", to_location_id="LEW"),
    HoldWaybill(id="h-1", industry_id="LEW-GRAIN", waiting_for="Load order"),
    BadOrderWaybill(id="b-1", from_location_id="LEW", shop_location_id="ALT"),
]


def _make_canvas():
    buf = io.BytesIO()
    return Canvas(buf, pagesize=letter)


def test_layout_constants():
    layout = StandardPrrLayout()
    assert layout.card_width_pt == 180.0
    assert layout.card_height_pt == 252.0
    assert layout.gutter_pt == 9.0
    assert layout.content_inset_pt == 4.0


def test_draw_card_all_waybill_types():
    layout = StandardPrrLayout()
    for waybill in WAYBILLS:
        canvas = _make_canvas()
        layout.draw_card(canvas, CAR, waybill, x=0, y=0)
        canvas.save()  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_layouts.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `waybill_generator/layouts/base.py`**

```python
from abc import ABC, abstractmethod
from reportlab.pdfgen.canvas import Canvas
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import WaybillBase


class BaseLayout(ABC):
    card_width_pt: float = 180.0
    card_height_pt: float = 252.0
    car_section_fraction: float = 0.33
    gutter_pt: float = 9.0
    content_inset_pt: float = 4.0

    def draw_card(
        self, canvas: Canvas, car: Car, waybill: WaybillBase, x: float, y: float
    ) -> None:
        w = self.card_width_pt
        h = self.card_height_pt
        inset = self.content_inset_pt
        car_h = h * self.car_section_fraction
        waybill_h = h - car_h

        self.draw_car_section(canvas, car, x + inset, y + waybill_h, w - 2 * inset, car_h - inset)
        self.draw_waybill_section(canvas, waybill, x + inset, y + inset, w - 2 * inset, waybill_h - inset)

    @abstractmethod
    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None: ...

    @abstractmethod
    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None: ...
```

- [ ] **Step 4: Write `waybill_generator/layouts/standard_prr.py`**

```python
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black, HexColor
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import (
    WaybillBase, WaybillType,
    LoadedWaybill, EmptyWaybill, DeadheadWaybill,
    MoWWaybill, HoldWaybill, BadOrderWaybill,
)

_PRR_TUSCAN = HexColor("#7B1113")
_LIGHT_GRAY = HexColor("#EEEEEE")


class StandardPrrLayout(BaseLayout):

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.setFillColor(_PRR_TUSCAN)
        canvas.rect(x, y, w, h, fill=1)

        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(x + 3, y + h - 11, car.road)

        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(x + w / 2, y + h - 11, car.car_type)
        canvas.drawRightString(x + w - 3, y + h - 11, car.car_number)

        canvas.setFont("Helvetica", 7)
        capacity = f"{car.capacity_tons}T"
        if car.capacity_cuft:
            capacity += f"  {car.capacity_cuft} cu ft"
        canvas.drawString(x + 3, y + 3, capacity)

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.setFillColor(black)
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

    def _label(self, canvas: Canvas, text: str, x: float, y: float, w: float) -> None:
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(HexColor("#666666"))
        canvas.drawString(x, y, text.upper())

    def _value(self, canvas: Canvas, text: str, x: float, y: float, size: int = 8) -> None:
        canvas.setFont("Helvetica-Bold", size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _type_badge(self, canvas: Canvas, text: str, x: float, y: float, w: float, color: HexColor) -> None:
        canvas.setFillColor(color)
        canvas.rect(x, y, w, 10, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawCentredString(x + w / 2, y + 2, text)

    def _draw_loaded(self, canvas: Canvas, w: LoadedWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "LOADED", x, y + h - 11, ww, _PRR_TUSCAN)
        self._label(canvas, "Commodity", x + 2, y + h - 22, ww)
        self._value(canvas, w.commodity_id, x + 2, y + h - 31)
        self._label(canvas, "From (Shipper)", x + 2, y + h - 44, ww)
        self._value(canvas, w.shipper_id, x + 2, y + h - 53)
        self._label(canvas, "To (Consignee)", x + 2, y + h - 66, ww)
        self._value(canvas, w.consignee_id, x + 2, y + h - 75)
        if w.routing:
            self._label(canvas, "Via", x + 2, y + h - 88, ww)
            self._value(canvas, " → ".join(w.routing), x + 2, y + h - 97, size=7)

    def _draw_empty(self, canvas: Canvas, w: EmptyWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "EMPTY", x, y + h - 11, ww, HexColor("#4A4A4A"))
        self._label(canvas, "From", x + 2, y + h - 22, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 31)
        self._label(canvas, "To", x + 2, y + h - 44, ww)
        self._value(canvas, w.to_location_id, x + 2, y + h - 53)

    def _draw_deadhead(self, canvas: Canvas, w: DeadheadWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "DEADHEAD", x, y + h - 11, ww, HexColor("#2B5EA7"))
        self._label(canvas, "From", x + 2, y + h - 22, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 31)
        self._label(canvas, "To", x + 2, y + h - 44, ww)
        self._value(canvas, w.to_location_id, x + 2, y + h - 53)
        if w.consist_note:
            self._label(canvas, "Consist", x + 2, y + h - 66, ww)
            self._value(canvas, w.consist_note, x + 2, y + h - 75, size=7)

    def _draw_mow(self, canvas: Canvas, w: MoWWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "M-O-W", x, y + h - 11, ww, HexColor("#5A7A2E"))
        self._label(canvas, "Material", x + 2, y + h - 22, ww)
        self._value(canvas, w.commodity_desc, x + 2, y + h - 31)
        self._label(canvas, "From", x + 2, y + h - 44, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 53)
        self._label(canvas, "To", x + 2, y + h - 66, ww)
        self._value(canvas, w.to_location_id, x + 2, y + h - 75)
        if w.project:
            self._label(canvas, "Project", x + 2, y + h - 88, ww)
            self._value(canvas, w.project, x + 2, y + h - 97, size=6)

    def _draw_hold(self, canvas: Canvas, w: HoldWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "HOLD", x, y + h - 11, ww, HexColor("#996633"))
        self._label(canvas, "Hold At", x + 2, y + h - 22, ww)
        self._value(canvas, w.industry_id, x + 2, y + h - 31)
        self._label(canvas, "Waiting For", x + 2, y + h - 44, ww)
        self._value(canvas, w.waiting_for, x + 2, y + h - 53, size=7)

    def _draw_bad_order(self, canvas: Canvas, w: BadOrderWaybill, x: float, y: float, ww: float, h: float) -> None:
        self._type_badge(canvas, "BAD ORDER", x, y + h - 11, ww, HexColor("#CC0000"))
        self._label(canvas, "From", x + 2, y + h - 22, ww)
        self._value(canvas, w.from_location_id, x + 2, y + h - 31)
        self._label(canvas, "Shop", x + 2, y + h - 44, ww)
        self._value(canvas, w.shop_location_id, x + 2, y + h - 53)
        if w.defect:
            self._label(canvas, "Defect", x + 2, y + h - 66, ww)
            self._value(canvas, w.defect, x + 2, y + h - 75, size=7)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_layouts.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/layouts/ tests/test_layouts.py
git commit -m "feat: BaseLayout and StandardPrrLayout with all waybill type renderers"
```

---

## Task 5: PDF Renderer

**Files:**
- Create: `waybill_generator/renderer/pdf.py`
- Create: `tests/test_renderer.py`

**Interfaces:**
- Consumes: `BaseLayout`, `Car`, `WaybillBase`
- Produces:
  - `render_pdf(pairs: list[tuple[Car, WaybillBase]], layout: BaseLayout, output_path: str | Path) -> None`
    from `waybill_generator.renderer.pdf`

- [ ] **Step 1: Write `tests/test_renderer.py` (failing)**

```python
# tests/test_renderer.py
from pathlib import Path
from waybill_generator.renderer.pdf import render_pdf
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import LoadedWaybill, EmptyWaybill

CAR_A = Car(id="PRR-1", road="PRR", car_number="1", car_type="X29", aar_code="XM", capacity_tons=50)
CAR_B = Car(id="PRR-2", road="PRR", car_number="2", car_type="H21a", aar_code="HM", capacity_tons=70)
LOADED = LoadedWaybill(id="w-1", commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP")
EMPTY = EmptyWaybill(id="e-1", from_location_id="ALT", to_location_id="LEW")


def test_render_creates_pdf(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED)], StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_pdf_header(tmp_path):
    out = tmp_path / "test.pdf"
    render_pdf([(CAR_A, LOADED)], StandardPrrLayout(), out)
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_multiple_pairs(tmp_path):
    out = tmp_path / "multi.pdf"
    pairs = [(CAR_A, LOADED), (CAR_B, EMPTY)] * 5  # 10 pairs = 2 pages
    render_pdf(pairs, StandardPrrLayout(), out)
    assert out.exists()
    assert out.stat().st_size > 1000


def test_render_empty_pairs(tmp_path):
    out = tmp_path / "empty.pdf"
    render_pdf([], StandardPrrLayout(), out)
    assert out.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_renderer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `waybill_generator/renderer/pdf.py`**

```python
from pathlib import Path
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.waybill import WaybillBase

_COLS = 3
_ROWS = 3
_PER_PAGE = _COLS * _ROWS
_PAGE_W, _PAGE_H = letter  # 612, 792


def render_pdf(
    pairs: list[tuple[Car, WaybillBase]],
    layout: BaseLayout,
    output_path: str | Path,
) -> None:
    canvas = Canvas(str(output_path), pagesize=letter)

    if not pairs:
        canvas.save()
        return

    g = layout.gutter_pt
    cw = layout.card_width_pt
    ch = layout.card_height_pt

    left_margin = (_PAGE_W - (_COLS * cw + (_COLS + 1) * g)) / 2
    bottom_margin = (_PAGE_H - (_ROWS * ch + (_ROWS + 1) * g)) / 2

    for page_idx, page_pairs in enumerate(_chunks(pairs, _PER_PAGE)):
        if page_idx > 0:
            canvas.showPage()

        for card_idx, (car, waybill) in enumerate(page_pairs):
            col = card_idx % _COLS
            row = card_idx // _COLS

            x = left_margin + g + col * (cw + g)
            y = _PAGE_H - bottom_margin - g - (row + 1) * ch - row * g

            layout.draw_card(canvas, car, waybill, x, y)
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

    # Bottom-left
    canvas.line(x - mark, y, x, y)
    canvas.line(x, y - mark, x, y)
    # Bottom-right
    canvas.line(x + w, y, x + w + mark, y)
    canvas.line(x + w, y - mark, x + w, y)
    # Top-left
    canvas.line(x - mark, y + h, x, y + h)
    canvas.line(x, y + h, x, y + h + mark)
    # Top-right
    canvas.line(x + w, y + h, x + w + mark, y + h)
    canvas.line(x + w, y + h, x + w, y + h + mark)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_renderer.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/renderer/ tests/test_renderer.py
git commit -m "feat: PDF renderer with page tiling and crop marks"
```

---

## Task 6: CLI Commands

**Files:**
- Modify: `waybill_generator/cli.py` (replace stub)
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Config`, `load_config`, `YamlRepository`, `StandardPrrLayout`, `render_pdf`, all models
- Produces: `waybill` CLI with commands `generate`, `list cars`, `list waybills`, `validate`

- [ ] **Step 1: Write `tests/test_cli.py` (failing)**

```python
# tests/test_cli.py
from pathlib import Path
from click.testing import CliRunner
from waybill_generator.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output


def test_validate_passes_with_valid_data():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "validate"])
    assert result.exit_code == 0
    assert "Cars: 2" in result.output
    assert "Waybills: 3" in result.output


def test_list_cars():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "list", "cars"])
    assert result.exit_code == 0
    assert "PRR-12345" in result.output
    assert "PRR-67890" in result.output


def test_list_waybills():
    runner = CliRunner()
    result = runner.invoke(main, ["--data-path", str(FIXTURES), "list", "waybills"])
    assert result.exit_code == 0
    assert "waybill-1" in result.output
    assert "LOADED" in result.output


def test_list_waybills_filtered_by_type():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--data-path", str(FIXTURES), "list", "waybills", "--type", "EMPTY"]
    )
    assert result.exit_code == 0
    assert "empty-1" in result.output
    assert "waybill-1" not in result.output


def test_generate_produces_pdf(tmp_path):
    session = tmp_path / "session.yaml"
    session.write_text(
        "cards:\n  - car: PRR-12345\n    waybill: waybill-1\n"
        "  - car: PRR-67890\n    waybill: empty-1\n"
    )
    out = tmp_path / "out.pdf"
    runner = CliRunner()
    result = runner.invoke(main, [
        "--data-path", str(FIXTURES),
        "generate",
        "--session", str(session),
        "--output", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL (stub CLI has no `generate`, `list`, or `validate` commands)

- [ ] **Step 3: Write `waybill_generator/cli.py`**

```python
from datetime import date
from pathlib import Path
import yaml
import click
from waybill_generator.config import load_config
from waybill_generator.repository.yaml_repo import YamlRepository
from waybill_generator.layouts.standard_prr import StandardPrrLayout
from waybill_generator.renderer.pdf import render_pdf

_LAYOUTS = {"standard_prr": StandardPrrLayout}


@click.group()
@click.option("--layout", default=None, help="Layout class name")
@click.option("--data-source", default=None, help="Data backend (yaml)")
@click.option("--data-path", default=None, help="Path to data directory")
@click.option("--output-dir", default=None, help="Directory for PDF output")
@click.pass_context
def main(ctx, layout, data_source, data_path, output_dir):
    cfg = load_config()
    ctx.ensure_object(dict)
    ctx.obj["layout"] = layout or cfg.layout
    ctx.obj["data_source"] = data_source or cfg.data_source
    ctx.obj["data_path"] = data_path or cfg.data_path
    ctx.obj["output_dir"] = output_dir or cfg.output_dir


def _get_repo(ctx):
    return YamlRepository(ctx.obj["data_path"])


@main.command()
@click.option("--session", required=True, type=click.Path(exists=True), help="Session YAML file")
@click.option("--output", default=None, help="Output PDF path")
@click.pass_context
def generate(ctx, session, output):
    """Generate a PDF from a session file."""
    session_data = yaml.safe_load(Path(session).read_text())
    repo = _get_repo(ctx)

    pairs = []
    for card in session_data.get("cards", []):
        car = repo.get_car(card["car"])
        waybill = repo.get_waybill(card["waybill"])
        pairs.append((car, waybill))

    layout_cls = _LAYOUTS.get(ctx.obj["layout"])
    if layout_cls is None:
        raise click.BadParameter(f"Unknown layout: {ctx.obj['layout']!r}")
    layout = layout_cls()

    if output is None:
        out_dir = Path(ctx.obj["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        output = str(out_dir / f"waybills-{date.today().isoformat()}.pdf")

    render_pdf(pairs, layout, output)
    click.echo(f"Generated: {output}")


@main.group("list")
def list_group():
    """List cars or waybills."""
    pass


@list_group.command("cars")
@click.pass_context
def list_cars(ctx):
    """List all cars in the roster."""
    repo = _get_repo(ctx)
    for car in repo.get_cars():
        status = "" if car.active else "  [inactive]"
        click.echo(f"{car.id:<20} {car.car_type}/{car.aar_code}  {car.capacity_tons}T{status}")


@list_group.command("waybills")
@click.option("--type", "waybill_type", default=None, help="Filter by type (LOADED, EMPTY, etc.)")
@click.pass_context
def list_waybills(ctx, waybill_type):
    """List all waybills, optionally filtered by type."""
    repo = _get_repo(ctx)
    waybills = repo.get_waybills()
    if waybill_type:
        waybills = [w for w in waybills if w.waybill_type.value == waybill_type.upper()]
    for w in waybills:
        click.echo(f"{w.id:<20} [{w.waybill_type.value}]")


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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cli.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Verify end-to-end manually**

```bash
waybill validate
```

Expected: `Cars: 2 loaded`, `Locations: 3 loaded`, `Commodities: 3 loaded`, `Waybills: 6 loaded`, `All data files valid.`

```bash
waybill list cars
waybill list waybills
```

```bash
cat > /tmp/session.yaml << 'EOF'
cards:
  - car: PRR-12345
    waybill: waybill-1
  - car: PRR-67890
    waybill: empty-1
  - car: PRR-12345
    waybill: badorder-1
EOF
waybill generate --session /tmp/session.yaml --output /tmp/test-waybills.pdf
```

Expected: `Generated: /tmp/test-waybills.pdf` — open the file and verify cards are visible with car info on top and waybill info below.

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/cli.py tests/test_cli.py
git commit -m "feat: complete CLI with generate, list, and validate commands"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Architecture ✓, waybill types (all 6) ✓, data model ✓, YAML data files ✓, session file ✓, repository interface ✓, layout system ✓, renderer + page layout ✓, CLI ✓, project structure ✓, CLAUDE.md ✓, README ✓
- [x] **No placeholders:** All steps contain actual code; no TBDs
- [x] **Type consistency:** `Car`, `WaybillBase`, `Waybill`, `BaseLayout`, `YamlRepository`, `render_pdf`, `Config`, `load_config` names are consistent across all tasks
- [x] **SqliteRepository** — out of scope for this plan per spec decision; noted in CLAUDE.md as planned
- [x] **`output/.gitkeep`** — created in Task 1 so the output dir exists in repo
