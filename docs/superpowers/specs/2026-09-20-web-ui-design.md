# Web UI for Data Entry, Preview, and Generation — Design

## Purpose

All car, waybill, location, commodity, and railroad data is currently
hand-edited in `data/*.yaml`. Cross-references (`consignee_id`,
`commodity_id`, industry ids) must be typed from memory, and there is no
way to see a card until a session file is written and `waybill generate`
is run.

This adds a local web UI, started with `uv run waybill serve`, for:

1. **Phase 1 — data entry:** create, edit, and delete records with
   validated, searchable forms.
2. **Phase 2 — preview and generate:** preview a single card, build a
   session, and generate the PDF.

YAML stays the source of truth. Edits are staged in memory and written
back to YAML only when the user chooses, so the CLI
(`waybill generate --session …`) can always regenerate the same output.

## Non-goals

- No auth, multi-user support, or network exposure (binds `127.0.0.1`).
- No live sync: no file watching, no draft autosave across restarts.
  Unsaved edits are lost if the server stops.
- No record renaming (ids are immutable after creation), no undo
  history, no per-file partial save.
- No JS build step or npm dependency.
- Out of scope entities: `industry_catalog.yaml`, `aar_codes.yaml`,
  `car_type_map.yaml` (reference data, still hand-edited), the
  OpSIG/JBritton browser, and the roster XLSX importer.
- No change to the SQLite-backend plan; `BaseRepository` is unchanged.

## Stack

FastAPI + Jinja2 + htmx, served by uvicorn. Server-rendered HTML; all
state and validation live on the server (Pydantic v2, already the model
layer). htmx swaps HTML fragments (e.g. the waybill type change).
Searchable dropdowns use Tom Select (vanilla JS). htmx and Tom Select
are vendored into `waybill_generator/web/static/` so the tool works
offline. New dependencies (added to the main `dependencies`, matching
how `openpyxl`/`xlrd` are handled): `fastapi`, `uvicorn`, `jinja2`,
`python-multipart`, `ruamel.yaml`. Dev: `httpx` (for `TestClient`).

Considered and rejected: JSON API + client-side SPA (validation in two
places), NiceGUI (less layout/preview control, heavier dependencies),
Streamlit (rerun model poor for multi-record CRUD), React/Vite (build
chain overkill for a single-user local tool).

## Architecture

```
Browser (htmx) ⇄ FastAPI routes ⇄ WorkingCopy ⇄ YamlStore ⇄ data/*.yaml
                                       ↓
                        (phase 2) resolve_card → render_pdf
```

New package `waybill_generator/web/`. `YamlRepository`, the CLI
commands, and the layouts are unchanged, except for the `resolve_card`
extraction in phase 2.

### `YamlStore`

Round-trip read/write of each data file with `ruamel.yaml`, preserving
comments and formatting. Records each file's content hash at load time.
Can produce a unified diff between the working copy and the on-disk
text. Saving **merges** changes into the round-tripped document
(update changed entries, append new, remove deleted) rather than
re-dumping, so untouched entries and comments stay byte-identical and
`git diff` shows only what changed. Writes go to temp files first, then
are renamed into place.

### `WorkingCopy`

Mutable in-memory typed records (cars, locations with nested
industries, commodities, railroads, waybills), loaded through
`YamlStore`. Implements the `BaseRepository` read interface so
renderer and resolve code work on it unchanged. Adds:

- `apply(kind, record)` / `delete(kind, id)` mutations
- per-file dirty tracking and a change summary (count, per-record
  new/modified/deleted state)
- reference-integrity checks: deleting a record that others reference
  is blocked and returns the list of referencing records
- `validate()`: the same cross-reference checks as `waybill validate`,
  shared rather than duplicated

### Form generation

One generic helper walks a Pydantic model's `model_fields` and emits
inputs. A small explicit table maps reference fields to the collection
they point at (e.g. `consignee_id` → industries, `commodity_id` →
commodities, `routing` → railroads); those render as searchable
pickers. Choosing a waybill type re-renders the field block for that
type via htmx. Adding a waybill type to the model yields a working form
without extra UI code; a parametrized test covers every type and fails
if a reference field has no picker mapping.

### Searchable pickers

Every reference field is a type-to-search Tom Select picker (single or
multi-select with chips), with keyboard navigation. Option lists are
small (~15 locations, ~11 commodities), so all options are embedded in
the page and filtered client-side. Search matches name, id, city,
track (industries), AAR code (commodities), road/number/type (cars).
Rows show enough context to distinguish similar names (name, id, city,
track). On LOADED waybills, once a commodity is chosen, industries
whose `ships`/`receives` list includes it are ranked first under a
"Receives/Ships <commodity>" group; other industries remain listed
below (ranked, never filtered, so incomplete `ships`/`receives` data
never blocks entry). Tom Select can switch to server-side loading if
lists ever grow large.

