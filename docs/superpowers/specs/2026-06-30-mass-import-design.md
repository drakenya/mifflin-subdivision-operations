# Mass Import — Design Spec

**Date:** 2026-06-30
**Project:** mifflin-subdivision-operations
**Status:** Approved

---

## Overview

A `waybill import` command that reads OpSIG and JBritton source files from `industry_database/`, parses and groups industry records into `CatalogIndustry` entries, normalizes commodities and car types, and writes the result to `data/industry_catalog.yaml`. Designed for iterative use: re-importing a file replaces only entries from that file; manually-added and other-source entries are never touched.

---

## Source Files

All source files live under `industry_database/`:

```
industry_database/
  opsig/        — OpSIG files (.txt and .xls)
  jbritton/     — JBritton files (.txt)
  commodity_map.yaml    — user-editable normalization overrides
  opsig_car_map.yaml    — pre-populated OpSIG car code → AAR code map
  README.md             — format documentation
```

### OpSIG `.txt` format

10-column TSV, Windows CRLF. Columns (0-indexed):

| # | Field       | Notes                              |
|---|-------------|------------------------------------|
| 0 | year        | e.g. `2004`, `55`, `90`            |
| 1 | name        | Industry name                      |
| 2 | city        |                                    |
| 3 | state       | 2-letter abbreviation              |
| 4 | railroad    | e.g. `PRR`, `P&W`, `CSX`          |
| 5 | direction   | `S` (ships) or `R` (receives)      |
| 6 | commodity   | Free-text                          |
| 7 | notes       | Description / process notes        |
| 8 | volume      | e.g. `VH`, `H(e)`, `M-H`          |
| 9 | car_types   | Comma-sep OpSIG codes, e.g. `CH,T` |

### OpSIG `.xls` format

Assumed same columns as `.txt`. Parsed with `xlrd`. Verify column layout during implementation — if the XLS files differ, add a note to `industry_database/README.md` and adjust the parser accordingly.

### JBritton `.txt` format

256-column wide TSV (most columns empty), Windows CRLF. Effective columns:

| # | Field        | Notes                                     |
|---|--------------|-------------------------------------------|
| 0 | year         |                                           |
| 1 | name         | Industry name                             |
| 2 | city         |                                           |
| 3 | state        |                                           |
| 4 | railroad     |                                           |
| 5 | direction    | `S`, `R`, or blank (station/delivery)     |
| 6 | commodity    | Free-text, or blank                       |
| 7 | (blank)      |                                           |
| 8 | location_ref | Division + milepost, stored as `notes`    |
| 9 | source_ref   | e.g. `pennsyrr.com PRR CT1000`            |

No car types. Source format auto-detected from parent directory name (`opsig/` or `jbritton/`), with optional `--source` CLI override.

---

## Architecture

### New package: `waybill_generator/importers/`

```
waybill_generator/
  importers/
    __init__.py
    base.py        — ImportedRow dataclass, grouper, ID generation
    opsig.py       — OpSIG parser (.txt and .xls)
    jbritton.py    — JBritton parser
    normalizer.py  — commodity normalization + car type inference
```

### Updated: `waybill_generator/repository/catalog_repo.py`

Adds one write method:

```python
def replace_from_source(
    self,
    source_file: str,
    new_entries: list[CatalogIndustry],
) -> tuple[int, int]:  # (replaced, added)
```

Reads current `industry_catalog.yaml`, removes all entries where `source_file` matches the argument, appends `new_entries`, writes the file back. Returns counts for the report.

### Updated: `waybill_generator/cli.py`

Adds the `waybill import` command.

---

## Data Flow

```
FILEPATH
  └─ detect source format (dir name or --source)
  └─ parser (opsig.py or jbritton.py)
       └─ list[ImportedRow]
            └─ grouper (base.py)
                 └─ list[grouped industry] (name, city, state, railroad, ships[], receives[], notes, raw_car_types[])
                      └─ normalizer (normalizer.py)
                           └─ list[CatalogIndustry]
                                └─ CatalogRepository.replace_from_source()
                                     └─ updated industry_catalog.yaml + report
```

---

## Shared Types (`base.py`)

```python
@dataclass
class ImportedRow:
    year: str
    name: str
    city: str
    state: str
    railroad: str
    direction: str        # "S", "R", or ""
    commodity: str
    notes: str
    car_types: list[str]  # raw source codes; empty for JBritton
    source_ref: str
```

**Grouper** groups `ImportedRow` list by `(name, city, state, railroad)`:
- `direction=S` → commodity goes into `ships`
- `direction=R` → commodity goes into `receives`
- `direction=""` → commodity goes into both `ships` and `receives` if non-empty; ignored if blank
- `notes` taken from first row with a non-empty notes field

