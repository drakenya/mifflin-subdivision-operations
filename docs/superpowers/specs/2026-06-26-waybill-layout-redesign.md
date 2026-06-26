# Waybill Layout Redesign — 3-Zone Card & Period Visual Style

**Date:** 2026-06-26
**Project:** mifflin-subdivision-operations
**Status:** Approved

---

## Overview

Redesign the printed car card to:

1. Add a third card zone — an **origination band** — that identifies the issuing railroad and bill type, matching prototype freight document conventions.
2. Introduce a **`Railroad`** entity so each waybill carries a reference to its originating railroad (name, form number, optional herald icon).
3. Update `StandardPrrLayout` to period-accurate visual style: Times serif typography, ruled section dividers, two-column field grids — modeled on 1940s–1960s SP freight waybill and empty car bill forms.

The result is a card that reads top-to-bottom: *who issued this bill → which car → what to do with it.*

---

## Card Zone Layout

Card dimensions unchanged: 2.5" × 3.5" (180pt × 252pt), 9 per 8.5×11 page.

Three zones (top to bottom in PDF coordinates, bottom to top in ReportLab y-axis):

| Zone | Height | Background | Purpose |
|---|---|---|---|
| Origination band | ~35pt | White | Issuing railroad, bill type, form number, herald |
| Car section | ~65pt | PRR Tuscan Red | Car identity |
| Waybill section | ~152pt | White | Routing instruction |

`BaseLayout` replaces `car_section_fraction` with two explicit constants:

```python
origination_height_pt: float = 35.0
car_height_pt: float = 65.0
# waybill fills remainder: card_height - origination - car
```

---

## Data Model Changes

### New: `Railroad` (`models/railroad.py`)

```python
class Railroad(BaseModel):
    id: str            # "PRR", "NYC", "B&O"
    name: str          # "Pennsylvania Railroad"
    form_number: str   # "Form 1304" — printed in origination band corners
    icon: str | None = None  # relative path to herald image, e.g. "assets/prr-herald.png"
```

Data file: `data/railroads.yaml`

### Updated: `WaybillBase`

Add required field (no default — every waybill must declare its railroad):

```python
originating_railroad_id: str
```

### Updated: `EmptyWaybill`

Two optional fields to support the "FOR LOADING" section layout:

```python
spot: str | None = None               # specific track/spot at destination
shipper_ordered_by: str | None = None # who ordered the empty ("Shipper" field)
```

---

## Repository Changes

`BaseRepository` gains:

```python
def get_railroads(self) -> list[Railroad]: ...
def get_railroad(self, id: str) -> Railroad: ...
```

`YamlRepository` implements these by loading `data/railroads.yaml`, following the same pattern as existing entity loaders.

---

## Rendering Signature Change

The rendering pipeline changes from pairs to triples throughout:

```python
# Before
list[tuple[Car, WaybillBase]]

# After
list[tuple[Car, WaybillBase, Railroad]]
```

Affected callsites:
- `render_pdf()` in `renderer/pdf.py`
- `layout.draw_card()` in `layouts/base.py`
- CLI `generate` command, which resolves all three entities from the repository before calling `render_pdf()`

---

## Layout Interface Changes (`BaseLayout`)

Replace `car_section_fraction` with:

```python
origination_height_pt: float = 35.0
car_height_pt: float = 65.0
```

Add abstract method:

```python
def draw_origination_section(
    self, canvas: Canvas, railroad: Railroad, x: float, y: float, w: float, h: float
) -> None: ...
```

`draw_card()` calls all three sections in order, computing `y` and `h` for each from the two height constants.

Existing `draw_car_section()` and `draw_waybill_section()` signatures are unchanged; only their `y` and `h` arguments change at the callsite.

---

## Visual Design: `StandardPrrLayout`

### Typography

All text shifts from Helvetica to Times-Roman / Times-Bold throughout. Labels are 5pt Times-Roman ALL CAPS. Values are 8–9pt Times-Bold.

### Origination Band (white bg)

- Railroad `name` centered, Times-Bold 8pt
- Bill type label beneath (e.g. "FREIGHT WAYBILL", "EMPTY CAR BILL"), Times-Roman 7pt
- `form_number` in Times-Roman 5pt, left and right corners
- Herald icon left-aligned at ~12pt height if `icon` is set
- Thin rule (0.5pt) along bottom edge

