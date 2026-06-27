# Text Wrapping for experimental_1 Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `_value_wrap` and `_value_truncate` helpers to `Experimental1Layout` and update all value-rendering call sites so text wraps across multiple lines (or truncates with "…") instead of overflowing field boundaries.

**Architecture:** Two new private helpers: `_value_wrap` (word-wraps text into up to `max_lines` lines using `stringWidth` for measurement, truncating the last line with "…" when text still doesn't fit) and `_value_truncate` (thin alias calling `_value_wrap` with `max_lines=1`). All existing `_value(...)` calls in `_draw_loaded`, `_draw_empty`, and `_draw_generic_rows` are replaced with the appropriate helper; `y` baselines shift upward in multi-line rows to leave room for the second line within the existing fixed row height.

**Tech Stack:** Python 3.11+, ReportLab (`reportlab.pdfbase.pdfmetrics.stringWidth` for text measurement — no new package installs needed).

## Global Constraints

- Modify only `waybill_generator/layouts/experimental_1.py` and `tests/test_layouts.py`; no changes to `BaseLayout`, the renderer, CLI, or any other layout
- No new dependencies; `stringWidth` is already available from `reportlab.pdfbase.pdfmetrics`
- Row heights are **fixed** — no dynamic growth; multi-line `y` positions must land inside the existing fixed rows
- Font: Courier-Bold; `line_gap = 2` pt between baselines
- Truncation marker: `"…"` (U+2026 HORIZONTAL ELLIPSIS)
- Card dimensions (from `BaseLayout`): 180 × 252 pt; inset 4.5 pt; waybill section `w ≈ 171 pt`, `h ≈ 162.5 pt`
- All tests in `tests/test_layouts.py`; commit after every task

---

### Task 1: Add `_value_wrap` and `_value_truncate` helpers

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py` (add two methods after `_value`, around line 35)
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Produces:
  - `_value_wrap(self, canvas, text, x, y, max_w, size, max_lines=1, line_gap=2) -> None`
  - `_value_truncate(self, canvas, text, x, y, max_w, size) -> None`

---

- [ ] **Step 1: Write the failing unit tests**

Add these three tests to `tests/test_layouts.py` (after the existing `WAYBILLS` list, before the first `def test_`):

```python
def test_value_wrap_short_text_draws_once():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    layout._value_wrap(canvas, "short", x=0, y=100, max_w=200, size=9)
    assert canvas.drawString.call_count == 1
    assert canvas.drawString.call_args_list[0].args[1] == 100  # y unchanged


def test_value_wrap_long_text_wraps_to_two_lines():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    # Courier-Bold 9pt: each char ≈ 5.4pt. "hello"=27pt fits in 30, "hello world"=59.4pt does not.
    layout._value_wrap(canvas, "hello world", x=0, y=100, max_w=30, size=9, max_lines=2)
    assert canvas.drawString.call_count == 2
    assert canvas.drawString.call_args_list[0].args[1] == 100       # line 1 at y
    assert canvas.drawString.call_args_list[1].args[1] == 100 - (9 + 2)  # line 2 at y - (size+gap)


def test_value_wrap_overflow_truncates_with_ellipsis():
    from unittest.mock import MagicMock
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    canvas = MagicMock()
    # max_lines=1, "hello world" can't fit in 30pt on one line → truncate with "…"
    layout._value_wrap(canvas, "hello world", x=0, y=100, max_w=30, size=9, max_lines=1)
    assert canvas.drawString.call_count == 1
    drawn = canvas.drawString.call_args_list[0].args[2]
    assert drawn.endswith("…"), f"Expected truncation with '…', got: {drawn!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_layouts.py::test_value_wrap_short_text_draws_once \
       tests/test_layouts.py::test_value_wrap_long_text_wraps_to_two_lines \
       tests/test_layouts.py::test_value_wrap_overflow_truncates_with_ellipsis -v
```

Expected: `FAIL` — `AttributeError: … has no attribute '_value_wrap'`

- [ ] **Step 3: Implement the helpers**

In `waybill_generator/layouts/experimental_1.py`, add these two methods immediately after `_value` (after line 35, before `_hrule`):

```python
    def _value_wrap(
        self,
        canvas: Canvas,
        text: str,
        x: float,
        y: float,
        max_w: float,
        size: int,
        max_lines: int = 1,
        line_gap: int = 2,
    ) -> None:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        canvas.setFont("Courier-Bold", size)
        canvas.setFillColor(black)
        words = text.split()
        if not words:
            return
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if stringWidth(candidate, "Courier-Bold", size) <= max_w:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
                if len(lines) >= max_lines:
                    break
        if current and len(lines) < max_lines:
            lines.append(current)
        if " ".join(lines) != text.strip():
            last = lines[-1] if lines else ""
            while last and stringWidth(last + "…", "Courier-Bold", size) > max_w:
                last = last[:-1]
            if lines:
                lines[-1] = last + "…"
            else:
                lines = ["…"]
        for i, line in enumerate(lines):
            canvas.drawString(x, y - i * (size + line_gap), line)

    def _value_truncate(
        self, canvas: Canvas, text: str, x: float, y: float, max_w: float, size: int
    ) -> None:
        self._value_wrap(canvas, text, x, y, max_w=max_w, size=size, max_lines=1)
```

- [ ] **Step 4: Run unit tests to verify they pass**

```bash
pytest tests/test_layouts.py::test_value_wrap_short_text_draws_once \
       tests/test_layouts.py::test_value_wrap_long_text_wraps_to_two_lines \
       tests/test_layouts.py::test_value_wrap_overflow_truncates_with_ellipsis -v
```

Expected: `PASS`

- [ ] **Step 5: Run all layout tests to confirm no regressions**

```bash
pytest tests/test_layouts.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: add _value_wrap and _value_truncate helpers to Experimental1Layout"
```

---

### Task 2: Update all call sites to use wrapping helpers

Replace all `_value(...)` calls in `_draw_loaded`, `_draw_empty`, and `_draw_generic_rows` with `_value_wrap` or `_value_truncate`, adjusting `y` baselines where needed to fit two lines inside the fixed row heights.

**Files:**
- Modify: `waybill_generator/layouts/experimental_1.py`
- Modify: `tests/test_layouts.py`

**Interfaces:**
- Consumes: `_value_wrap` and `_value_truncate` from Task 1
- `mid = x + w / 2` (used in `_draw_loaded` and `_draw_empty`; `w ≈ 171`)
- `col_rr = x + w * 3 / 4` (used in `_draw_empty` To or Via / R.R. row)

---

- [ ] **Step 1: Write the integration test**

Add to `tests/test_layouts.py`:

```python
def test_loaded_long_values_render_without_error():
    """Long station/consignee/routing values must not raise and must produce a valid PDF."""
    import io
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.pagesizes import letter
    from waybill_generator.layouts.experimental_1 import Experimental1Layout
    layout = Experimental1Layout()
    waybill = LoadedWaybill(
        id="w-long", originating_railroad_id="PRR",
        commodity_id="coal",
        to_city="West Pittsburgh and Allegheny Terminal Junction", to_state="PA",
        from_city="New Cumberland Freight Yard and Classification Center", from_state="PA",
        consignee_name="Pittsburgh Steel Manufacturing Company Incorporated",
        shipper_name="Appalachian Mining and Extraction Cooperative",
        routing=["PRR", "B&O", "C&O", "N&W", "L&N", "Southern Railway Lines"],
    )
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=letter)
    layout.draw_card(c, CAR, waybill, RR, x=0, y=0)
    c.save()
    assert b"%PDF" in buf.getvalue()