**ID generation**: `cat-{first 8 hex chars of sha256(source_file + name + city + state + railroad)}` — deterministic and stable across re-imports of the same file. The same industry present in two different source files produces two distinct catalog entries (different `source_file` → different hash).

**Fields set by the importer on each `CatalogIndustry`:**
- `source`: `"opsig"` or `"jbritton"` (from detected format)
- `source_file`: the bare filename, e.g., `"OpSig_prrmiddle1945_170802.txt"`
- `source_ref`: for JBritton rows, the value from column 9 (e.g., `"pennsyrr.com PRR CT1000"`); for OpSIG rows, `None`

---

## Normalization (`normalizer.py`)

### Commodity normalization (priority order)

1. **`commodity_map.yaml` explicit lookup** — user-maintained overrides. Lookup is case-insensitive exact match on `source_text`:
   ```yaml
   - source_text: "Petroleum Products"
     commodity_id: petroleum
   - source_text: "Sleds"
     commodity_id: null   # known unmappable; suppressed from unmatched report
   ```
   `commodity_id: null` marks the entry as intentionally unmapped — it stays as free-text and is excluded from the unmatched-commodities report.

2. **Auto-match** — case-insensitive substring check against each commodity's `name` in `commodities.yaml`. Both directions: source text contains commodity name, or commodity name contains source text.

3. **Free-text fallback** — source text stored as-is; entry flagged in the report.

### Car type normalization

**OpSIG sources:** column 9 contains OpSIG shorthand codes. `opsig_car_map.yaml` (pre-populated, not user-edited) maps them to AAR codes:

```yaml
T:  TM    # Tank Car
H:  HM    # Open Hopper
CH: LO    # Covered Hopper
B:  XM    # Box Car
G:  GB    # Gondola
```

Unknown OpSIG codes are dropped and logged as warnings.

**JBritton sources (no car types):** if the commodity resolved to a known commodity id, pull `acceptable_car_types` from `commodities.yaml`. If free-text, `car_types: []`.

---

## Re-import Strategy

Re-import is keyed on `source_file` (the filename, e.g., `OpSig_prrmiddle1945_170802.txt`):

1. Parse the file → normalized `list[CatalogIndustry]`
2. Call `replace_from_source(source_file, new_entries)`
3. All entries in `industry_catalog.yaml` with a matching `source_file` are removed
4. New entries are appended
5. Entries with `source: manual` or a different `source_file` are never modified

This makes re-import safe to run repeatedly as normalization improves.

---

## CLI Command

```
waybill import FILEPATH [--source opsig|jbritton]
```

`--source` is optional; auto-detected from parent directory name. Any file under `industry_database/` is a valid target.

### Report format

```
Importing: OpSig_prrmiddle1945_170802.txt  [jbritton]
  Rows parsed:    342  →  128 industries grouped
  Replaced:        89  existing entries
  Added:           39  new entries
  Catalog total:  172  entries

Commodity normalization:
  map-matched:    12
  auto-matched:   82
  free-text:      34

Unmatched commodities (add to commodity_map.yaml to normalize):
  "Freight - All Kinds"   18 industries
  "Hardware"               4 industries
  "Sleds"                  1 industry
  ...
```

---

## File Layout Changes

```
waybill_generator/
  importers/
    __init__.py          # new
    base.py              # new: ImportedRow, grouper, ID generation
    opsig.py             # new: OpSIG parser (.txt + .xls)
    jbritton.py          # new: JBritton parser
    normalizer.py        # new: commodity + car type normalization
  repository/
    catalog_repo.py      # updated: add replace_from_source()
  cli.py                 # updated: add import command

industry_database/
  commodity_map.yaml     # new: user-editable normalization overrides (starts empty)
  opsig_car_map.yaml     # new: pre-populated OpSIG car code → AAR map
  README.md              # new: format docs for all source files and maps

tests/
  test_importers.py      # new: parser, grouper, normalizer, re-import tests
```

---

## Testing

`tests/test_importers.py` covers:

- **Parser tests**: inline fixture rows → correct `ImportedRow` fields for both OpSIG and JBritton formats
- **Grouper tests**: multiple rows for same industry → one entry with correct `ships`/`receives`; blank-direction rows go into both lists when commodity is non-empty
- **Normalizer tests**: map lookup wins over auto-match; auto-match finds known commodities by substring; free-text fallback; `null` sentinel suppresses unmatched report entry
- **Car type tests**: OpSIG codes map to AAR codes; JBritton entries inherit from commodity; unmatched commodity → empty list
- **Re-import test**: `replace_from_source` called twice with different sets leaves `source: manual` entries and entries from other source files untouched

No integration tests against real `industry_database/` files.

---

## Dependencies

- `xlrd` — reading `.xls` files from OpSIG (added to `pyproject.toml`)