Bill type labels by waybill type:

| `WaybillType` | Label in origination band |
|---|---|
| LOADED | FREIGHT WAYBILL |
| EMPTY | EMPTY CAR BILL |
| DEADHEAD | DEADHEAD ORDER |
| MOW | M-O-W SERVICE BILL |
| HOLD | HOLD ORDER |
| BAD_ORDER | BAD ORDER CARD |

### Car Section (Tuscan Red bg `#7B1113`, white text)

- Road marking left, car type centered, car number right — Times-Bold 9pt
- Vertical rule dividing road / car number columns
- Capacity bottom-left — Times-Roman 7pt

### Waybill Section — All Types (white bg)

Labels: Times-Roman 5pt ALL CAPS  
Values: Times-Bold 8–9pt  
Horizontal rules (0.5pt) separate each field group.

**LOADED:**
- Two-column row: "TO STATION" / "FROM STATION" with vertical divider and values in 9pt
- Two-column row: "CONSIGNEE" / "SHIPPER" with vertical divider
- "ROUTE" field (7pt, single row)
- "DESCRIPTION OF ARTICLES" label → commodity name in Times-Bold 9pt at bottom

**EMPTY:**
- "FOR LOADING" bold centered section header (Times-Bold 8pt)
- Double horizontal rules above and below header
- "BILLED FROM" → `from_location_id`
- "TO" → `to_location_id`
- "SHIPPER" → `shipper_ordered_by` (if present)
- "SPOT" → `spot` (if present)
- Small instruction text at bottom: *"This bill must accompany car to destination."* (Times-Roman 5pt)

**DEADHEAD:**
- "FROM" / "TO" fields
- "CONSIST" → `consist_note` if present

**MOW:**
- "MATERIAL" → `commodity_desc`
- "FROM" / "TO" fields
- "PROJECT" → `project` if present

**HOLD:**
- "HOLD AT" → `industry_id`
- "WAITING FOR" → `waiting_for`

**BAD ORDER:**
- "FROM" → `from_location_id`
- "SHOP" → `shop_location_id`
- "DEFECT" → `defect` if present

---

## Data Files to Update

- `data/railroads.yaml` — new file; must include a PRR entry and an entry for every railroad ID already referenced by `originating_railroad_id` in `data/waybills.yaml`
- `data/waybills.yaml` — add `originating_railroad_id` to every waybill entry
- `tests/fixtures/railroads.yaml` — new test fixture
- `tests/fixtures/waybills.yaml` — update with `originating_railroad_id`

---

## Files Changed

| File | Change |
|---|---|
| `waybill_generator/models/railroad.py` | New — `Railroad` model |
| `waybill_generator/models/__init__.py` | Export `Railroad` |
| `waybill_generator/models/waybill.py` | Add `originating_railroad_id` to `WaybillBase`; add `spot`, `shipper_ordered_by` to `EmptyWaybill` |
| `waybill_generator/repository/base.py` | Add `get_railroad()` / `get_railroads()` |
| `waybill_generator/repository/yaml_repo.py` | Implement railroad loading |
| `waybill_generator/layouts/base.py` | Replace `car_section_fraction`; add `draw_origination_section()`; update `draw_card()` |
| `waybill_generator/layouts/standard_prr.py` | Full visual redesign; implement `draw_origination_section()` |
| `waybill_generator/renderer/pdf.py` | Pairs → triples |
| `waybill_generator/cli.py` | Resolve railroad; pass triples to renderer |
| `data/railroads.yaml` | New |
| `data/waybills.yaml` | Add `originating_railroad_id` to all entries |
| `tests/fixtures/railroads.yaml` | New |
| `tests/fixtures/waybills.yaml` | Add `originating_railroad_id` |
| `tests/test_models.py` | Railroad model tests; updated waybill tests |
| `tests/test_repository.py` | Railroad repo tests |
| `tests/test_layouts.py` | Updated layout tests (3 zones, origination section) |
| `tests/test_renderer.py` | Updated for triple signature |
| `tests/test_cli.py` | Updated for triple resolution |
