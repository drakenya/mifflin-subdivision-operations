# Industry Database Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single static HTML page that loads all ~73,179 industry records produced by `convert-industry-db` and lets you search/filter them in a browser.

**Architecture:** One self-contained file, `tools/industry-browser.html` (inline CSS + vanilla JS, no framework, no build step). On load it `fetch()`s all 19 known JSON files from `industry_database/{opsig,jbritton}/json/`, merges them into one in-memory array, and renders a filterable, virtually-scrolled table. No changes to the Python package.

**Tech Stack:** Plain HTML5 / CSS / vanilla JavaScript (ES2017+, `async`/`await`, template literals — no transpilation, no dependencies).

**Spec:** `docs/superpowers/specs/2026-09-13-industry-db-browser-design.md`

## Global Constraints

- No build step, no JS framework, no npm/external dependency of any kind — everything inline in one HTML file.
- File lives at `tools/industry-browser.html` (tracked in git) — **not** inside `industry_database/`, which is gitignored (generated output only).
- The page must be served over HTTP (e.g. `python3 -m http.server` from the repo root); `fetch()` is blocked on `file://` origins, and the page must show a clear on-page message when that happens rather than fail silently.
- No automated test suite — this tool is outside `waybill_generator` and not covered by `pytest`. Every task is verified manually in a real browser (this plan uses the `claude-in-chrome` MCP tools for that; load them via `ToolSearch` with query `select:mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__tabs_close_mcp` before first use in each task).
- Total record count across all 19 source files is **73,179** — used as the expected value in verification steps below (re-confirm with a quick Python count if the underlying JSON has changed since this plan was written).

---

### Task 1: Page scaffold + data loading

**Files:**
- Create: `tools/industry-browser.html`

**Interfaces:**
- Produces: `allRecords` (module-level `let`, array of record objects — each has `name`, `city`, `state`, `railroad`, `car_types: string[]`, `ships: string[]`, `receives: string[]`, `notes`, `source_ref`, `source_file`, `source`, `year`, all strings/arrays), `async function loadAllData(): Promise<void>` (fetches all 19 files, populates `allRecords`, throws on any fetch/parse failure), `async function init(): Promise<void>` (page entry point, called once at the bottom of the script). DOM element ids: `status`, `file-note`, `count`, `filter-text`, `filter-state`, `filter-railroad`, `filter-source`, `filter-cartype`, `filter-commodity`, `cartype-options`, `commodity-options`, `table-container`, `spacer`, `rows-viewport`.

- [ ] **Step 1: Create the page**

