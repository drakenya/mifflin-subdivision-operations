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
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
waybill validate                         # check data files
waybill generate --session session.yaml  # produce PDF
waybill list cars
waybill list waybills [--type LOADED]
```

## Design Decisions
- YAML first; SQLite backend planned once schema stabilises
- No static assignments — session file is the mapping for each print job
- Car id convention: `{road}-{car_number}` e.g. `PRR-12345`
- Python 3.11+; Pydantic v2; ReportLab for PDF; Click for CLI
- Spec: `docs/superpowers/specs/2026-06-26-waybill-generator-design.md`
