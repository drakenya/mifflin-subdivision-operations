# Roster XLSX Import — Design Spec

**Date:** 2026-07-15
**Project:** mifflin-subdivision-operations
**Status:** Approved

---

## Overview

A `waybill import-roster` command that reads the "Freight Cars" sheet from a
OneDrive-synced `.xlsx` inventory spreadsheet (the user's personal HO scale
collection tracker), maps its free-text columns onto the `Car` model, and
fully regenerates `data/cars.yaml`. Sold/listed-for-sale cars are excluded.
Car type and capacity are derived from a free-text description column using
a map-file-first, keyword-fallback strategy — the same normalization pattern
used by the existing industry catalog importer
(`waybill_generator/importers/normalizer.py`).

Scope for this pass is the **Freight Cars** sheet only. The workbook also
has Cabooses, Passenger Cars, Steam Locomotives, Diesel Locomotives, Parts,
Structures, MSC, and Track sheets — column layouts for the rolling-stock
sheets (Cabooses, Passenger Cars) are documented below for future work, but
not implemented now.

---

## Source File

Path is passed explicitly via `--source`; nothing OneDrive-specific is
hardcoded (the file simply happens to live in a OneDrive-synced folder,
e.g. `~/OneDrive/Trains/Modeling/Ho Models.xlsx`, which is read like any
other local file once the OneDrive desktop client has synced it).

### `Freight Cars` sheet — column layout

Read via `openpyxl` using each cell's column reference (not positional
order — blank cells are omitted from the underlying XML, so naive
positional reads silently misalign columns on sparse rows).

| Col | Header (as labeled in the sheet) | Actual content |
|---|---|---|
| A | `Inventory date` | date serial, or status text (`SOLD`, `Sell - Box 02`, `LISTED - HO SWAP`) |
| B | *(unlabeled — header cell holds a stray row-count value, not a real label)* | **Road** / reporting mark, e.g. `PRR`, `ATSF`, `B&O` |
| C | `Manufacturer` | manufacturer name |
| D | `Manufacturer #` | manufacturer catalog/stock number |
| E | `Location` | storage bin, or sometimes also status text (`SOLD - HO SWAP`, `Sell - Lot 09`) |
| F | `Type` | free-text car description, e.g. `"70 Ton 12 Panel Triple Hopper"`, `"40' Steel SD Box Car"` |
| K | `Car #` | **car_number** (road number, digits) |
| S | `Notes` | maps directly to `Car.notes` |

Columns G–J, L–R, T onward (Class, Blt, Reweigh, Era/Date, Scheme, Color,
Doors, Ends, Assembled, Couplers, Wheels, purchase/sale/pricing fields,
photo) are not used by this import — the `Car` model has no place for them.

### Other rolling-stock sheets (documented for later, not implemented)

- **Cabooses**: same layout as Freight Cars (Inventory date, Road, Manufacturer,
  Manufacturer #, Location, Type, Class, Blt, ReWeigh, Era/Date, Car #, Assignment,
  Scheme, Color, Assembled, Couplers, Notes, ...).
- **Passenger Cars**: narrower layout — `Inventory Date, Road(unlabeled), Manufacturer,
  Manufacturer #, Model Location, Type, Car # / Name, Scheme, Notes, Date of
  Purchase, Price, Supplier`. No AAR-style car type concept applies; would need
  its own field mapping if added later.
- Steam/Diesel Locomotives, Parts, Structures, MSC, Track: out of scope — the
  `Car` model represents waybill-eligible freight rolling stock only.

---

## Architecture

### New module: `waybill_generator/importers/roster_xlsx.py`

```
waybill_generator/
  importers/
    roster_xlsx.py   — new: sheet reader, row parser, sold filter,
                        type/capacity/length normalization, report
```

Reuses `waybill_generator/importers/base.py` conventions where they fit
(dataclass-based intermediate row, report object) but is its own module
since the domain (physical roster vs. industry catalog) is unrelated.

### Updated: `waybill_generator/cli.py`

Adds the `waybill import-roster` command.

### Updated: `pyproject.toml`

Adds `openpyxl` — the existing `xlrd` dependency only reads legacy `.xls`,
not `.xlsx`.

---

## Data Flow

```
SOURCE.xlsx
  └─ openpyxl reads "Freight Cars" sheet, row by cell-reference
       └─ RawRosterRow (inventory_status, road, type_text, car_number, notes)
            └─ filter: skip rows where inventory_status or location text
                       matches sold/sell/listed/swap (case-insensitive)
            └─ filter: skip rows missing road or car_number (→ "incomplete" report bucket)
            └─ normalize (car_type_map.yaml → keyword fallback → XM default)
                 └─ aar_code
            └─ derive capacity_tons (regex tonnage in type_text → capacity-by-aar_code table)
            └─ derive length_ft (regex leading NN' in type_text → blank if absent)
            └─ build Car(id=f"{road}-{car_number}", ...)
                 └─ dedup by id (last row wins; collisions reported)
                      └─ write data/cars.yaml (full replace)
                           └─ print report
```

---

## Normalization

### AAR code (priority order)

