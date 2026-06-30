# Industry Catalog — Design Spec

**Date:** 2026-06-29
**Project:** mifflin-subdivision-operations
**Status:** Approved

---

## Overview

Two related improvements:

1. **Location model cleanup** — remove `subdivision` (unused) and add `railroad_id` + `on_layout` to properly represent off-layout and foreign-railroad industries.
2. **Industry reference catalog** — a searchable YAML file of real-world industries sourced from OpSIG and JBritton, with CLI commands to search and add entries to the operational data.

The catalog is a browsable reference, not a static import. You dip into it whenever composing a new operating session and need a realistic source or destination for a waybill.

---

## Data Model Changes

### Location (updated)

Remove `subdivision`. Add `railroad_id` and `on_layout`.

```python
class Location(BaseModel):
    id: str
    name: str
    state: str = "PA"
    railroad_id: str | None = None   # None = PRR (home road); set for foreign RRs
    on_layout: bool = False           # True = physically present on the layout
    industries: list[Industry] = []
```

`Industry` is unchanged.

**Migration:** Remove all `subdivision` fields from `data/locations.yaml` and `tests/fixtures/locations.yaml`. Add `on_layout: true` to locations that are physically on the layout (Mifflin Subdivision: BRN, MCV, MIF, MFT, LEW, LJ). Off-layout locations (ALT, HBG, PGH) get `on_layout: false` (the default).

---

## Industry Catalog

### File: `data/industry_catalog.yaml`

Purely reference data — not loaded by the repository for waybill generation. Only read by the `waybill search` and `waybill add-industry` commands.

```yaml
- id: cat-001
  name: Clearfield Coal & Coke Co.
  city: Clearfield
  state: PA
  railroad_id: PRR
  source: opsig
  source_file: freight-forwarders-pa.csv
  source_ref: "OPSIG-4872"          # optional — row/record id in source file
  ships:
    - coal
  receives: []
  car_types:                         # AAR codes for cars this industry uses
    - HM
    - HT
  notes: Bituminous coal, Clearfield County
```

### CatalogIndustry model (new)

```python
class CatalogIndustry(BaseModel):
    id: str
    name: str
    city: str
    state: str = "PA"
    railroad_id: str | None = None
    source: str                      # opsig | jbritton | manual
    source_file: str                 # specific file or article within source
    source_ref: str | None = None    # optional row/record pointer
    ships: list[str] = []            # commodity ids or free-text
    receives: list[str] = []
    car_types: list[str] = []        # AAR codes
    notes: str | None = None
```

### CatalogRepository (new)

A lightweight loader separate from `BaseRepository` — reads `industry_catalog.yaml` and provides search/filter:

```python
class CatalogRepository:
    def search(
        self,
        keyword: str | None = None,
        commodity: str | None = None,
        car_type: str | None = None,
        railroad: str | None = None,
        ships: bool = False,
        receives: bool = False,
        source: str | None = None,
        limit: int = 20,
    ) -> list[CatalogIndustry]: ...

    def get(self, id: str) -> CatalogIndustry: ...
```

Search matches `keyword` against name, city, and notes (case-insensitive substring). `commodity` combined with `--ships` / `--receives` filters the `ships` or `receives` lists.

---

## CLI Commands

### `waybill search`

```
waybill search [OPTIONS]

Options:
  --commodity TEXT    commodity id or keyword
  --car-type TEXT     AAR code (e.g. HM, XM, GB)
  --railroad TEXT     railroad id (e.g. PRR, NYC)
  --ships             match only industries that ship the commodity
  --receives          match only industries that receive it
  --source TEXT       filter by source (opsig, jbritton, manual)
  --keyword TEXT      free-text search on name, city, notes
  --limit INT         max results (default 20)
```

Output: compact table — id, name, city/state, railroad, ships, receives, source/file.

### `waybill add-industry <catalog-id>`

```
waybill add-industry CATALOG_ID [--preview]
```

**Workflow:**

1. Load and display the catalog entry in full.
2. Check `locations.yaml` for existing locations matching city + state + railroad_id:
   - **One match:** offer to add the industry to that location.
   - **Multiple matches:** list matching location ids and prompt the user to pick one.
   - **No match:** propose a new `Location` entry (auto-generate an id from city initials) containing the industry.
3. Display a preview of the exact YAML block that would be written.
4. Prompt:
   - **Y** — write to `locations.yaml`
   - **E** — open proposed block in `$EDITOR`, then write on save
   - **N** — cancel without changes
5. On confirm, append or update `locations.yaml` and report the new industry id.

`--preview` skips the prompt and just shows steps 1–3.

After adding an industry, create the corresponding waybill manually in `waybills.yaml` using the new industry id as `shipper_id` or `consignee_id`.

---

## File Layout Changes

```
data/
  locations.yaml          # updated: remove subdivision, add railroad_id + on_layout
  industry_catalog.yaml   # new: reference catalog
waybill_generator/
  models/
    location.py           # updated: remove subdivision, add railroad_id + on_layout
    catalog.py            # new: CatalogIndustry model
  repository/
    catalog_repo.py       # new: CatalogRepository
  cli.py                  # updated: add search + add-industry commands
tests/
  fixtures/
    locations.yaml        # updated: remove subdivision
    industry_catalog.yaml # new: fixture with a few sample entries
  test_catalog.py         # new: search filter tests
  test_models.py          # updated: remove subdivision assertions
```

---

## Future: Mass Import from OpSIG / JBritton

> **Stub — separate sub-project.** The catalog is designed to support bulk population, but the import tooling is out of scope for this spec.

Planned: an `import` command (or standalone script) that reads a source file from OpSIG or JBritton, maps fields to `CatalogIndustry`, normalizes commodity names and car types against the project's commodity/AAR lists, deduplicates against existing catalog entries, and appends new records to `industry_catalog.yaml` with a review step before writing.

Source format, normalization rules, and deduplication strategy will be designed once the source file structures are known.

---

## Key Design Decisions

- **Catalog is read-only reference data** — `CatalogRepository` is separate from `BaseRepository` and never participates in waybill generation. No risk of catalog entries appearing on cards.
- **YAML-first catalog** — consistent with the rest of the project. Easy to hand-edit, grows entry by entry. If the catalog outgrows YAML (hundreds of entries), migrating to SQLite is the same pattern already planned for operational data.
- **`add-industry` writes to locations.yaml, not waybills.yaml** — adding an industry to operational data and creating a waybill for it are two distinct acts. Keeping them separate avoids half-finished waybills with missing fields.
- **`subdivision` removed** — was never consumed by layouts, renderer, or CLI. `on_layout` replaces its only practical use (distinguishing layout vs off-layout).