Create `tools/industry-browser.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Industry Database Browser</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: system-ui, sans-serif;
    background: #fff;
    color: #111;
  }
  @media (prefers-color-scheme: dark) {
    body { background: #1a1a1a; color: #eee; }
  }
  header {
    padding: 12px 16px;
    border-bottom: 1px solid #ccc;
  }
  h1 { font-size: 16px; margin: 0 0 8px; }
  #controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
  }
  #controls input, #controls select {
    font-size: 13px;
    padding: 4px 6px;
  }
  #count { font-size: 12px; margin-left: auto; opacity: 0.75; white-space: nowrap; }
  #status {
    padding: 8px 16px;
    font-size: 13px;
  }
  #file-note {
    display: none;
    padding: 8px 16px;
    background: #ffe9a8;
    color: #442;
    font-size: 13px;
  }
  .row-grid {
    display: grid;
    grid-template-columns: 1.3fr 1fr 0.5fr 0.7fr 1.2fr 1.5fr 1.5fr 1.8fr 1.3fr;
    gap: 8px;
    padding: 0 16px;
    align-items: center;
  }
  #table-header {
    font-size: 12px;
    font-weight: 600;
    border-bottom: 1px solid #ccc;
    padding-top: 6px;
    padding-bottom: 6px;
  }
  #table-container {
    position: relative;
    overflow-y: auto;
    height: calc(100vh - 120px);
  }
  #spacer { position: relative; }
  #rows-viewport { position: absolute; top: 0; left: 0; right: 0; }
  .data-row {
    position: absolute;
    left: 0;
    right: 0;
    height: 32px;
    font-size: 12px;
    border-bottom: 1px solid #eee;
  }
  .data-row > div { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
</head>
<body>
<header>
  <h1>Industry Database Browser</h1>
  <div id="controls">
    <input id="filter-text" type="text" placeholder="Search all fields&hellip;" size="24">
    <select id="filter-state"><option value="">All states</option></select>
    <select id="filter-railroad"><option value="">All railroads</option></select>
    <select id="filter-source"><option value="">All sources</option></select>
    <input id="filter-cartype" type="text" list="cartype-options" placeholder="Car type&hellip;">
    <datalist id="cartype-options"></datalist>
    <input id="filter-commodity" type="text" list="commodity-options" placeholder="Commodity&hellip;">
    <datalist id="commodity-options"></datalist>
    <span id="count"></span>
  </div>
</header>
<div id="status">Loading industry database&hellip;</div>
<div id="file-note">
  This page loads data via <code>fetch()</code>, which browsers block on
  <code>file://</code> pages. Serve this repo over HTTP instead, e.g. from
  the repo root: <code>python3 -m http.server 8000</code>, then open
  <code>http://localhost:8000/tools/industry-browser.html</code>.
</div>
<div id="table-header" class="row-grid">
  <div>Name</div><div>City</div><div>State</div><div>Railroad</div>
  <div>Car Types</div><div>Ships</div><div>Receives</div><div>Notes</div><div>Source</div>
</div>
<div id="table-container">
  <div id="spacer">
    <div id="rows-viewport"></div>
  </div>
</div>
<script>
"use strict";

const SOURCE_FILES = [
  "../industry_database/opsig/json/DHCanada.json",
  "../industry_database/opsig/json/DHWest.json",
  "../industry_database/opsig/json/OpSigCANADA.json",
  "../industry_database/opsig/json/OpSigEST.json",
  "../industry_database/opsig/json/OpSigMWC.json",
  "../industry_database/opsig/json/OpSigSTH.json",
  "../industry_database/opsig/json/OpSigWEST.json",
  "../industry_database/opsig/json/OpSigWST.json",
  "../industry_database/jbritton/json/OpSig_baltimoreeastern1945_170906.json",
  "../industry_database/jbritton/json/OpSig_bobmartin_170802.json",
  "../industry_database/jbritton/json/OpSig_cnj1945_170906.json",
  "../industry_database/jbritton/json/OpSig_hbtm1942_170802.json",
  "../industry_database/jbritton/json/OpSig_maryland1945_170906.json",
  "../industry_database/jbritton/json/OpSig_nylb1945_170906.json",
  "../industry_database/jbritton/json/OpSig_prrmiddle1945_170802.json",
  "../industry_database/jbritton/json/OpSig_prrphiladelphia1945_170807.json",
  "../industry_database/jbritton/json/OpSig_prrpittsburgh1945_170807.json",
  "../industry_database/jbritton/json/OpSig_prrwilkesbarre1945_170807.json",
  "../industry_database/jbritton/json/OpSig_prrwilliamsport1945_170807.json",
];

let allRecords = [];

async function loadAllData() {
  const results = await Promise.all(
    SOURCE_FILES.map((path) =>
      fetch(path).then((res) => {
        if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
        return res.json();
      })
    )
  );
  allRecords = results.flat();
}

async function init() {
  try {
    await loadAllData();
  } catch (err) {
    document.getElementById("status").textContent = `Failed to load data: ${err.message}`;
    document.getElementById("file-note").style.display = "block";
    return;
  }
  document.getElementById("status").style.display = "none";
  document.getElementById("count").textContent =
    `${allRecords.length.toLocaleString()} records loaded`;
}

init();
</script>
</body>
</html>
```

- [ ] **Step 2: Start a local server for verification**

Run in background:

```bash
cd /Users/krolla/code/mifflin-subdivision-operations && python3 -m http.server 8000
```