1. **`car_type_map.yaml` explicit lookup** — user-maintained, same shape as
   `commodity_map.yaml`:
   ```yaml
   - source_text: "70 Ton 12 Panel Triple Hopper"
     aar_code: HM
   - source_text: "GS 40' Gondola"
     aar_code: GS
   ```
   Lookup is case-insensitive exact match on the full `Type` text.

2. **Keyword auto-match** against the project's own `data/aar_codes.yaml`
   codes (not generic real-world AAR conventions — this project uses its
   own subset, e.g. `RB` = Refrigerator Car, `RS` = Stock Car):

   | Keyword in Type text | aar_code |
   |---|---|
   | `box car` | `XM` |
   | `hopper` (no `covered`/`grain`/`cement`) | `HM` |
   | `covered hopper` | `LO` |
   | `grain` + `hopper` | `LB` |
   | `cement` + `hopper` | `LC` |
   | `gondola` + `steel` | `GS` |
   | `gondola` (otherwise) | `GB` |
   | `flat car` | `FM` |
   | `tank car` | `TM` |
   | `reefer` / `ice bunker` / `ice hatch` / `refrigerator` | `RB` |
   | `stock car` | `RS` |

3. **Fallback**: `XM` (generic box car), and the car's `notes` gets a
   marker appended: `[import: guessed aar_code from "<type text>"]`.

### Capacity (tons)

1. Regex-extract an explicit tonnage from the Type text, e.g.
   `r"(\d+)\s*[Tt]on"` → `"70 Ton 12 Panel Triple Hopper"` → `70`.
2. Else, look up a small built-in default-by-aar_code table (era-typical
   PRR transition-era capacities, e.g. XM→50, HM→70, LO→70, GS/GB→50,
   FM→50, TM→50, RB→40, RS→40).
3. Whenever the value comes from step 2 (not an explicit regex match), the
   `notes` marker also flags it: `[import: guessed capacity_tons]`.

### Length (ft)

Regex-extract a leading `NN'` from the Type text, e.g. `r"^(\d+)'"` →
`"40' Steel SD Box Car"` → `40`. If absent, `length_ft` is left blank
(field is optional on `Car`).

### Sold/status filtering

A row is skipped entirely (not imported as `active: false`, per decision —
sold cars shouldn't clutter an active roster) if the Inventory Date column
or the Location column contains (case-insensitive) any of: `sold`, `sell`,
`listed`, `swap`.

### Missing-field and duplicate handling

- Row missing `road` or `car_number` → skipped, counted as "incomplete" in
  the report (not guessed — these look like genuine data-entry gaps, e.g.
  a value shifted into the wrong column).
- Duplicate `id` (same road + car_number appearing twice) → last row wins;
  the report lists any collisions so they can be checked by hand.

---

## Re-import Strategy

Full resync: every run reads the spreadsheet's current "Freight Cars" sheet
and replaces `data/cars.yaml` entirely. No merge with prior YAML content —
the spreadsheet is the source of truth for this data. Safe to re-run any
time the spreadsheet changes; guessed/fallback values are re-derived (and
re-flagged in `notes`) each time until `car_type_map.yaml` is extended to
cover them explicitly.

---

## CLI Command

```
waybill import-roster --source "/path/to/Ho Models.xlsx"
```

### Report format

```
Importing roster: Ho Models.xlsx  [Freight Cars]
  Rows read:        816
  Skipped (sold):   142
  Skipped (incomplete): 3
  Imported:         671
  Duplicate ids:      0

AAR code resolution:
  map-matched:      412
  keyword-matched:  238
  fallback (XM):     21

Capacity resolution:
  regex-extracted:  187
  default table:     484

Unmapped types (add to car_type_map.yaml to resolve):
  "Bev-Bel Special Run Box Car"    3 cars
  "Custom decorated hopper"        1 car
  ...
```

---

## File Layout Changes

```
waybill_generator/
  importers/
    roster_xlsx.py        # new: sheet reader, normalization, report
  cli.py                   # updated: add import-roster command

data/
  car_type_map.yaml        # new: user-editable Type-text → aar_code overrides (starts empty)

pyproject.toml              # updated: add openpyxl

tests/
  test_roster_import.py    # new: parser, sold-filter, normalizer, dedup tests
```

---

## Testing

`tests/test_roster_import.py` covers, using a small fixture `.xlsx` (or
in-memory `openpyxl.Workbook`) with a handful of representative rows:

- **Parsing**: correct extraction of road, car_number, type_text, notes
  from cells addressed by reference, including a row with blank leading
  cells (the sparse-cell misalignment case found during investigation).
- **Sold filtering**: rows with `SOLD`, `Sell - Box 02`, `LISTED - HO SWAP`
  in either status column are excluded; a normal row is not.
- **Incomplete rows**: missing road or car_number → skipped, not crashed on.
- **AAR normalization**: map lookup wins over keyword match; keyword match
  covers each keyword in the table; unmapped text falls back to `XM` and
  appends the guess marker to `notes`.
- **Capacity/length derivation**: explicit tonnage/length text extracted
  correctly; absence falls back to the default table / blank.
- **Dedup**: two rows with the same road+car_number → one Car in output,
  collision reported.

No integration test against the real spreadsheet (personal/private data).

---

## Dependencies

- `openpyxl` — reading `.xlsx` files (added to `pyproject.toml`).
