# Industry Database Browser — Design

## Purpose

`uv run waybill convert-industry-db` produces ~73,000 flat industry
records (opsig + jbritton sources) as JSON under `industry_database/`
(gitignored — generated output, not source data). There is currently
no way to search or filter this data other than opening the raw JSON
files. This adds a small, standalone, static HTML tool to search and
filter across all sources in one table.

This is intentionally decoupled from the main waybill_generator
package: it's a viewer for pre-normalization source data, not a
feature of the car card / waybill generation pipeline. It reads the
same output that `convert-industry-db` already produces and adds
nothing to the Python package or its dependencies.

## Non-goals

- No build step, no JS framework, no npm dependency.
- No changes to the converters, data model, or CLI.
- No automated tests (it's outside the `waybill_generator` package and
  not covered by `pytest`); verified manually in-browser instead.
- Not a replacement for the eventual normalized industry catalog —
  this only searches the raw converter output.

## Location

`tools/industry-browser.html` — a tracked, single self-contained HTML
file (inline `<style>` and `<script>`, no external files). It lives
outside `industry_database/` deliberately: that directory is
gitignored (holds only generated JSON), so anything placed inside it
would not be tracked by git and could be lost on a clean checkout.

## Data loading

On page load, the script `fetch()`s all known JSON files:

```
industry_database/opsig/json/*.json      (8 files)
industry_database/jbritton/json/*.json   (11 files)
```

The file list is hardcoded in the page (the converter's set of source
files is stable; there's no directory-listing API available to a
static page). Each fetched array is concatenated into one in-memory
array of ~73k record objects — each record already carries a
`source_file` field from the converter, which the page also uses to
populate the "source" filter.

`fetch()` requires the page to be served over HTTP, not opened via
`file://` (browsers block `fetch` on `file://` origins). The page must
be served from the repo root so its relative paths to
`industry_database/` resolve, e.g.:

```
uv run python -m http.server 8000
# then open http://localhost:8000/tools/industry-browser.html
```

This requirement is documented both in a visible on-page note (shown
if a fetch fails, e.g. due to `file://`) and in `CLAUDE.md`.

A loading indicator is shown while all 19 fetches are in flight (total
~24MB); the UI is not interactive until all files have loaded and been
merged.

## Filtering / UI

Controls, top of page:

- **Free-text search** (text input): case-insensitive substring match
  tested against `name`, `city`, `notes`, `source_ref`, `railroad`,
  `state`, and the flattened contents of `car_types`, `ships`,
  `receives`.
- **State** (`<select>`): populated from the sorted unique set of
  `state` values found in the loaded data, plus an "All" option.
- **Railroad** (`<select>`): same pattern, from `railroad`.
- **Source** (`<select>`): same pattern, from `source_file`.
- **Car type** (`<input list="...">` + `<datalist>`): datalist options
  are the sorted unique set of all values across every record's
  `car_types` array. Matching a record means the filter value appears
  in that record's `car_types` list (substring match on each element,
  case-insensitive).
- **Commodity** (`<input list="...">` + `<datalist>`): same pattern,
  but matches if the filter value appears (substring, case-insensitive)
  in any entry of either `ships` or `receives`.

All active filters AND together. A result count ("N of 73,179 records")
is shown above the table and updates live.

Table columns: Name, City, State, Railroad, Car Types, Ships, Receives,
Notes, Source. Car Types/Ships/Receives render their arrays
comma-joined.

## Performance

Rendering all matching rows as plain `<table>` rows is too slow when
the result set is large (up to ~73k rows). The page implements a small
hand-rolled virtual scroll:

- A fixed row height (in px) is assumed for all rows.
- An outer scroll container has its inner height set to
  `filteredRows.length * rowHeight` (via a spacer element) so the
  scrollbar reflects the true result count.
- On scroll (and on filter change), only the rows currently in the
  viewport (plus a small overscan buffer) are rendered into the table
  body, absolutely positioned/offset to their true row position.

Filtering itself re-runs a single `Array.prototype.filter` pass over
the in-memory ~73k records on every change, debounced 150ms on the
free-text input (the select/datalist filters, being less frequent,
filter immediately). This is expected to comfortably run in well under
100ms per pass on modern hardware for flat objects with a handful of
string fields.

## Testing / verification

No automated test suite — manual verification only, since this tool
lives outside the `waybill_generator` Python package and its `pytest`
suite:

1. Serve and load the page; confirm the result count reads 73,179 (the
   full merged record count) with no filters applied.
2. Free-text search for `"Ackley"` returns the MSTL "Ackley Grain"
   industry (present in `OpSigMWC.json`).
3. Each filter type (state, railroad, source, car type, commodity)
   individually narrows the result count as expected, and combining
   two filters narrows further (AND semantics).
4. Scrolling through a large unfiltered result set renders correctly
   (no blank gaps, no duplicate rows) via the virtual-scroll list.
5. Opening the page directly via `file://` shows the documented
   "serve over HTTP" guidance rather than a silent blank page.
