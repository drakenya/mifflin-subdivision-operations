# Industry Database JSON Conversion — Design

## Purpose

Convert the raw OpSIG (`.xls`/`.txt`) and JBritton (`.txt`) industry source
files under `industry_database/` into structured JSON, one JSON file per
source file, so the data is parsable by future tools without needing a
custom line/column parser each time.

This is **pure format conversion**: it transcribes rows into structured
records and groups rows that clearly describe the same industry/station.
It does **not** normalize commodities or car types, and it does not write
to `data/industry_catalog.yaml` — that logic (the mass-import feature) was
deliberately reverted and will be redesigned separately against this JSON
as its input, once this conversion exists.

## Background

`industry_database/opsig/` and `industry_database/jbritton/` hold raw
source files (tab-delimited `.txt`, legacy Excel `.xls`) documenting PRR
industries and stations, sourced from OpSIG (Operations Special Interest
Group) and JBritton (pennsyrr.com). A prior importer
(commit `b69b375`, reverted in commit `b072b85`) parsed these directly
into the catalog with commodity/car-type normalization baked in. That
feature is being redesigned; this spec covers only the reusable parsing
step it depended on.

Both source formats share the same 10-column layout (0-indexed):

| col | opsig | jbritton |
|-----|-------|----------|
| 0 | year | year |
| 1 | name | name |
| 2 | city | city |
| 3 | state | state |
| 4 | railroad | railroad |
| 5 | direction (S/R) | direction (S/R) |
| 6 | commodity | commodity |
| 7 | notes | (unused) |
| 8 | (unused) | notes |
| 9 | car_types (comma-separated) | source_ref |

## Architecture

New package `waybill_generator/converters/` (kept separate from the
deleted `importers/` package — this only transcribes files, it doesn't
touch the catalog):

- **`base.py`**
  - `RawRow` dataclass: `year, name, city, state, railroad, direction, commodity, notes, car_types: list[str], source_ref`
  - `parse_tab_line(line: list[str], notes_col: int, source_ref_col: int | None, car_types_col: int | None) -> RawRow | None` — shared column-extraction logic; returns `None` if `name` is blank
  - `group_by_industry(rows: list[RawRow]) -> list[dict]` — groups rows by `(name, city, state, railroad)`, splitting `commodity` into `ships`/`receives` by the `direction` column (`S` → ships, `R` → receives, blank/other → both), deduplicating within each list, and merging `car_types` and the first non-blank `notes`/`source_ref` seen
  - `to_json_records(groups: list[dict], source: str, source_file: str) -> list[dict]` — stamps `source` and `source_file` onto each group and produces the final JSON-ready record shape (see schema below)

- **`opsig.py`**
  - `parse_opsig(filepath: Path) -> list[RawRow]` — dispatches on suffix: `.txt` read as tab-delimited `latin-1`; `.xls` read via `xlrd` (reintroducing this dependency, removed when the prior importer was reverted, since these are legacy pre-2007 `.xls` files that `openpyxl` cannot open)

- **`jbritton.py`**
  - `parse_jbritton(filepath: Path) -> list[RawRow]` — tab-delimited `latin-1`, `.txt`/`.TXT`

## JSON Record Schema

One JSON array per source file, each element:

```json
{
  "name": "Sunbury Lumber Co.",
  "city": "Sunbury",
  "state": "PA",
  "railroad": "PRR",
  "year": "1945",
  "ships": ["lumber"],
  "receives": [],
  "car_types": ["FM", "FL"],
  "source_ref": "",
  "notes": "",
  "source": "jbritton",
  "source_file": "OpSig_prrmiddle1945_170802.txt"
}
```

All fields are always present — `car_types` is `[]` for JBritton records,
`source_ref` is `""` for OpSIG records — so downstream consumers don't
need to branch on `source` to know which keys exist.

## CLI

New command on the existing `waybill` Click app:

```
uv run waybill convert-industry-db [--industry-db PATH]
```

- Defaults `--industry-db` to `./industry_database`
- Walks `<industry-db>/opsig/*.xls`, `<industry-db>/opsig/*.txt`, and
  `<industry-db>/jbritton/*.txt` (case-insensitive extension match, to
  catch files like `OpSig_hbtm1942_170802.TXT`)
- For each file: parse → group → write pretty-printed, sorted-key JSON to
  a sibling `json/` subfolder, e.g.
  `industry_database/opsig/OpSigWEST.xls` → `industry_database/opsig/json/OpSigWEST.json`