## Screens

**Global:** top bar with tabs (Cars, Waybills, Locations, Commodities,
Railroads, Session) and an unsaved-changes indicator with **Review &
Save** and **Discard** (re-reads all files from disk, dropping every
staged change). **Apply** stages an edit in the working copy;
**Save to YAML** writes to disk. The two are named distinctly on
purpose.

**Phase 1**

- **List pages:** search box; the waybill list also has a type filter
  (parity with `list waybills --type`); new/modified rows are marked;
  click a row to edit; **New** opens an empty form.
- **Edit forms:** generated from the models; Pydantic errors are shown
  beside the field. Suggested ids: `{road}-{car_number}` for cars,
  the existing `_generate_location_id` / `_generate_industry_id`
  helpers from `cli.py` for locations/industries.
- **Locations:** the location form embeds an industries table
  (add/edit/remove); `ships`/`receives` are commodity multi-selects.
- **Review & Save:** runs `validate()` (errors block saving); shows a
  per-file YAML diff; **Save to YAML** writes all changed files. If a
  file's hash differs from load time, a warning offers **Reload from
  disk** (re-reads that file, dropping its staged edits) or
  **Overwrite anyway**.

**Phase 2**

- **Card preview:** pick car, waybill, and layout; an `<iframe>` shows
  a one-card PDF rendered from the working copy (unsaved edits
  included). A refresh button re-renders; no live auto-update.
- **Session builder:** table of (car, waybill) rows with add, remove,
  reorder; load an existing `sessions/*.yaml`; **Generate PDF** writes
  to the output directory like the CLI and opens it; **Save session**
  writes `sessions/<name>.yaml` so the CLI reproduces the same PDF.
  If a session references records that exist only in the working copy,
  the page warns that the CLI cannot regenerate it until Save to YAML.

Wireframe mockups from the design session are kept locally under
`.superpowers/brainstorm/` (untracked) and are illustrative only; some
industry names in them are abbreviated.

## Shared refactor: `resolve_card`

The step in `cli.py` `generate` (lines ~85–121) that looks up the
railroad and fills a LOADED waybill's resolved display fields
(`to_city`, `consignee_name`, …) moves into a `resolve_card(repo,
car_id, waybill_id)` function that returns a `(car, waybill, railroad)`
triple. The CLI and the web preview both call it. Existing CLI
behavior and tests are unchanged.

## Error handling

- **Form input:** Pydantic `ValidationError` is mapped to fields and
  the form is re-rendered; nothing is applied until clean.
- **Referential integrity:** blocked deletes list their referencers;
  Save is blocked by `validate()` errors.
- **Startup:** a YAML file that fails to parse stops the server with
  the file and line; it never starts with an empty dataset.
- **Save:** temp-file-then-rename; a failure before the renames leaves
  data untouched. Renames are not atomic across files; if one fails
  partway the UI reports which files were written.
- **Disk conflict:** hash check at save time (see Review & Save).
- **Preview:** render errors display as text in the preview pane.

## Testing

pytest and ruff, against copies of `tests/fixtures`:

- `YamlStore`: golden round-trip (comments and untouched entries
  byte-identical after add/update/delete); conflict detection; temp
  file cleanup on failure.
- `WorkingCopy`: apply/delete, dirty tracking, reference blocking,
  `BaseRepository` contract, `validate()`.
- Form helper: parametrized over all waybill types, including the
  picker-mapping completeness check.
- Routes (`TestClient`): list → edit → apply → review → save on a temp
  fixture copy; preview endpoint returns `application/pdf` (`%PDF`).
- `resolve_card`: new unit tests; `tests/test_cli.py` must still pass
  unchanged.
- Browser behavior (typeahead, htmx swaps) is not in the suite; smoke
  tested manually per phase with scratch Playwright + Chromium.

## Build order

Two implementation plans, one per phase; each is squashed to a single
commit on `main`.

**Phase 1:** (1) `YamlStore`; (2) `WorkingCopy`; (3) app shell, list
pages, generic form helper, proven on cars, commodities, railroads;
(4) waybills with type swap and pickers; (5) locations with nested
industries editor; (6) Review & Save. Add `waybill serve` to
CLAUDE.md's Key Commands.

**Phase 2:** (1) extract `resolve_card`; (2) card preview; (3) session
builder with Generate and Save session.

## Open items to verify during implementation

- `render_pdf` currently takes an output path; single-card preview
  needs it to accept an in-memory buffer, or falls back to a temp file.
- Nested location/industry merge in `YamlStore` (industries live inside
  a location document) needs its own round-trip test cases.
