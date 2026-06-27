# Experimental 1 Layout Design

**Date:** 2026-06-27
**Status:** Approved

## Overview

Add a second layout, `experimental_1`, that ports the AAR Form AD-98-style freight waybill grid from the `gemini-start` branch prototype (`src/pdf_renderer.py → render_prototype_waybills`) into the current architecture. The layout fits into the existing `BaseLayout` three-zone contract (origination / car / waybill) and is registered in the CLI alongside `modelling_the_sp`.

The experimental aspect is visual — flat grid rows with horizontal dividers, Helvetica labels, and Courier values — not architectural.

## Files Changed

| File | Change |
|---|---|
| `waybill_generator/layouts/experimental_1.py` | New file — `Experimental1Layout` class |
| `waybill_generator/cli.py` | Add `"experimental_1": Experimental1Layout` to `_LAYOUTS` |

No changes to `BaseLayout`, the renderer, or any other layout.

## Architecture

`Experimental1Layout` subclasses `BaseLayout` and implements the three abstract methods. `BaseLayout.draw_card` continues to manage zone coordinates and insets; the layout only draws within the bounds it receives.

```
BaseLayout.draw_card(canvas, car, waybill, railroad, x, y)
    └─ draw_origination_section(...)   # AAR header band
    └─ draw_car_section(...)           # car ID + date/waybill rows
    └─ draw_waybill_section(...)       # outer border + waybill content
```

**Fonts:** Helvetica-Bold for labels, Courier-Bold for values. No custom font registration needed.

## Zone Specifications

Card dimensions (from `BaseLayout`): 180 × 252 pt (2.5" × 3.5"). Inset on sides: 4.5pt. Sections receive inset `(x, y, w, h)` coordinates.

### Origination Section (h ≈ 30.5pt)

- Bottom horizontal rule at `y` (visual separator)
- Form number at top-left and top-right: Helvetica 5pt
- Railroad name centered: Helvetica-Bold 8pt
- Bill-type label centered below: Helvetica 6pt

Bill-type label strings:
- `LOADED` → "FREIGHT WAYBILL"
- `EMPTY` → "SLIP BILL FOR EMPTY CAR"
- `DEADHEAD` → "DEADHEAD ORDER"
- `MOW` → "M-O-W SERVICE BILL"
- `HOLD` → "HOLD ORDER"
- `BAD_ORDER` → "BAD ORDER CARD"

### Car Section (h = 50pt)

Two equal rows of 25pt, separated by a horizontal rule at `y + 25`.

**Top row** (y+25 to y+50):
- Left half: label "CAR INITIALS & NUMBER", value `car.road + " " + car.car_number` (Courier-Bold 9pt)
- Right half: label "KIND", value `car.aar_code` (Courier-Bold 8pt)
- Vertical rule at midpoint, full row height

**Bottom row** (y to y+25):
- Left half: label "DATE", value blank (no date field in model)
- Right half: label "WAYBILL NO.", value `waybill.id` (Courier-Bold 7pt)
- Vertical rule at midpoint, full row height
- Horizontal rule at `y` (bottom edge of car section)

### Waybill Section (h ≈ 162.5pt)

On entry, draws the **full outer card border** by stepping back to the card edge using `self.content_inset_pt`:
```python
inset = self.content_inset_pt
canvas.rect(x - inset, y - inset, self.card_width_pt, self.card_height_pt)
```

Then draws type-specific content within `(x, y, w, h)`:

#### LOADED (5 rows, top to bottom)

| Row | Height | Content |
|---|---|---|
| TO / FROM stations | 35pt | Split columns at mid; labels "TO STATION, STATE" / "FROM STATION, STATE"; values `to_city, to_state` / `from_city, from_state`; Courier-Bold 10pt; vertical rule; horizontal rule at bottom |
| CONSIGNEE / SHIPPER | 28pt | Split at mid; labels "CONSIGNEE" / "SHIPPER"; values `consignee_name` / `shipper_name`; Courier-Bold 7pt; vertical rule; horizontal rule |
| ROUTE | 20pt | Full width; label "ROUTE — SHOW IN ROUTE ORDER"; value `" - ".join(routing)` if any; Courier-Bold 7pt; horizontal rule |
| DESCRIPTION header | 10pt | Full width label "DESCRIPTION OF ARTICLES"; horizontal rule |
| Commodity | ~69pt remaining | `commodity_id` centered, Courier-Bold 12pt |

#### EMPTY (mirrors StandardPrrLayout structure, flat grid style)