```

- [ ] **Step 2: Run test to verify it fails (currently overflows, or passes by luck — verify the helpers are actually called)**

```bash
pytest tests/test_layouts.py::test_loaded_long_values_render_without_error -v
```

The test itself may not fail with the old `_value` calls (ReportLab doesn't raise on overflow), but it documents intent and will catch regressions. If it passes already, that's fine — the remaining steps still update the call sites as required by the spec.

- [ ] **Step 3: Update `_draw_loaded` call sites**

In `waybill_generator/layouts/experimental_1.py`, replace the entire `_draw_loaded` method with:

```python
    def _draw_loaded(
        self, canvas: Canvas, waybill: LoadedWaybill,
        x: float, y: float, w: float, h: float,
    ) -> None:
        cursor = y + h
        mid = x + w / 2
        col_w = mid - x - 4  # usable column width ≈ 81.5pt

        # TO STATION, STATE | FROM STATION, STATE (35pt, size=10, 2 lines)
        # Line 1 at cursor+22, line 2 at cursor+10 — both inside the 35pt row.
        cursor -= 35
        self._label(canvas, "TO STATION, STATE", x + 2, cursor + 28)
        self._label(canvas, "FROM STATION, STATE", mid + 2, cursor + 28)
        to_val = f"{waybill.to_city}, {waybill.to_state}" if waybill.to_city else ""
        from_val = f"{waybill.from_city}, {waybill.from_state}" if waybill.from_city else ""
        self._value_wrap(canvas, to_val, x + 2, cursor + 22, max_w=col_w, size=10, max_lines=2)
        self._value_wrap(canvas, from_val, mid + 2, cursor + 22, max_w=col_w, size=10, max_lines=2)
        self._vcol(canvas, mid, cursor, 35)
        self._hrule(canvas, x, cursor, w)

        # CONSIGNEE | SHIPPER (28pt, size=7, 2 lines)
        # Line 1 at cursor+15, line 2 at cursor+6 — both inside the 28pt row.
        cursor -= 28
        self._label(canvas, "CONSIGNEE", x + 2, cursor + 21)
        self._label(canvas, "SHIPPER", mid + 2, cursor + 21)
        self._value_wrap(canvas, waybill.consignee_name or "", x + 2, cursor + 15,
                         max_w=col_w, size=7, max_lines=2)
        self._value_wrap(canvas, waybill.shipper_name or "", mid + 2, cursor + 15,
                         max_w=col_w, size=7, max_lines=2)
        self._vcol(canvas, mid, cursor, 28)
        self._hrule(canvas, x, cursor, w)

        # ROUTE (20pt, size=7, single line — row too tight for a second)
        cursor -= 20
        self._label(canvas, "ROUTE — SHOW IN ROUTE ORDER", x + 2, cursor + 13)
        if waybill.routing:
            self._value_truncate(canvas, " - ".join(waybill.routing), x + 2, cursor + 4,
                                 max_w=w - 4, size=7)
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

