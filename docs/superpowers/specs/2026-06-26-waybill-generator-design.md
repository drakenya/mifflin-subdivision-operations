# Waybill Generator — Design Spec

**Date:** 2026-06-26
**Project:** mifflin-subdivision-operations
**Status:** Approved

---

## Overview

A Python CLI tool that generates printable car card + waybill PDFs for model railroad operations. Output is baseball-card-sized cards (2.5" × 3.5"), 9 per 8.5×11 portrait page, cut apart after printing. Each card combines the car's identity (top ~1/3) with its current routing instruction (bottom ~2/3) on a single physical card that is swapped out when assignments change.

**Prototype:** Pennsylvania Railroad, 1930s–1960s (transition era). Accuracy-first, adjusted for operational usability.

---

## Waybill Types

Six types supported, each with distinct fields and card rendering:

| Type | Description |
|---|---|
| `LOADED` | Standard freight move: commodity, shipper → consignee |
| `EMPTY` | Empty car repositioning: from → to |
| `DEADHEAD` | Passenger/MU equipment move: from → to, consist note |
| `MOW` | Maintenance-of-way / company service car |
| `HOLD` | Car sitting at industry waiting for load |
| `BAD_ORDER` | Car to/from repair shop |

System is designed to be extensible — adding a new type means a new Pydantic subclass and a new render method in the layout.

---

## Data Model

All models defined as **Pydantic v2** classes. Schema is expected to evolve; optional fields with defaults keep existing YAML files valid as fields are added.

### Car
```python
id: str                # unique key, convention: "{road}-{car_number}", e.g. "PRR-12345"
road: str              # reporting marks, e.g. "PRR", "NYC", "B&O"
car_number: str        # e.g. "12345"
car_type: str          # PRR classification, e.g. "X29", "H21a", "G28"
aar_code: str          # AAR type code, e.g. "XM", "HM", "GB"
capacity_tons: int
capacity_cuft: int | None = None
length_ft: int | None = None
active: bool = True    # False = excluded from print runs
notes: str | None = None
```

### Location
```python
id: str                # short code, e.g. "LEW" for Lewistown
name: str
subdivision: str | None = None
industries: list[Industry] = []
```

### Industry
```python
id: str
name: str
location_id: str
track: str | None = None
car_capacity: int | None = None
ships: list[str] = []      # commodity ids
receives: list[str] = []
```

### Commodity
```python
id: str
name: str
aar_code: str | None = None
acceptable_car_types: list[str] = []   # aar_codes
```

### Waybill (base + subtypes)

Base fields on all waybills:
```python
id: str
waybill_type: WaybillType   # discriminator
notes: str | None = None
```

Subtype extra fields:

- **LoadedWaybill:** `commodity_id`, `shipper_id` (Industry), `consignee_id` (Industry), `routing: list[str]` (optional location ids)
- **EmptyWaybill:** `from_location_id`, `to_location_id`
- **DeadheadWaybill:** `from_location_id`, `to_location_id`, `consist_note: str | None`
- **MoWWaybill:** `commodity_desc: str`, `from_location_id`, `to_location_id`, `project: str | None`
- **HoldWaybill:** `industry_id`, `waiting_for: str`
- **BadOrderWaybill:** `from_location_id`, `shop_location_id`, `defect: str | None`

Waybills are **not** linked to specific cars in the data files. The session file provides the car→waybill mapping at print time.

---

## Data Files (YAML)

```
data/
  cars.yaml          # list of Car records
  locations.yaml     # list of Location records (with nested Industries)
  commodities.yaml   # list of Commodity records
  waybills.yaml      # list of Waybill records (all types, discriminated by waybill_type)
```

No permanent assignment file. Assignments are ephemeral, provided via session file at print time.

---

## Session File

A lightweight YAML file created per print job:

```yaml
# session.yaml
cards:
  - car: PRR-123
    waybill: waybill-1
  - car: PRR-123
    waybill: empty-4       # second option for same car — both get printed
  - car: PRR-456
    waybill: coal-to-pgh
```

Cars and waybills are matched by their `id` fields. A car can appear multiple times with different waybills to print options. The session file can be saved for reprints or discarded after use.

---

## Repository Layer

Abstract interface decouples data access from business logic:

```python
class BaseRepository(ABC):
    def get_cars(self) -> list[Car]: ...
    def get_car(self, id: str) -> Car: ...
    def get_locations(self) -> list[Location]: ...
    def get_location(self, id: str) -> Location: ...
    def get_commodities(self) -> list[Commodity]: ...
    def get_commodity(self, id: str) -> Commodity: ...
    def get_waybills(self) -> list[Waybill]: ...
    def get_waybill(self, id: str) -> Waybill: ...
```

Concrete implementations:
- **`YamlRepository`** — reads from a directory of YAML files (default, used during schema iteration)
- **`SqliteRepository`** — reads from a SQLite database (for later, once schema stabilizes)
- Future: spreadsheet connector (OneDrive/Excel)

