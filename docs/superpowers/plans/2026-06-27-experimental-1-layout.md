# Experimental 1 Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Experimental1Layout` — an AAR Form AD-98-style grid layout — registered as `"experimental_1"` in the CLI alongside the existing `modelling_the_sp` layout.

**Architecture:** `Experimental1Layout` subclasses `BaseLayout` and implements the three abstract methods (`draw_origination_section`, `draw_car_section`, `draw_waybill_section`). `BaseLayout.draw_card` manages zone coordinates and insets unchanged; the new class only draws within the bounds it receives. The waybill section also draws the outer card border using `self.content_inset_pt` to step back to the card edge.

**Tech Stack:** Python 3.11+, ReportLab (built-in fonts only — Helvetica-Bold labels, Courier-Bold values, no TTF registration), Pydantic v2.

## Global Constraints

- Python 3.11+ (use `match` statements freely)
- No changes to `BaseLayout`, the renderer (`renderer/pdf.py`), or any existing layout
- No new dependencies; Helvetica and Courier are ReportLab built-ins
- Card dimensions: 180 × 252 pt (from `BaseLayout` class attributes)
- Zone heights: origination = 35pt, car = 50pt, waybill = 167pt; sections receive inset `(x, y, w, h)` where inset = 4.5pt on sides; waybill zone also inset 4.5pt from bottom
- All tests go in `tests/test_layouts.py`
- Commit after every task

---

### Task 1: Scaffold `Experimental1Layout` and register in CLI

**Files:**
- Create: `waybill_generator/layouts/experimental_1.py`
- Modify: `waybill_generator/cli.py` (lines 7–11)
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Produces: `Experimental1Layout` class, importable and instantiable; registered as `"experimental_1"` in `cli._LAYOUTS`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_layouts.py` (after the existing `WAYBILLS` list):

```python
def test_experimental1_layout_is_registered():
    from waybill_generator.cli import _LAYOUTS
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    assert "experimental_1" in _LAYOUTS
    assert _LAYOUTS["experimental_1"] is Experimental1Layout


def test_experimental1_layout_instantiates():
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    assert layout.card_width_pt == 180.0
    assert layout.card_height_pt == 252.0
    assert layout.origination_height_pt == 35.0
    assert layout.car_height_pt == 50.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_layouts.py::test_experimental1_layout_is_registered tests/test_layouts.py::test_experimental1_layout_instantiates -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'waybill_generator.layouts.experimental_1'`

- [ ] **Step 3: Create the scaffold**

Create `waybill_generator/layouts/experimental_1.py`:

```python
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import black
from waybill_generator.layouts.base import BaseLayout
from waybill_generator.models.car import Car
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import (
    WaybillBase, WaybillType,
    LoadedWaybill, EmptyWaybill,
)

_BILL_TYPE_LABELS = {
    WaybillType.LOADED: "FREIGHT WAYBILL",
    WaybillType.EMPTY: "SLIP BILL FOR EMPTY CAR",
    WaybillType.DEADHEAD: "DEADHEAD ORDER",
    WaybillType.MOW: "M-O-W SERVICE BILL",
    WaybillType.HOLD: "HOLD ORDER",
    WaybillType.BAD_ORDER: "BAD ORDER CARD",
}