- [ ] **Step 4: Update `_draw_empty` call sites**

Replace the entire `_draw_empty` method with:

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

        # Billed from (10pt, single line)
        cursor -= 10
        self._label(canvas, "Billed from", x + 2, cursor + 4)
        if waybill.home_billed_from:
            self._value_truncate(canvas, waybill.home_billed_from, x + 38, cursor + 4,
                                 max_w=w - 40, size=7)
        self._hrule(canvas, x, cursor, w)

        # To or Via / R.R. (10pt, single line each)
        cursor -= 10
        col_rr = x + w * 3 / 4
        self._label(canvas, "To or Via", x + 2, cursor + 4)
        self._label(canvas, "R.R.", col_rr + 2, cursor + 4)
        if waybill.home_to_or_via:
            self._value_truncate(canvas, waybill.home_to_or_via, x + 30, cursor + 4,
                                 max_w=col_rr - x - 32, size=7)
        if waybill.home_rr:
            self._value_truncate(canvas, waybill.home_rr, col_rr + 10, cursor + 4,
                                 max_w=w - w * 3 / 4 - 12, size=7)
            self._vcol(canvas, col_rr, cursor, 10)
        self._hrule(canvas, x, cursor, w)

        # FOR LOADING section header (20pt)
        cursor -= 20
        self._section_header(canvas, "FOR LOADING", x, cursor, w)

        # Billed from (10pt, single line)
        cursor -= 10
        self._label(canvas, "Billed from", x + 2, cursor + 4)
        self._value_truncate(canvas, waybill.from_location_id, x + 38, cursor + 4,
                             max_w=w - 40, size=7)
        self._hrule(canvas, x, cursor, w)

        # To (10pt, single line)
        cursor -= 10
        self._label(canvas, "To", x + 2, cursor + 4)
        self._value_truncate(canvas, waybill.to_location_id, x + 12, cursor + 4,
                             max_w=w - 14, size=7)
        self._hrule(canvas, x, cursor, w)

        # Shipper / Spot (remaining ≈ 82.5pt, up to 3 lines each)
        # Labels at cursor-6, first value baseline at cursor-10.
        self._label(canvas, "Shipper", x + 2, cursor - 6)
        self._label(canvas, "Spot", mid + 2, cursor - 6)
        if waybill.shipper_ordered_by:
            self._value_wrap(canvas, waybill.shipper_ordered_by, x + 2, cursor - 10,
                             max_w=w / 2 - 4, size=7, max_lines=3)
        if waybill.spot:
            self._value_wrap(canvas, waybill.spot, mid + 2, cursor - 10,
                             max_w=w / 2 - 4, size=7, max_lines=3)
        self._vcol(canvas, mid, y, cursor - y)
```

- [ ] **Step 5: Update `_draw_generic_rows` call site**

Replace the entire `_draw_generic_rows` method with:

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
            # Value starts at cursor+18; line 2 at cursor+7 — both inside the 30pt row.
            self._value_wrap(canvas, value, x + 2, cursor + 18, max_w=w - 4, size=9, max_lines=2)
            self._hrule(canvas, x, cursor, w)
```

- [ ] **Step 6: Run the integration test**

```bash
pytest tests/test_layouts.py::test_loaded_long_values_render_without_error -v
```

Expected: PASS

- [ ] **Step 7: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass. Verify these pass specifically:
- `test_experimental1_origination_draws_railroad_name`
- `test_experimental1_car_section_draws_car_identity`
- `test_experimental1_waybill_section_loaded_draws_commodity`
- `test_experimental1_waybill_section_empty_draws_for_home`
- `test_experimental1_draw_card_all_waybill_types`

- [ ] **Step 8: Commit**

```bash
git add waybill_generator/layouts/experimental_1.py tests/test_layouts.py
git commit -m "feat: update experimental_1 call sites to use _value_wrap for text wrapping"
```