Confirm `industry_database/opsig/json/` and `industry_database/jbritton/json/` exist with data (they're generated by `uv run waybill convert-industry-db`; run that first if the directory is missing).

- [ ] **Step 3: Verify data loads over HTTP**

Load `ToolSearch` with query `select:mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__tabs_close_mcp`, then:
1. Create a tab and navigate to `http://localhost:8000/tools/industry-browser.html`.
2. Wait briefly, then use `javascript_tool` to evaluate `document.getElementById('count').textContent`.
3. Expected: `"73,179 records loaded"` (or the current true total if the source data has changed — re-derive with a quick `python3` count over `industry_database/*/json/*.json` if this doesn't match).
4. Also evaluate `document.getElementById('status').style.display` — expected `"none"`.

- [ ] **Step 4: Verify the file:// failure path**

1. Navigate the same tab to `file:///Users/krolla/code/mifflin-subdivision-operations/tools/industry-browser.html`.
2. Evaluate `document.getElementById('file-note').style.display` — expected `"block"`.
3. Evaluate `document.getElementById('status').textContent` — expected to start with `"Failed to load data:"`.
4. Close the tab.

- [ ] **Step 5: Commit**

```bash
git add tools/industry-browser.html
git commit -m "feat: add industry database browser page scaffold and data loading"
```

---

### Task 2: Filter controls and filtering logic

**Files:**
- Modify: `tools/industry-browser.html`

**Interfaces:**
- Consumes: `allRecords` (from Task 1), DOM ids `filter-state`, `filter-railroad`, `filter-source`, `filter-cartype`, `filter-commodity`, `cartype-options`, `commodity-options`, `filter-text`, `count` (from Task 1).
- Produces: `filteredRecords` (module-level `let`, array), `function uniqueSorted(values: string[]): string[]`, `function populateSelect(selectEl, values)`, `function populateFilterOptions()`, `function getFilterValues()` (returns `{text, state, railroad, source, carType, commodity}`, all lowercase-trimmed strings except `state`/`railroad`/`source` which are exact select values), `function matchesFilters(record, filters): boolean`, `function applyFilters()` (recomputes `filteredRecords` and the `#count` text; ends by calling `updateSpacerHeight()`), `function updateSpacerHeight()`, `function debounce(fn, wait)`, `function wireControls()`.

- [ ] **Step 1: Add filter/matching logic and wire controls**

In `tools/industry-browser.html`, replace:

```javascript
let allRecords = [];
```

with:

```javascript
let allRecords = [];
let filteredRecords = [];
```

Then replace the `init()` function body's success branch:

```javascript
  document.getElementById("status").style.display = "none";
  document.getElementById("count").textContent =
    `${allRecords.length.toLocaleString()} records loaded`;
}
```

with:

```javascript
  document.getElementById("status").style.display = "none";
  populateFilterOptions();
  filteredRecords = allRecords.slice();
  applyFilters();
}
```

And add these functions immediately before `async function init() {`:

```javascript
function uniqueSorted(values) {
  return Array.from(new Set(values.filter((v) => v))).sort((a, b) =>
    a.localeCompare(b)
  );
}

function populateSelect(selectEl, values) {
  for (const v of values) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    selectEl.appendChild(opt);
  }
}

function populateFilterOptions() {
  const states = uniqueSorted(allRecords.map((r) => r.state));
  const railroads = uniqueSorted(allRecords.map((r) => r.railroad));
  const sources = uniqueSorted(allRecords.map((r) => r.source_file));
  const carTypes = uniqueSorted(allRecords.flatMap((r) => r.car_types || []));
  const commodities = uniqueSorted(
    allRecords.flatMap((r) => [...(r.ships || []), ...(r.receives || [])])
  );

  populateSelect(document.getElementById("filter-state"), states);
  populateSelect(document.getElementById("filter-railroad"), railroads);
  populateSelect(document.getElementById("filter-source"), sources);
  populateSelect(document.getElementById("cartype-options"), carTypes);
  populateSelect(document.getElementById("commodity-options"), commodities);
}

function getFilterValues() {
  return {
    text: document.getElementById("filter-text").value.trim().toLowerCase(),
    state: document.getElementById("filter-state").value,
    railroad: document.getElementById("filter-railroad").value,
    source: document.getElementById("filter-source").value,
    carType: document.getElementById("filter-cartype").value.trim().toLowerCase(),
    commodity: document.getElementById("filter-commodity").value.trim().toLowerCase(),
  };
}

function matchesFilters(record, filters) {
  if (filters.state && record.state !== filters.state) return false;
  if (filters.railroad && record.railroad !== filters.railroad) return false;
  if (filters.source && record.source_file !== filters.source) return false;

  if (filters.carType) {
    const carTypes = record.car_types || [];
    if (!carTypes.some((c) => c.toLowerCase().includes(filters.carType)))
      return false;
  }

  if (filters.commodity) {
    const commodities = [...(record.ships || []), ...(record.receives || [])];
    if (!commodities.some((c) => c.toLowerCase().includes(filters.commodity)))
      return false;
  }

  if (filters.text) {
    const haystack = [
      record.name,
      record.city,
      record.notes,
      record.source_ref,
      record.railroad,
      record.state,
      ...(record.car_types || []),
      ...(record.ships || []),
      ...(record.receives || []),
    ]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(filters.text)) return false;
  }

  return true;
}

function applyFilters() {
  const filters = getFilterValues();
  filteredRecords = allRecords.filter((r) => matchesFilters(r, filters));
  document.getElementById("count").textContent =
    `${filteredRecords.length.toLocaleString()} of ${allRecords.length.toLocaleString()} records`;
  updateSpacerHeight();
}

function updateSpacerHeight() {
  document.getElementById("spacer").style.height =
    `${filteredRecords.length * 32}px`;
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function wireControls() {
  document
    .getElementById("filter-text")
    .addEventListener("input", debounce(applyFilters, 150));
  for (const id of [
    "filter-state",
    "filter-railroad",
    "filter-source",
    "filter-cartype",
    "filter-commodity",
  ]) {
    document.getElementById(id).addEventListener("input", applyFilters);
  }
}
```

Finally, add a call to `wireControls();` as the first line inside `async function init() {` (before the `try`).

- [ ] **Step 2: Verify initial filtered count**

With the server from Task 1 still running (restart it if needed), navigate to `http://localhost:8000/tools/industry-browser.html` and evaluate `document.getElementById('count').textContent`. Expected: `"73,179 of 73,179 records"`.

- [ ] **Step 3: Verify free-text search**

Use `javascript_tool` to set the search box and dispatch an input event, then wait >150ms and check the count:

```javascript
const el = document.getElementById('filter-text');
el.value = 'ackley';
el.dispatchEvent(new Event('input'));
```

After a short wait, evaluate `document.getElementById('count').textContent`. Expected: `"6 of 73,179 records"` (6 records mention "ackley" across name/city/notes as of the current data — re-derive this number with a quick Python substring count over the JSON if the source data has changed).

- [ ] **Step 4: Verify dropdown filters and AND semantics**

1. Clear the text filter (`el.value = ''; el.dispatchEvent(new Event('input'))`).
2. Evaluate `document.getElementById('filter-state').options.length` — expected greater than 1 (real state values populated).
3. Set `document.getElementById('filter-state').value = 'IA'` and dispatch `input`; confirm the count narrows to fewer than 73,179 and greater than 0.
4. Additionally set `document.getElementById('filter-railroad').value = 'MSTL'` and dispatch `input`; confirm the count is less than or equal to the IA-only count (AND narrows further or stays the same, never increases).

- [ ] **Step 5: Commit**

```bash
git add tools/industry-browser.html
git commit -m "feat: add filter controls and search logic to industry browser"
```

---

### Task 3: Virtual-scroll results table

**Files:**
- Modify: `tools/industry-browser.html`

**Interfaces:**
- Consumes: `filteredRecords`, `applyFilters()`, `updateSpacerHeight()`, `wireControls()` (from Task 2), DOM ids `table-container`, `spacer`, `rows-viewport` (from Task 1).
- Produces: `const ROW_HEIGHT = 32`, `const OVERSCAN = 10`, `function escapeHtml(s): string`, `function renderRowHtml(record, index): string`, `function renderVisibleRows()`.

- [ ] **Step 1: Add row rendering and wire it into filtering + scrolling**

In `tools/industry-browser.html`, add near the top of the `<script>` block (right after `"use strict";`):

```javascript
const ROW_HEIGHT = 32;
const OVERSCAN = 10;
```

Add these functions immediately before `function applyFilters() {`:

```javascript
function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function renderRowHtml(record, index) {
  const top = index * ROW_HEIGHT;
  const cells = [
    record.name,
    record.city,
    record.state,
    record.railroad,
    (record.car_types || []).join(", "),
    (record.ships || []).join(", "),
    (record.receives || []).join(", "),
    record.notes,
    record.source_file,
  ];
  const cellsHtml = cells
    .map((c) => `<div title="${escapeHtml(c)}">${escapeHtml(c)}</div>`)
    .join("");
  return `<div class="data-row row-grid" style="top:${top}px">${cellsHtml}</div>`;
}

function renderVisibleRows() {
  const container = document.getElementById("table-container");
  const viewport = document.getElementById("rows-viewport");
  const scrollTop = container.scrollTop;
  const visibleCount = Math.ceil(container.clientHeight / ROW_HEIGHT);

  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const end = Math.min(
    filteredRecords.length,
    start + visibleCount + OVERSCAN * 2
  );

  let html = "";
  for (let i = start; i < end; i++) {
    html += renderRowHtml(filteredRecords[i], i);
  }
  viewport.innerHTML = html;
}
```

Then update `applyFilters()` to render after resizing the spacer — replace:

```javascript
  updateSpacerHeight();
}
```

with:

```javascript
  updateSpacerHeight();
  renderVisibleRows();
}
```

Finally, add a scroll listener inside `wireControls()` — add this line at the end of the function body (before its closing `}`):

```javascript
  document
    .getElementById("table-container")
    .addEventListener("scroll", () => requestAnimationFrame(renderVisibleRows));
```

- [ ] **Step 2: Verify only a small window of rows is ever in the DOM**

Reload `http://localhost:8000/tools/industry-browser.html` with no filters applied. Evaluate `document.querySelectorAll('.data-row').length`. Expected: a small number determined by viewport height (well under 100), never anywhere close to 73,179.

- [ ] **Step 3: Verify spacer height reflects the true result count**

Evaluate `document.getElementById('spacer').style.height`. Expected: `"2341728px"` (73,179 &times; 32) when unfiltered — recompute as `filteredRecords.length * 32` if the total has changed.

- [ ] **Step 4: Verify scrolling changes the rendered window without gaps or duplicates**

```javascript
const container = document.getElementById('table-container');
container.scrollTop = 500000;
container.dispatchEvent(new Event('scroll'));
```

Wait briefly (scroll handling is `requestAnimationFrame`-throttled), then evaluate the first `.data-row`'s inline `top` style and confirm it is close to `500000` (within one `ROW_HEIGHT` `OVERSCAN` window, i.e. `500000 - 10*32` to `500000 + 10*32`). Also confirm `document.querySelectorAll('.data-row').length` is still small (same order of magnitude as Step 2 — the window size doesn't grow after scrolling).

- [ ] **Step 5: Verify a filtered, non-scrolled result renders correctly**

```javascript
const el = document.getElementById('filter-text');
el.value = 'ackley';
el.dispatchEvent(new Event('input'));
```

Wait >150ms, then evaluate:

```javascript
Array.from(document.querySelectorAll('.data-row')).some(
  (row) => row.textContent.includes('Ackley Grain')
)
```

Expected: `true`.

- [ ] **Step 6: Commit**

```bash
git add tools/industry-browser.html
git commit -m "feat: add virtual-scroll rendering to industry browser table"
```

---

### Task 4: Documentation and final verification pass

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the finished `tools/industry-browser.html` from Tasks 1-3.
- Produces: no new code interfaces — documentation only.

- [ ] **Step 1: Document the tool in CLAUDE.md**

In `CLAUDE.md`, after the `## Key Commands` section's closing code fence, add:

```markdown
## Industry Database Browser
`tools/industry-browser.html` is a standalone page for searching/filtering
the ~73k records produced by `convert-industry-db`. It reads directly from
`industry_database/{opsig,jbritton}/json/*.json` via `fetch()`, so it must
be served over HTTP (not opened via `file://`):

\```bash
uv run waybill convert-industry-db   # if industry_database/ doesn't exist yet
python3 -m http.server 8000          # from the repo root
\```

Then open `http://localhost:8000/tools/industry-browser.html`.
```

(Use literal triple-backtick fences in the actual file, not the escaped `\```` shown here — they're escaped above only so this plan's own code block doesn't terminate early.)

- [ ] **Step 2: Run the full spec test plan end-to-end**

With the server still running, walk through all 5 verification items from the spec's "Testing / verification" section as one final combined pass (reload the page fresh for this, with no filters applied first):

1. Result count reads `73,179 of 73,179 records` unfiltered.
2. Free-text search for `"Ackley"` surfaces the MSTL "Ackley Grain" row (per Task 3, Step 5).
3. Each filter type individually narrows the count, and combining two narrows further or holds steady, never increases (per Task 2, Step 4 — repeat once more here including the car type and commodity filters, which Task 2 didn't individually re-verify since row rendering didn't exist yet).
4. Scroll through a large unfiltered result set at three different scroll positions (top, middle, near bottom) and confirm `.data-row` count stays small at each and `top` offsets stay plausible (per Task 3, Steps 2-4).
5. Opening via `file:///Users/krolla/code/mifflin-subdivision-operations/tools/industry-browser.html` shows the "serve over HTTP" guidance (per Task 1, Step 4).

Fix anything that fails before proceeding.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document industry database browser tool"
```