- Re-running overwrites existing JSON files — no idempotency bookkeeping
  needed, since this never touches the catalog or any other stateful file
- Prints a per-file summary: rows parsed, industries grouped, rows skipped
  (missing name)
- Files with unrecognized extensions in the source folders are skipped
  with a warning, not an error

## Error Handling

- Rows with a blank `name` column are skipped (matches prior importer
  behavior) and counted per file so gaps are visible in the CLI summary
  rather than silent
- A source file that fails to parse entirely (e.g. corrupt `.xls`) is
  reported as an error for that file; the command continues processing
  remaining files rather than aborting the whole run

## Testing

- `base.py`: unit tests for `parse_tab_line` (short lines padded, blank
  name skipped) and `group_by_industry` (multiple rows merge into one
  record, ships/receives dedup, direction blank goes to both lists)
- `opsig.py` / `jbritton.py`: unit tests using small fixture strings for
  the `.txt` path; the `.xls` path is tested by monkeypatching
  `xlrd.open_workbook` to return a fake workbook object (`nrows`/`ncols`/
  `cell_value`) rather than checking in a real `.xls` fixture — the real
  files are multi-megabyte and `xlrd` can't write new ones to generate a
  small fixture
- CLI test: run `convert-industry-db` against a temp directory seeded
  with a couple of fixture files, assert the `json/` output files exist
  and match the expected record shape

## Known Caveats (discovered during implementation)

Real-data verification against the files actually present in
`industry_database/` surfaced several assumptions in this design that
don't hold uniformly. Recorded here so they don't need to be
rediscovered:

- **Two `.xls` column layouts exist, not one.** `OpSigCANADA.xls` and
  `OpSigWEST.xls` are 10 columns, matching the table above. `DHCanada.xls`
  and `DHWest.xls` are **11 columns** — a leading `List` column (values
  are only ever `"C"` or `"W"`, a region tag) shifts every other field
  right by one. The converter auto-detects this via `ws.ncols` and folds
  the `List` value into the `notes` field as a `[list: C]`/`[list: W]`
  prefix rather than dropping it or expanding the JSON schema.
- **Every real `.xls` file has a header row at index 0** (e.g.
  `["ERA", "INDUSTRY/COMPANY NAME", "CITY", ...]`); the converter skips
  it unconditionally. The `.txt` files (both OpSIG and JBritton) do NOT
  have header rows — verified directly against every real `.txt` file
  in the repo, so the header skip is `.xls`-only.
- **`OpSigCANADA.xls`/`OpSigWEST.xls`'s columns 7 and 9 are not really
  "notes"/"car_types".** Their real headers show column 7 is `STTC`
  (a shipping commodity code) and column 9 is `CONTRIBUTOR` (the
  initials of whoever submitted the row to OpSIG, e.g. `"butts"`). This
  is a deliberate, deferred mismapping: the raw values are preserved
  faithfully, just under field names that don't describe them for
  `.xls`-sourced records. Revisit if a consumer needs the true STCC/
  contributor semantics.
- **`DHCanada.xls` contains 3 sheets; only sheet 0 (`"All"`) is read.**
  Verified that sheet 0 already contains the union of the other two
  sheets (`"Canada"`, `"West"`) for this file, so nothing is lost today.
  The converter warns (via Python's `warnings` module) whenever a
  workbook has more than one sheet and a non-zero sheet holds data, so
  a future file where this assumption doesn't hold will be visible
  rather than silently dropped.
- **`DHWest.xls` is a full duplicate of `DHCanada.xls`'s `"W"`-tagged
  rows.** Every one of `DHWest.xls`'s ~7,800 industries (matched on
  `name`/`city`/`state`/`railroad`) already appears in `DHCanada.xls`'s
  output. A consumer that concatenates all `opsig/json/*.json` files
  without deduping on `(name, city, state, railroad)` will double-count
  these industries.
- **`year` values are not normalized and are heterogeneous across
  files** — some OpSIG files use 2-digit "era" codes (`"90"`, `"48"`),
  others use full 4-digit years (`"1996"`, `"1945"`). This is expected
  under "pure format conversion, no normalization" — a downstream
  consumer needing consistent years must handle both forms itself.

## Dependencies

Reintroduce `xlrd>=2` in `pyproject.toml` (removed in the revert; needed
again here for legacy `.xls` parsing).