class Experimental1Layout(BaseLayout):

    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float, y: float, w: float, h: float,
    ) -> None:
        pass

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        pass

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        pass
```

- [ ] **Step 4: Register in CLI**

In `waybill_generator/cli.py`, add the import and update `_LAYOUTS`:

```python
from waybill_generator.layouts.modelling_the_sp import ModellingTheSpLayout
from waybill_generator.layouts.experimental_1 import Experimental1Layout
```

```python
_LAYOUTS = {
    "modelling_the_sp": StandardPrrLayout,
    "experimental_1": Experimental1Layout,
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_layouts.py::test_experimental1_layout_is_registered tests/test_layouts.py::test_experimental1_layout_instantiates -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py waybill_generator/cli.py tests/test_layouts.py
git commit -m "feat: scaffold Experimental1Layout and register in CLI"
```

---

### Task 2: Implement `draw_origination_section` and private drawing helpers

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py`
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `Experimental1Layout` stub from Task 1
- Produces: helpers `_label`, `_value`, `_hrule`, `_vcol`, `_section_header` (used by all later tasks); `draw_origination_section` draws railroad name, bill type, and waybill id in the header band

- [ ] **Step 1: Write the failing test**

Add to `tests/test_layouts.py`:

```python
def test_experimental1_origination_draws_railroad_name():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    rr = Railroad(id="PRR", name="Pennsylvania Railroad", form_number="Form 1304")
    waybill = WAYBILLS[0]  # LoadedWaybill
    layout.draw_origination_section(canvas, rr, waybill, x=4.5, y=217.0, w=171.0, h=30.5)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("PENNSYLVANIA RAILROAD" in c for c in calls), (
        "Expected railroad name (uppercased) in origination section draw calls"
    )
    assert any("FREIGHT WAYBILL" in c for c in calls), (
        "Expected bill type label in origination section draw calls"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_layouts.py::test_experimental1_origination_draws_railroad_name -v
```

Expected: FAIL — `pass` stub makes no canvas calls, assertions fail.

- [ ] **Step 3: Implement helpers and `draw_origination_section`**

Replace the scaffold class body in `waybill_generator/layouts/experimental_1.py` with:

```python
class Experimental1Layout(BaseLayout):

    # -- Private drawing helpers ----------------------------------------------

    def _label(self, canvas: Canvas, text: str, x: float, y: float) -> None:
        canvas.setFont("Helvetica-Bold", 3.8)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _value(
        self, canvas: Canvas, text: str, x: float, y: float, size: int = 9
    ) -> None:
        canvas.setFont("Courier-Bold", size)
        canvas.setFillColor(black)
        canvas.drawString(x, y, text)

    def _hrule(self, canvas: Canvas, x: float, y: float, w: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)

    def _vcol(self, canvas: Canvas, x: float, y: float, h: float) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.4)
        canvas.line(x, y, x, y + h)

    def _section_header(
        self, canvas: Canvas, text: str, x: float, y: float, w: float
    ) -> None:
        """Centered section header (Helvetica-Bold 9pt) with double rules."""
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(black)
        canvas.drawCentredString(x + w / 2, y + 3, text)
        self._hrule(canvas, x, y + 14, w)
        self._hrule(canvas, x, y + 1, w)

    # -- Origination band -----------------------------------------------------

    def draw_origination_section(
        self,
        canvas: Canvas,
        railroad: Railroad,
        waybill: WaybillBase,
        x: float, y: float, w: float, h: float,
    ) -> None:
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.5)
        canvas.line(x, y, x + w, y)  # bottom separator rule

        canvas.setFillColor(black)

        # Form number top-left, waybill id top-right
        canvas.setFont("Helvetica", 5)
        canvas.drawString(x, y + h - 6, railroad.form_number)
        canvas.drawRightString(x + w, y + h - 6, waybill.id)

        # Railroad name centered
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawCentredString(x + w / 2, y + h / 2 + 2, railroad.name.upper())

        # Bill type label centered below railroad name
        canvas.setFont("Helvetica", 6)
        canvas.drawCentredString(
            x + w / 2, y + 4, _BILL_TYPE_LABELS[waybill.waybill_type]
        )

    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        pass

    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_layouts.py::test_experimental1_origination_draws_railroad_name -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: implement Experimental1Layout origination section and drawing helpers"
```

---

### Task 3: Implement `draw_car_section`

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py`
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `_label`, `_value`, `_hrule`, `_vcol` from Task 2
- Produces: `draw_car_section` draws a two-row grid: (CAR INITIALS & NUMBER | KIND) over (DATE | WAYBILL NO.)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_layouts.py`:

```python
def test_experimental1_car_section_draws_car_identity():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    layout.draw_car_section(canvas, CAR, x=4.5, y=167.0, w=171.0, h=50.0)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("PRR 12345" in c for c in calls), (
        "Expected 'PRR 12345' (road + car_number) in car section draw calls"
    )
    assert any("XM" in c for c in calls), (
        "Expected aar_code 'XM' (KIND field) in car section draw calls"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_layouts.py::test_experimental1_car_section_draws_car_identity -v
```

Expected: FAIL — `pass` stub makes no canvas calls.

- [ ] **Step 3: Implement `draw_car_section`**

Replace the `draw_car_section` stub in `waybill_generator/layouts/experimental_1.py`:

```python
    def draw_car_section(
        self, canvas: Canvas, car: Car, x: float, y: float, w: float, h: float
    ) -> None:
        mid = x + w / 2
        row_h = h / 2  # 25pt per row

        # Top row: CAR INITIALS & NUMBER (left) | KIND (right)
        self._label(canvas, "CAR INITIALS & NUMBER", x + 2, y + h - 8)
        self._label(canvas, "KIND", mid + 2, y + h - 8)
        self._value(canvas, f"{car.road} {car.car_number}", x + 2, y + h - 20, size=9)
        self._value(canvas, car.aar_code, mid + 2, y + h - 20, size=8)
        self._vcol(canvas, mid, y + row_h, row_h)
        self._hrule(canvas, x, y + row_h, w)

        # Bottom row: DATE (left, blank) | WAYBILL NO. (right, blank)
        self._label(canvas, "DATE", x + 2, y + row_h - 8)
        self._label(canvas, "WAYBILL NO.", mid + 2, y + row_h - 8)
        self._vcol(canvas, mid, y, row_h)
        self._hrule(canvas, x, y, w)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_layouts.py::test_experimental1_car_section_draws_car_identity -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: implement Experimental1Layout car section"
```

---

### Task 4: Implement `draw_waybill_section` — outer border and LOADED content

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py`
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `_label`, `_value`, `_hrule`, `_vcol` from Task 2; `LoadedWaybill` fields: `to_city`, `to_state`, `from_city`, `from_state`, `consignee_name`, `shipper_name`, `routing` (list[str]), `commodity_id`
- Produces: `draw_waybill_section` draws the full outer card border and dispatches to `_draw_loaded` for LOADED waybills; other types raise `ValueError` (fixed in Task 6)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_layouts.py`:

```python
def test_experimental1_waybill_section_loaded_draws_commodity():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    waybill = LoadedWaybill(
        id="w-1", originating_railroad_id="PRR",
        commodity_id="grain", shipper_id="LEW-GRAIN", consignee_id="ALT-SHOP",
        to_city="Altoona", to_state="PA", consignee_name="Steel Shop",
        from_city="Lewistown", from_state="PA", shipper_name="Grain Co",
    )
    layout.draw_waybill_section(canvas, waybill, x=4.5, y=4.5, w=171.0, h=162.5)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("GRAIN" in c for c in calls), (
        "Expected commodity_id (uppercased) in waybill section draw calls"
    )
    assert any("Altoona, PA" in c for c in calls), (
        "Expected to_city+to_state in waybill section draw calls"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_layouts.py::test_experimental1_waybill_section_loaded_draws_commodity -v
```

Expected: FAIL — `pass` stub makes no canvas calls.

- [ ] **Step 3: Implement `draw_waybill_section` and `_draw_loaded`**

Replace the `draw_waybill_section` stub and add `_draw_loaded` in `waybill_generator/layouts/experimental_1.py`. The full class body (keeping all prior methods, replacing stubs):

```python
    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        # Full outer card border (step back to card edge from the inset coordinates)
        inset = self.content_inset_pt
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.8)
        canvas.rect(x - inset, y - inset, self.card_width_pt, self.card_height_pt)

        match waybill.waybill_type:
            case WaybillType.LOADED:
                self._draw_loaded(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"Unhandled waybill type: {waybill.waybill_type}")

    def _draw_loaded(
        self, canvas: Canvas, waybill: LoadedWaybill,
        x: float, y: float, w: float, h: float,
    ) -> None:
        cursor = y + h
        mid = x + w / 2

        # TO STATION, STATE | FROM STATION, STATE (35pt)
        cursor -= 35
        self._label(canvas, "TO STATION, STATE", x + 2, cursor + 28)
        self._label(canvas, "FROM STATION, STATE", mid + 2, cursor + 28)
        to_val = f"{waybill.to_city}, {waybill.to_state}" if waybill.to_city else ""
        from_val = f"{waybill.from_city}, {waybill.from_state}" if waybill.from_city else ""
        self._value(canvas, to_val, x + 2, cursor + 15, size=10)
        self._value(canvas, from_val, mid + 2, cursor + 15, size=10)
        self._vcol(canvas, mid, cursor, 35)
        self._hrule(canvas, x, cursor, w)

        # CONSIGNEE | SHIPPER (28pt)
        cursor -= 28
        self._label(canvas, "CONSIGNEE", x + 2, cursor + 21)
        self._label(canvas, "SHIPPER", mid + 2, cursor + 21)
        self._value(canvas, waybill.consignee_name or "", x + 2, cursor + 10, size=7)
        self._value(canvas, waybill.shipper_name or "", mid + 2, cursor + 10, size=7)
        self._vcol(canvas, mid, cursor, 28)
        self._hrule(canvas, x, cursor, w)

        # ROUTE (20pt)
        cursor -= 20
        self._label(canvas, "ROUTE — SHOW IN ROUTE ORDER", x + 2, cursor + 13)
        if waybill.routing:
            self._value(canvas, " - ".join(waybill.routing), x + 2, cursor + 4, size=7)
        self._hrule(canvas, x, cursor, w)

        # DESCRIPTION OF ARTICLES header (10pt)
        cursor -= 10
        self._label(canvas, "DESCRIPTION OF ARTICLES", x + 2, cursor + 4)
        self._hrule(canvas, x, cursor, w)

        # Commodity — centered in remaining space (~69.5pt)
        remaining_h = cursor - y
        canvas.setFont("Courier-Bold", 12)
        canvas.setFillColor(black)
        canvas.drawCentredString(
            x + w / 2, y + remaining_h / 2 - 2, waybill.commodity_id.upper()
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_layouts.py::test_experimental1_waybill_section_loaded_draws_commodity -v
```

Expected: PASS

- [ ] **Step 5: Run all layout tests to check for regressions**

```bash
pytest tests/test_layouts.py -v
```

Expected: all existing tests pass; `test_experimental1_*` tests pass; any test that calls `draw_card` with non-LOADED waybills for the new layout will show `ValueError` (that's acceptable until Task 6).

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: implement Experimental1Layout waybill section outer border and LOADED content"
```

---

### Task 5: Implement EMPTY waybill content

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py`
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `_label`, `_value`, `_hrule`, `_vcol`, `_section_header` from Task 2; `EmptyWaybill` fields: `home_billed_from` (optional), `home_to_or_via` (optional), `home_rr` (optional), `from_location_id`, `to_location_id`, `shipper_ordered_by` (optional), `spot` (optional)
- Produces: `_draw_empty` renders FOR HOME + FOR LOADING sections in flat grid style

- [ ] **Step 1: Write the failing test**

Add to `tests/test_layouts.py`:

```python
def test_experimental1_waybill_section_empty_draws_for_home():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    waybill = EmptyWaybill(
        id="e-1", originating_railroad_id="PRR",
        from_location_id="ALT", to_location_id="LEW",
        home_billed_from="PHL", home_to_or_via="ENOLA", home_rr="PRR",
    )
    layout.draw_waybill_section(canvas, waybill, x=4.5, y=4.5, w=171.0, h=162.5)
    calls = [str(c) for c in canvas.mock_calls]
    assert any("FOR HOME" in c for c in calls), (
        "Expected 'FOR HOME' section header in EMPTY waybill draw calls"
    )
    assert any("FOR LOADING" in c for c in calls), (
        "Expected 'FOR LOADING' section header in EMPTY waybill draw calls"
    )
    assert any("ALT" in c for c in calls), (
        "Expected from_location_id in EMPTY waybill draw calls"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_layouts.py::test_experimental1_waybill_section_empty_draws_for_home -v
```

Expected: FAIL — `draw_waybill_section` raises `ValueError` for EMPTY type.

- [ ] **Step 3: Add EMPTY case to `draw_waybill_section` and implement `_draw_empty`**

In `draw_waybill_section`, add the EMPTY case before the `case _` default:

```python
        match waybill.waybill_type:
            case WaybillType.LOADED:
                self._draw_loaded(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.EMPTY:
                self._draw_empty(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case _:
                raise ValueError(f"Unhandled waybill type: {waybill.waybill_type}")
```

Add `_draw_empty` method to the class:

```python
    def _draw_empty(
        self, canvas: Canvas, waybill: EmptyWaybill,
        x: float, y: float, w: float, h: float,
    ) -> None:
        cursor = y + h
        mid = x + w / 2

        # FOR HOME section header (20pt)
        cursor -= 20
        self._section_header(canvas, "FOR HOME", x, cursor, w)

        # Billed from (10pt)
        cursor -= 10
        self._label(canvas, "Billed from", x + 2, cursor + 4)
        if waybill.home_billed_from:
            self._value(canvas, waybill.home_billed_from, x + 38, cursor + 4, size=7)
        self._hrule(canvas, x, cursor, w)

        # To or Via / R.R. (10pt)
        cursor -= 10
        col_rr = x + w * 3 / 4
        self._label(canvas, "To or Via", x + 2, cursor + 4)
        self._label(canvas, "R.R.", col_rr + 2, cursor + 4)
        if waybill.home_to_or_via:
            self._value(canvas, waybill.home_to_or_via, x + 30, cursor + 4, size=7)
        if waybill.home_rr:
            self._value(canvas, waybill.home_rr, col_rr + 10, cursor + 4, size=7)
            self._vcol(canvas, col_rr, cursor, 10)
        self._hrule(canvas, x, cursor, w)

        # FOR LOADING section header (20pt)
        cursor -= 20
        self._section_header(canvas, "FOR LOADING", x, cursor, w)

        # Billed from (10pt)
        cursor -= 10
        self._label(canvas, "Billed from", x + 2, cursor + 4)
        self._value(canvas, waybill.from_location_id, x + 38, cursor + 4, size=7)
        self._hrule(canvas, x, cursor, w)

        # To (10pt)
        cursor -= 10
        self._label(canvas, "To", x + 2, cursor + 4)
        self._value(canvas, waybill.to_location_id, x + 12, cursor + 4, size=7)
        self._hrule(canvas, x, cursor, w)

        # Shipper / Spot (remaining ≈ 82.5pt)
        self._label(canvas, "Shipper", x + 2, cursor - 6)
        self._label(canvas, "Spot", mid + 2, cursor - 6)
        if waybill.shipper_ordered_by:
            self._value(canvas, waybill.shipper_ordered_by, x + 2, cursor - 16, size=7)
        if waybill.spot:
            self._value(canvas, waybill.spot, mid + 2, cursor - 16, size=7)
        self._vcol(canvas, mid, y, cursor - y)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_layouts.py::test_experimental1_waybill_section_empty_draws_for_home -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: implement Experimental1Layout EMPTY waybill content"
```

---

### Task 6: Implement remaining waybill types and final smoke test

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py`
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `_label`, `_value`, `_hrule` from Task 2; `DeadheadWaybill`, `MoWWaybill`, `HoldWaybill`, `BadOrderWaybill` fields; `WAYBILLS` fixture from `test_layouts.py`
- Produces: `_draw_generic_rows` helper; full `draw_waybill_section` dispatch for all 6 waybill types; final smoke test confirming all types render to valid PDF

- [ ] **Step 1: Write the failing smoke test**

Add to `tests/test_layouts.py`:

```python
def test_experimental1_draw_card_all_waybill_types():
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    for waybill in WAYBILLS:
        buf = io.BytesIO()
        canvas = Canvas(buf, pagesize=letter)
        layout.draw_card(canvas, CAR, waybill, RR, x=0, y=0)
        canvas.save()
        content = buf.getvalue()
        assert b"%PDF" in content
        assert len(content) > 500, (
            f"Card for {waybill.waybill_type} produced suspiciously small PDF"
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_layouts.py::test_experimental1_draw_card_all_waybill_types -v
```

Expected: FAIL — `ValueError: Unhandled waybill type: DEADHEAD` (or similar) for waybill types beyond LOADED/EMPTY.

- [ ] **Step 3: Add `_draw_generic_rows` and wire remaining types**

Add `_draw_generic_rows` to the class in `waybill_generator/layouts/experimental_1.py`:

```python
    def _draw_generic_rows(
        self,
        canvas: Canvas,
        rows: list[tuple[str, str | None]],
        x: float, y: float, w: float, h: float,
    ) -> None:
        """Stack (label, value) pairs as 30pt rows with horizontal rules; skip None values."""
        cursor = y + h
        for label, value in rows:
            if value is None:
                continue
            if cursor - 30 < y:
                break
            cursor -= 30
            self._label(canvas, label, x + 2, cursor + 22)
            self._value(canvas, value, x + 2, cursor + 10, size=9)
            self._hrule(canvas, x, cursor, w)
```

Replace the `draw_waybill_section` `match` statement with the full dispatch:

```python
    def draw_waybill_section(
        self, canvas: Canvas, waybill: WaybillBase, x: float, y: float, w: float, h: float
    ) -> None:
        inset = self.content_inset_pt
        canvas.setStrokeColor(black)
        canvas.setLineWidth(0.8)
        canvas.rect(x - inset, y - inset, self.card_width_pt, self.card_height_pt)

        match waybill.waybill_type:
            case WaybillType.LOADED:
                self._draw_loaded(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.EMPTY:
                self._draw_empty(canvas, waybill, x, y, w, h)  # type: ignore[arg-type]
            case WaybillType.DEADHEAD:
                self._draw_generic_rows(canvas, [
                    ("FROM", waybill.from_location_id),  # type: ignore[attr-defined]
                    ("TO", waybill.to_location_id),  # type: ignore[attr-defined]
                    ("CONSIST", waybill.consist_note),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case WaybillType.MOW:
                self._draw_generic_rows(canvas, [
                    ("MATERIAL", waybill.commodity_desc),  # type: ignore[attr-defined]
                    ("FROM", waybill.from_location_id),  # type: ignore[attr-defined]
                    ("TO", waybill.to_location_id),  # type: ignore[attr-defined]
                    ("PROJECT", waybill.project),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case WaybillType.HOLD:
                self._draw_generic_rows(canvas, [
                    ("HOLD AT", waybill.industry_id),  # type: ignore[attr-defined]
                    ("WAITING FOR", waybill.waiting_for),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case WaybillType.BAD_ORDER:
                self._draw_generic_rows(canvas, [
                    ("FROM", waybill.from_location_id),  # type: ignore[attr-defined]
                    ("REPAIR SHOP", waybill.shop_location_id),  # type: ignore[attr-defined]
                    ("DEFECT", waybill.defect),  # type: ignore[attr-defined]
                ], x, y, w, h)
            case _:
                raise ValueError(f"Unhandled waybill type: {waybill.waybill_type}")
```

- [ ] **Step 4: Run smoke test to verify it passes**

```bash
pytest tests/test_layouts.py::test_experimental1_draw_card_all_waybill_types -v
```

Expected: PASS

- [ ] **Step 5: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass with no regressions.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: complete Experimental1Layout with all waybill types"
```