Switching backends is a config change, not a code change.

---

## Layout System

Card rendering uses a **Strategy pattern**. Each layout is a class that knows how to draw one card.

```python
class BaseLayout(ABC):
    card_width_pt: float = 180.0       # 2.5"
    card_height_pt: float = 252.0      # 3.5"
    car_section_fraction: float = 0.33 # top 1/3 = car info
    gutter_pt: float = 9.0             # 1/8" between cards
    content_inset_pt: float = 4.0      # white border inside cut line

    def draw_car_section(self, canvas, car, x, y, w, h): ...
    def draw_waybill_section(self, canvas, waybill, x, y, w, h): ...
```

Each waybill type can render its section differently (e.g. `BAD_ORDER` shows a prominent badge, `HOLD` shows "HOLD AT:" in large type).

Initial layout: **`StandardPrrLayout`** — PRR visual style, transition era.

Adding a new layout = new subclass file, no changes to renderer.

---

## Renderer & Page Layout

**Page:** 8.5" × 11" portrait = 612pt × 792pt

**Grid with 1/8" gutters:**
- 3 columns × 180pt + 4 × 9pt gutters = 576pt (fits in 612pt, ~18pt left/right margin)
- 3 rows × 252pt + 4 × 9pt gutters = 792pt (exactly fills height)
- 9 cards per page

**Content inset:** card content is inset 4pt from the cut line on all sides — a thin white border so imperfect cuts don't clip content.

**Crop marks** appear at each card corner, outside the gutter, to guide cutting.

**Renderer logic:**
1. Accept a list of `(Car, Waybill)` pairs from the session file
2. Chunk into groups of 9
3. For each group, tile cards onto a page using the active Layout
4. Write to a single PDF output file

---

## CLI

Entry point: `waybill` (installed via `pyproject.toml` scripts).

```
waybill generate --session session.yaml   # generate cards from session file
waybill list cars                         # show active car roster
waybill list waybills [--type LOADED]     # show waybills, optionally filtered by type
waybill validate                          # validate all data files against schema
```

**Global options:**
```
--layout standard_prr       # layout class to use
--output waybills.pdf        # output PDF path (default: waybills-YYYYMMDD.pdf)
--data-source yaml|sqlite    # backend to use
--data-path ./data           # path to data directory or db file
```

**`waybill.toml`** at project root sets defaults:
```toml
[defaults]
layout = "standard_prr"
data_source = "yaml"
data_path = "./data"
output_dir = "./output"
```

---

## Project Structure

```
mifflin-subdivision-operations/
├── CLAUDE.md                          # project context for Claude Code sessions
├── waybill.toml                       # run-time defaults
├── pyproject.toml                     # build + dependencies
├── README.md                          # setup and usage docs
├── .venv/                             # local virtualenv (gitignored)
├── waybill_generator/
│   ├── __init__.py
│   ├── cli.py                         # Click entry point
│   ├── config.py                      # load waybill.toml defaults
│   ├── models/
│   │   ├── __init__.py
│   │   ├── car.py
│   │   ├── location.py
│   │   ├── commodity.py
│   │   └── waybill.py                 # base + all subtypes
│   ├── repository/
│   │   ├── __init__.py
│   │   ├── base.py                    # abstract BaseRepository
│   │   ├── yaml_repo.py
│   │   └── sqlite_repo.py
│   ├── layouts/
│   │   ├── __init__.py
│   │   ├── base.py                    # abstract BaseLayout
│   │   └── standard_prr.py
│   └── renderer/
│       ├── __init__.py
│       └── pdf.py                     # page tiler + crop marks
├── data/
│   ├── cars.yaml
│   ├── locations.yaml
│   ├── commodities.yaml
│   └── waybills.yaml
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-06-26-waybill-generator-design.md
└── tests/
    ├── test_models.py
    ├── test_repository.py
    └── test_renderer.py
```

---

## Tech Stack

| Concern | Library |
|---|---|
| CLI | Click |
| Data models + validation | Pydantic v2 |
| PDF generation | ReportLab |
| YAML parsing | PyYAML |
| Config file | tomllib (stdlib, Python 3.11+) |
| Testing | pytest + pytest-cov |
| Linting | ruff |

**Python:** 3.11+

**Setup:**
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
waybill --help
```

---

## Key Design Decisions

- **YAML first, SQLite later** — schema is still evolving; YAML makes field changes trivial. Migrate to SQLite once the model stabilizes.
- **No static assignments** — car→waybill mapping lives only in ephemeral session files, not the data layer.
- **Layout as Strategy** — swapping card visual design requires only changing a config value, not modifying renderer logic.
- **Repository as interface** — the rest of the system is completely unaware of the data backend.
- **Session file = print job input** — same path for one replacement card or a full run; no special-casing.