| Row | Height | Content |
|---|---|---|
| FOR HOME header | 20pt | Bold centered section header with double rules above and below |
| Billed from | 10pt | Label + value `home_billed_from`; horizontal rule |
| To or Via / R.R. | 10pt | Split at ¾; values `home_to_or_via`, `home_rr`; vertical rule; horizontal rule |
| FOR LOADING header | 20pt | Bold centered section header with double rules |
| Billed from | 10pt | Label + value `from_location_id`; horizontal rule |
| To | 10pt | Label + value `to_location_id`; horizontal rule |
| Shipper / Spot | ~82pt remaining | Split at mid; values `shipper_ordered_by`, `spot`; vertical rule |

#### DEADHEAD / MOW / HOLD / BAD_ORDER (best-effort flat grid)

Stack available fields as labeled rows with horizontal rules between them, Courier-Bold 9pt values:

- **DEADHEAD**: FROM (`from_location_id`), TO (`to_location_id`), CONSIST (`consist_note`, if set)
- **MOW**: MATERIAL (`commodity_desc`), FROM (`from_location_id`), TO (`to_location_id`), PROJECT (`project`, if set)
- **HOLD**: HOLD AT (`industry_id`), WAITING FOR (`waiting_for`)
- **BAD_ORDER**: FROM (`from_location_id`), REPAIR SHOP (`shop_location_id`), DEFECT (`defect`, if set)

Each row height: 30pt. Remaining space left blank.

## Text Wrapping (Amendment 2026-06-27)

Long field values overflow row boundaries; add word-wrap with truncation.

### New Helpers

**`_value_wrap(canvas, text, x, y, max_w, size, max_lines=1, line_gap=2)`**

Word-wraps `text` into up to `max_lines` lines of width `max_w`, each in Courier-Bold at `size` pt. Lines descend from `y` (first-line baseline) by `size + line_gap` pts. If text still doesn't fit after filling all lines, the last line is truncated and appended with `"…"`. Uses `reportlab.pdfbase.pdfmetrics.stringWidth` for measurement.

**`_value_truncate(canvas, text, x, y, max_w, size)`**

Thin alias: calls `_value_wrap(..., max_lines=1)`. Use for rows where only one line fits.

### LOADED — field-by-field

| Field | Row ht | Old y | New y | max_lines | max_w |
|---|---|---|---|---|---|
| TO / FROM STATION | 35pt, sz=10 | `cursor+15` | `cursor+22` | 2 | `mid − x − 4` ≈ 81.5pt |
| CONSIGNEE / SHIPPER | 28pt, sz=7 | `cursor+10` | `cursor+15` | 2 | `mid − x − 4` ≈ 81.5pt |
| ROUTE | 20pt, sz=7 | `cursor+4` | `cursor+4` | 1 | `w − 4` ≈ 167pt |

TO/FROM two-line positions: cursor+22 (line 1), cursor+10 (line 2). Both within the 35pt row.  
CONSIGNEE/SHIPPER two-line positions: cursor+15 (line 1), cursor+6 (line 2). Both within the 28pt row.

### EMPTY — field-by-field

All 10pt rows are single-line (4pt below value baseline leaves no room for a second line).

| Field | max_lines | max_w | Notes |
|---|---|---|---|
| FOR HOME Billed from | 1 | `w − 38` | label occupies first 36pt |
| FOR HOME To or Via | 1 | `col_rr − x − 32` | |
| FOR HOME R.R. | 1 | `w − w*3/4 − 12` | |
| FOR LOADING Billed from | 1 | `w − 38` | |
| FOR LOADING To | 1 | `w − 14` | |
| Shipper (remaining ≈82pt) | 3 | `mid − x − 4` | first value y: `cursor−10` |
| Spot (remaining ≈82pt) | 3 | `w/2 − 4` | first value y: `cursor−10` |

Shipper/Spot: change `cursor−16` → `cursor−10` to align with label at `cursor−6`.

### Generic rows

Change `_value(…, cursor+10, size=9)` → `_value_wrap(…, cursor+18, max_w=w−4, size=9, max_lines=2)`.  
Two lines land at cursor+18 and cursor+7 — both inside the 30pt row.

## Constraints and Decisions

- **No weight/billing section.** The bottom weight grid from the gemini prototype is dropped entirely.
- **No background tinting.** All cards render on pure white (no manila/canary fills).
- **No custom font.** Helvetica/Courier are built-in ReportLab fonts; no TTF registration needed.
- **No landscape rotation.** Cards are portrait/upright in the existing 3×3 portrait-page grid.
- **Waybill ID as waybill number.** The model has no explicit `waybill_number` field; `waybill.id` is used.
- **Date row left blank.** No date field exists in `WaybillBase`; the DATE cell is present but empty.

## CLI Registration

```python
_LAYOUTS = {
    "modelling_the_sp": StandardPrrLayout,
    "experimental_1": Experimental1Layout,
}
```

Usage: `waybill generate --session session.yaml --layout experimental_1`
