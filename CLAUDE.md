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
uv sync --extra dev                             # install deps (creates .venv)
uv run waybill validate                         # check data files
uv run waybill generate --session session.yaml  # produce PDF
uv run waybill list cars
uv run waybill list waybills [--type LOADED]
uv run waybill serve [--port 8000] [--open]   # local web UI: edit data, review diff, save to YAML
uv run waybill convert-industry-db                # convert opsig/jbritton source files to JSON
uv run pytest                                   # run tests
uv run ruff check .                             # lint
```

## Industry Database Browser
`tools/industry-browser.html` is a standalone page for searching/filtering
the ~73k records produced by `convert-industry-db`. It reads directly from
`industry_database/{opsig,jbritton}/json/*.json` via `fetch()`, so it must
be served over HTTP (not opened via `file://`):

```bash
uv run waybill convert-industry-db   # if industry_database/ doesn't exist yet
uv run python -m http.server 8000    # from the repo root
```

Then open `http://localhost:8000/tools/industry-browser.html`.

The list of source files the page loads is hardcoded in its `SOURCE_FILES`
constant and needs a manual update if `convert-industry-db`'s source file
set ever changes.

## Web UI
`uv run waybill serve` runs a local web UI (binds 127.0.0.1) for creating, editing, and deleting
cars, waybills, locations (with industries), commodities, and railroads. Edits are **staged in
memory**; nothing is written until **Review & Save → Save to YAML**, which splices only the changed
records into `data/*.yaml` (comments, section headers, and untouched records stay byte-identical).
References already broken on disk are warnings; only newly broken references block saving.
Code lives in `waybill_generator/web/` (`YamlFile` → `WorkingCopy` → FastAPI routes + Jinja2/htmx
templates; htmx and Tom Select are vendored in `web/static/`). Spec:
`docs/superpowers/specs/2026-09-20-web-ui-design.md`. Phase 2 (card preview, session builder) is
not built yet.
A new record's id is generated for you (shown locked; it follows the fields it is derived from) —
click Edit to type your own. Ids can't be renamed afterwards. Record ids must be URL-safe (letters,
digits, `.`, `_`, `&`, `-`; not `new`/`fields`/`suggest-id`), and after hand-editing
`data/aar_codes.yaml` use Discard/Reload (no restart needed).

## Design Decisions
- YAML first; SQLite backend planned once schema stabilises
- No static assignments — session file is the mapping for each print job
- Car id convention: `{road}-{car_number}` e.g. `PRR-12345`
- Python 3.11+; Pydantic v2; ReportLab for PDF; Click for CLI
- Spec: `docs/superpowers/specs/2026-06-26-waybill-generator-design.md`
