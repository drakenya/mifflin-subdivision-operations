# Web UI Phase 1 (Data Entry) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web UI (`uv run waybill serve`) for creating, editing, and deleting cars, waybills, locations (with industries), commodities, and railroads, with searchable dropdowns, staged edits, and an explicit Review & Save that writes minimal diffs back to the YAML files.

**Architecture:** FastAPI + Jinja2 + htmx serve server-rendered pages over a `WorkingCopy` (an in-memory, mutable copy of the data files that implements `BaseRepository`). Edits are staged; nothing touches disk until Save. `YamlFile` saves by splicing only the changed records into each file's original text, so untouched records, section-header comments, and formatting stay byte-identical. Pickers are Tom Select (vendored); the waybill type swap uses htmx.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, python-multipart, PyYAML (existing), Pydantic v2 (existing), htmx 2.0.4 + Tom Select 2.4.3 (vendored JS), pytest + `httpx2` (dev).

**Spec:** `docs/superpowers/specs/2026-09-20-web-ui-design.md` (this plan implements **Phase 1**; Phase 2 — `resolve_card`, card preview, session builder — gets its own plan).

> **Verification note.** Every code block below was built task-by-task in a scratch copy of the repository and run: the suite grew from 185 to 275 passing tests, `ruff check` is clean on all new files, and a 15-check headless-Chromium smoke test (Task 9) passed against `waybill serve`. If a step's expected output differs from what you see, investigate — don't loosen the test.

## Global Constraints

- Python 3.11+ (`requires-python = ">=3.11"`); Pydantic v2; PyYAML for YAML. **Do not add `ruamel.yaml`** — it was evaluated and rejected (see spec, `YamlStore`).
- New main dependencies, exactly: `fastapi>=0.115`, `uvicorn>=0.30`, `jinja2>=3.1`, `python-multipart>=0.0.9`. New dev dependency: `httpx2>=2`.
- No JS build step and no npm dependency in the repo. htmx and Tom Select are vendored into `waybill_generator/web/static/`.
- The server binds `127.0.0.1` only. No authentication.
- YAML files stay the source of truth. Nothing is written to `data/` until the user chooses **Save to YAML**. Record ids are immutable once created.
- Save is blocked only by broken references that staged edits *introduced*. References already broken in the files on disk are non-blocking warnings.
- `YamlRepository`, the layouts, the renderer, and existing CLI commands are unchanged. The only change to `cli.py` is the new `serve` command.
- Tests are hermetic: they use copies of `tests/fixtures/`, never `data/`.
- `ruff check waybill_generator/web tests/web` must pass. The repository already has 52 unrelated ruff errors: do not fix or add to them (`cli.py` must not gain any).
- Work on `main` (no worktree). Commit after each task with explicit `git add <paths>` — never `git add -A` / `git add .` (`.superpowers/` is untracked and must stay out). Commit messages use a conventional prefix (`feat:`, `test:`, `docs:`) and end with `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Keep the user-visible wording used in the spec: **Apply** stages an edit; **Save to YAML** writes to disk; **Discard** re-reads everything from disk.

## Corrections to the approved spec discovered while planning

The spec file has been amended to match; they are listed here so nobody re-introduces the old design.

1. **YAML mechanism.** `ruamel.yaml` rewrites every nested list in these files (they indent nested lists under their key while top-level records start at column 0). `YamlFile` instead splits a file into per-record text and re-emits only changed keys.
2. **Validation.** `waybill validate` only checks that files load — it does no cross-reference checking. The reference checks in `WorkingCopy.validate()` are new, cover only fields in an explicit table, and are relative to a baseline of what is already broken on disk.
3. **Loose data.** `routing` lists hold free-form junction/railroad codes (`LJ`, `NYC`, `B&M`) and TEMPORARY waybills' locations are free text (`"Burnham PA"`), so neither is a reference. The only genuinely dangling references today are `commodity_id: produce` on the two perishable waybills.

## File Structure

| File | Responsibility |
|---|---|
| `waybill_generator/web/yaml_store.py` | `YamlFile`: parse a flat record file into text segments; render an edited record list back with minimal diffs; hash/conflict check; temp-file staging |
| `waybill_generator/web/references.py` | The reference table (which fields point at which collection), `Ref`, `iter_refs`, `WAYBILL_CLASSES` |
| `waybill_generator/web/working_copy.py` | `WorkingCopy(BaseRepository)`: staged edits, change tracking, reference-integrity checks, baseline-relative validation, diffs, save/discard/reload |
| `waybill_generator/web/forms.py` | Generic form building/parsing driven by the Pydantic models; picker option lists |
| `waybill_generator/web/entities.py` | The five collections' list/search/edit settings; waybill summaries; id suggestions |
| `waybill_generator/web/context.py` | Shared request helpers: templates, `render`, `redirect`, `form_page` |
| `waybill_generator/web/routes_records.py` | List / create / edit / delete for any collection, and the type-swap fragment |
| `waybill_generator/web/routes_industries.py` | Add / edit / remove the industries nested under a location |
| `waybill_generator/web/routes_review.py` | Review, Save, Discard, Reload |
| `waybill_generator/web/app.py` | `create_app(data_path)` |
| `waybill_generator/web/templates/*.html`, `static/*` | Pages, stylesheet, `pickers.js`, vendored htmx / Tom Select |
| `waybill_generator/cli.py` | New `serve` command only |
| `tests/web/*` | Hermetic tests per module |

---

### Task 1: Dependencies, package skeleton, vendored assets

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (regenerated)
- Create: `waybill_generator/web/__init__.py` (empty), `tests/web/__init__.py` (empty), `tests/fixtures/aar_codes.yaml`
- Create: `waybill_generator/web/static/htmx.min.js`, `tom-select.complete.min.js`, `tom-select.default.min.css`, `VENDORED.md`

**Interfaces:**
- Produces: importable package `waybill_generator.web`; test package `tests.web`; the fixture `tests/fixtures/aar_codes.yaml` (codes XM, HM, GB, LO); the three vendored assets.

- [ ] **Step 1: Record the base commit and commit any pending design docs**

```bash
git rev-parse HEAD            # note this hash: Task 9 squashes back to it
git status --short            # expect only `?? .superpowers/` (and, if not yet committed, the spec + this plan)
```

If `docs/superpowers/specs/2026-09-20-web-ui-design.md` or this plan show as modified/untracked, commit them first (the base for the squash is the commit *after* this one):

```bash
git add docs/superpowers/specs/2026-09-20-web-ui-design.md \
  docs/superpowers/plans/2026-09-20-web-ui-phase-1.md
git commit -m "$(cat <<'EOF'
docs: correct web UI spec and add phase 1 implementation plan

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 2: Add the dependencies to `pyproject.toml`**

In `[project] dependencies`, after `"xlrd>=2",` add four lines; in `[project.optional-dependencies]`, extend `dev`:

```toml
dependencies = [
    "click>=8",
    "pydantic>=2",
    "reportlab>=4",
    "pyyaml>=6",
    "openpyxl>=3",
    "xlrd>=2",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "httpx2>=2"]
```

- [ ] **Step 3: Create the skeleton and the aar-codes fixture**

```bash
mkdir -p waybill_generator/web/static waybill_generator/web/templates tests/web
: > waybill_generator/web/__init__.py
: > tests/web/__init__.py
```

Create `tests/fixtures/aar_codes.yaml` (the picker option list for car types; the real file lives at `data/aar_codes.yaml`):

```yaml
- code: XM
  name: Box Car
- code: HM
  name: Open Hopper
- code: GB
  name: Gondola
- code: LO
  name: Covered Hopper
```

- [ ] **Step 4: Vendor htmx and Tom Select**

```bash
cd waybill_generator/web/static
curl -fsSL -o htmx.min.js https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js
curl -fsSL -o tom-select.complete.min.js https://cdn.jsdelivr.net/npm/tom-select@2.4.3/dist/js/tom-select.complete.min.js
curl -fsSL -o tom-select.default.min.css https://cdn.jsdelivr.net/npm/tom-select@2.4.3/dist/css/tom-select.default.min.css
cd ../../..
wc -c waybill_generator/web/static/*
```

Expected sizes: `htmx.min.js` ≈ 50 KB, `tom-select.complete.min.js` ≈ 50 KB, `tom-select.default.min.css` ≈ 10 KB. If any file is tiny (an HTML error page) or `curl` fails, stop and report — do not commit.

Create `waybill_generator/web/static/VENDORED.md`:

```markdown
# Vendored front-end libraries

Served from this directory so the UI works offline. Do not edit; to upgrade, replace the file
and update the version here.

| File | Library | Version | License |
|---|---|---|---|
| `htmx.min.js` | [htmx](https://htmx.org) | 2.0.4 | 0BSD |
| `tom-select.complete.min.js`, `tom-select.default.min.css` | [Tom Select](https://tom-select.js.org) | 2.4.3 | Apache-2.0 |
```

- [ ] **Step 5: Install and confirm nothing existing broke**

Run: `uv sync --extra dev && uv run pytest -q`

Expected: installs fastapi/uvicorn/jinja2/python-multipart/httpx2; the existing suite passes (185 tests at the time of writing).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml \
  uv.lock \
  waybill_generator/web/__init__.py \
  waybill_generator/web/static \
  tests/web/__init__.py \
  tests/fixtures/aar_codes.yaml
git commit -m "$(cat <<'EOF'
feat: add web UI dependencies, package skeleton, and vendored htmx/Tom Select

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `YamlFile` — minimal-diff read/write of a record file

**Files:**
- Create: `waybill_generator/web/yaml_store.py`
- Test: `tests/web/test_yaml_store.py`

**Interfaces:**
- Produces:
  - `class UnsupportedLayout(ValueError)`
  - `dump_record(record: dict) -> str` — one record as a top-level list item, house style
  - `class YamlFile(path: str | Path, group_key: Callable[[dict], object] | None = None)` with `.path: Path`, `.text: str`, `.records() -> list[dict]` (deep copies), `.render(desired: list[dict]) -> str`, `.changed_on_disk() -> bool`, `.stage(new_text: str) -> Path`, `.commit(tmp: Path) -> None`, `.reload() -> None`
  - `render()` semantics: `desired` is the full list of raw record dicts (each with an `id`). Records present in the file and unchanged keep their text; changed ones are edited key-by-key; new ones are inserted after the last record with the same `group_key` (else appended); records missing from `desired` are deleted.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_yaml_store.py`:

```python
import difflib

import pytest
import yaml

from waybill_generator.web.yaml_store import UnsupportedLayout, YamlFile, dump_record

SAMPLE = """\
# Sample data
# second header line

# ── SECTION A ──

- id: a1
  kind: A
  code: "01110"
  tags: [x, y]
  # what it ships
  ships:
    - p
    - q
  label: "Track 1"

- id: a2
  kind: A

# ── SECTION B ──

- id: b1
  kind: B
  label: hello
"""


def changed_lines(before: str, after: str) -> list[str]:
    diff = difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
    return [line for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---"))]


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text(SAMPLE)
    return YamlFile(path, group_key=lambda r: r.get("kind"))


def ids(text: str) -> list[str]:
    return [r["id"] for r in yaml.safe_load(text)]


def test_noop_render_is_byte_identical(sample):
    assert sample.render(sample.records()) == SAMPLE


def test_records_are_deep_copies(sample):
    records = sample.records()
    records[0]["ships"].append("z")
    assert sample.records()[0]["ships"] == ["p", "q"]


def test_edit_touches_only_the_changed_line(sample):
    records = sample.records()
    records[0]["label"] = "Yard"
    out = sample.render(records)
    assert changed_lines(SAMPLE, out) == ['-  label: "Track 1"', "+  label: Yard"]
    assert "tags: [x, y]" in out and "# what it ships" in out


def test_changed_list_is_reemitted_but_keeps_its_comment_and_neighbours(sample):
    records = sample.records()
    records[0]["ships"] = ["p", "q", "r"]
    out = sample.render(records)
    assert changed_lines(SAMPLE, out) == ["+    - r"]
    assert "# what it ships" in out and "tags: [x, y]" in out


def test_new_record_goes_after_the_last_of_its_group(sample):
    records = sample.records() + [{"id": "a3", "kind": "A", "label": "z"}]
    out = sample.render(records)
    assert ids(out) == ["a1", "a2", "a3", "b1"]
    assert "# ── SECTION B ──\n\n- id: b1" in out          # section header still heads its section
    assert all(line.startswith("+") for line in changed_lines(SAMPLE, out))


def test_new_record_without_matching_group_is_appended(sample):
    out = sample.render(sample.records() + [{"id": "c1", "kind": "C"}])
    assert ids(out)[-1] == "c1"
    assert all(line.startswith("+") for line in changed_lines(SAMPLE, out))


def test_delete_removes_only_that_record_and_keeps_section_comments(sample):
    out = sample.render([r for r in sample.records() if r["id"] != "a2"])
    assert ids(out) == ["a1", "b1"]
    assert out.count("# ── SECTION") == 2
    assert all(line.startswith("-") for line in changed_lines(SAMPLE, out))


def test_delete_last_record_keeps_the_section_comment(sample):
    out = sample.render([r for r in sample.records() if r["id"] != "b1"])
    assert ids(out) == ["a1", "a2"]
    assert "# ── SECTION B ──" in out and out.endswith("\n")


def test_delete_first_record(sample):
    out = sample.render([r for r in sample.records() if r["id"] != "a1"])
    assert ids(out) == ["a2", "b1"] and out.startswith("# Sample data")


def test_append_into_header_only_and_empty_files(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("# just a header\n")
    assert YamlFile(path).render([{"id": "a", "name": "A"}]) == "# just a header\n\n- id: a\n  name: A\n"
    path.write_text("")
    assert YamlFile(path).render([{"id": "a", "name": "A"}]) == "- id: a\n  name: A\n"


def test_missing_file_is_treated_as_empty(tmp_path):
    file = YamlFile(tmp_path / "nope.yaml")
    assert file.records() == []
    assert file.render([{"id": "a"}]) == "- id: a\n"


@pytest.mark.parametrize("text", ["key: value\n", "- just\n- scalars\n", "- name: no id\n"])
def test_unsupported_layouts_are_rejected(tmp_path, text):
    path = tmp_path / "x.yaml"
    path.write_text(text)
    with pytest.raises(UnsupportedLayout):
        YamlFile(path)


def test_conflict_detection_stage_and_commit(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("- id: a\n  name: A\n")
    file = YamlFile(path)
    assert not file.changed_on_disk()
    path.write_text("- id: a\n  name: B\n")
    assert file.changed_on_disk()
    tmp = file.stage("- id: a\n  name: C\n")
    assert tmp != path and path.read_text() == "- id: a\n  name: B\n"
    file.commit(tmp)
    assert path.read_text() == "- id: a\n  name: C\n"
    assert not tmp.exists() and not file.changed_on_disk() and file.records()[0]["name"] == "C"


def test_dump_record_house_style():
    assert dump_record({"id": "x", "ships": ["a", "b"], "none": None, "empty": [], "active": True}) == (
        "- id: x\n  ships:\n    - a\n    - b\n  none: null\n  empty: []\n  active: true\n"
    )


def test_dump_record_quotes_numeric_looking_strings():
    out = dump_record({"id": "x", "code": "01110", "n": "12345", "w": "36,200", "price": "112.40", "word": "Track 1"})
    assert 'code: "01110"' in out and 'n: "12345"' in out and 'w: "36,200"' in out and 'price: "112.40"' in out
    assert "word: Track 1" in out
    assert yaml.safe_load(out)[0]["n"] == "12345"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_yaml_store.py -q`

Expected: collection error — `ModuleNotFoundError: No module named 'waybill_generator.web.yaml_store'`.

- [ ] **Step 3: Implement `yaml_store.py`**

Create `waybill_generator/web/yaml_store.py`:

```python
"""Minimal-diff read/write of the flat, top-level-list YAML record files.

Each data file is a comment header followed by records that start with ``- `` at
column 0.  A file is split into (body, gap) segments: the body is one record's
text, the gap is the blank / column-0-comment lines between it and the next
record (section headers live there).  Saving rewrites only the bodies of
changed records and splices new/deleted ones in and out, so untouched records,
section-header comments and blank lines stay byte-identical.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import itertools
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml


class UnsupportedLayout(ValueError):
    """The file is not a flat top-level list of ``- `` records."""


class _HouseDumper(yaml.SafeDumper):
    """Emit YAML in the repo's house style: nested lists indented under their key."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


_NUMERIC_LIKE = re.compile(r"^[+-]?\d[\d_,.]*$")


def _represent_str(dumper, data):
    implicit = dumper.resolve(yaml.ScalarNode, data, (True, False))
    if implicit != "tag:yaml.org,2002:str" or _NUMERIC_LIKE.match(data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_HouseDumper.add_representer(str, _represent_str)


def dump_record(record: dict) -> str:
    """One record as a top-level list item, in house style."""
    return yaml.dump(
        [record], Dumper=_HouseDumper, sort_keys=False, default_flow_style=False,
        width=4096, allow_unicode=True,
    )


@dataclass
class _Segment:
    body: str
    gap: str
    raw: dict | None  # None for gap-only pseudo-segments


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _split(text: str) -> tuple[str, list[_Segment]]:
    if text and not text.endswith("\n"):
        text += "\n"
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith("- ")]
    parsed = yaml.safe_load(text) or []
    if len(parsed) != len(starts) or not all(isinstance(r, dict) and "id" in r for r in parsed):
        raise UnsupportedLayout("expected a top-level list of mappings that each have an id")
    header = "".join(lines[: starts[0]]) if starts else text
    segments = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        stop = end
        while stop > start + 1 and (lines[stop - 1].strip() == "" or lines[stop - 1].startswith("#")):
            stop -= 1
        segments.append(_Segment("".join(lines[start:stop]), "".join(lines[stop:end]), parsed[n]))
    return header, segments


_KEY_LINE = re.compile(r"^(?:- |  )(\S[^:]*?):(?:\s|$)")


def _blocks(text: str) -> list[tuple[str, list[str]]]:
    """Group a record's lines by top-level key: [(key, lines), ...].

    The ``- key:`` line starts the first block.  Indented comment lines belong to
    the key that follows them (comments usually describe the next key).
    """
    blocks: list[tuple[str, list[str]]] = []
    pending: list[str] = []
    for line in text.splitlines(keepends=True):
        is_key_line = line.startswith("- ") or (
            line.startswith("  ") and not line.startswith("   ") and not line.startswith("  -")
        )
        match = _KEY_LINE.match(line) if is_key_line else None
        if match:
            blocks.append((match.group(1), pending + [line]))
            pending = []
        elif line.strip().startswith("#"):
            pending.append(line)
        elif blocks:
            blocks[-1][1].extend(pending + [line])
            pending = []
    if pending and blocks:
        blocks[-1][1].extend(pending)
    return blocks


def _merge_lines(original: list[str], old: list[str], new: list[str]) -> list[str]:
    """Line-level old->new applied to `original` (only when `original` lines align 1:1 with `old`)."""
    if len(original) != len(old):
        return new
    merged: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        merged.extend(original[i1:i2] if tag == "equal" else new[j1:j2])
    return merged


def _edit_body(body: str, old_raw: dict, new_raw: dict) -> str:
    """Apply old_raw -> new_raw to a record's original text.

    Keys whose value did not change keep their original text (flow-style lists,
    odd quoting, indented comments); changed keys are re-emitted in house style.
    Anything unexpected falls back to re-emitting the whole record.
    """
    old_emit, new_emit = dump_record(old_raw), dump_record(new_raw)
    if body == old_emit:
        return new_emit
    original, old_blocks, new_blocks = _blocks(body), _blocks(old_emit), _blocks(new_emit)
    if [k for k, _ in original] != [k for k, _ in old_blocks]:
        return new_emit
    original_by_key, old_by_key = dict(original), dict(old_blocks)
    merged: list[str] = []
    for key, new_lines in new_blocks:
        if key in old_raw and key in new_raw and old_raw[key] == new_raw[key]:
            merged.extend(original_by_key[key])
        elif key in original_by_key:
            block = original_by_key[key]
            lead = len(list(itertools.takewhile(lambda line: line.strip().startswith("#"), block)))
            merged.extend(block[:lead])   # a comment above the key survives a change to its value
            merged.extend(_merge_lines(block[lead:], old_by_key[key], new_lines))
        else:
            merged.extend(new_lines)
    candidate = "".join(merged)
    try:
        if yaml.safe_load(candidate) == [new_raw]:
            return candidate
    except yaml.YAMLError:
        pass
    return new_emit


class YamlFile:
    """One data file: parsed records, and rendering of an edited record list back to text."""

    def __init__(self, path: str | Path, group_key: Callable[[dict], object] | None = None):
        self.path = Path(path)
        self.group_key = group_key
        self.reload()

    def reload(self) -> None:
        self.text = self.path.read_text() if self.path.exists() else ""
        self.digest = _digest(self.text)
        self._header, self._segments = _split(self.text)

    def records(self) -> list[dict]:
        return [copy.deepcopy(s.raw) for s in self._segments]

    def changed_on_disk(self) -> bool:
        current = self.path.read_text() if self.path.exists() else ""
        return _digest(current) != self.digest

    def render(self, desired: list[dict]) -> str:
        """Text for this file after applying `desired` (records keyed by their ``id``)."""
        wanted = {d["id"]: d for d in desired}
        existing = {s.raw["id"] for s in self._segments}
        out: list[_Segment] = []
        for seg in self._segments:
            rid = seg.raw["id"]
            if rid in wanted:
                new = wanted[rid]
                body = seg.body if new == seg.raw else _edit_body(seg.body, seg.raw, new)
                out.append(_Segment(body, seg.gap, new))
            elif seg.gap.strip() == "":
                if seg is self._segments[-1] and out and out[-1].gap.strip() == "":
                    out[-1].gap = seg.gap   # keep the file's original ending
            else:  # keep section-header comments that follow a deleted record
                out.append(_Segment("", seg.gap, None))
        for new in (d for d in desired if d["id"] not in existing):
            body = dump_record(new)
            index = len(out) - 1
            if self.group_key is not None:
                key = self.group_key(new)
                same = [i for i, s in enumerate(out) if s.raw is not None and self.group_key(s.raw) == key]
                if same:
                    index = same[-1]
            if index < 0:
                out.append(_Segment(body, "", new))
                continue
            anchor = out[index]
            out.insert(index + 1, _Segment(body, anchor.gap, new))
            anchor.gap = "\n"
        header = self._header
        if header and out and not header.endswith("\n\n") and not self._segments:
            header += "\n"
        return header + "".join(s.body + s.gap for s in out)

    def stage(self, new_text: str) -> Path:
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(new_text)
        return tmp

    def commit(self, tmp: Path) -> None:
        os.replace(tmp, self.path)
        self.reload()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_yaml_store.py -q`

Expected: 17 passed.

- [ ] **Step 5: Lint the new files**

Run: `uv run ruff check waybill_generator/web tests/web`

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/web/yaml_store.py \
  tests/web/test_yaml_store.py
git commit -m "$(cat <<'EOF'
feat: add YamlFile for minimal-diff record file edits

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Reference table and `WorkingCopy`

**Files:**
- Create: `waybill_generator/web/references.py`, `waybill_generator/web/working_copy.py`
- Create: `tests/web/conftest.py` (extended in Task 5)
- Test: `tests/web/test_references.py`, `tests/web/test_working_copy.py`

**Interfaces:**
- Consumes: `YamlFile`, `UnsupportedLayout` (Task 2); the existing models and `BaseRepository`.
- Produces (`references.py`): `WAYBILL_CLASSES: dict[str, type[BaseModel]]` (waybill_type → class, in union order, `"LOADED"` first); `REFERENCES: dict[tuple[str, str], str]` ((model class name, field) → target collection); `NOT_REFERENCES`; `SUGGESTIONS`; `class Ref(NamedTuple)` with `kind, record_id, field, target, value` and `.describe() -> str`; `iter_refs(records: dict[str, dict[str, BaseModel]]) -> Iterator[Ref]`.
- Produces (`working_copy.py`): `KINDS = ("cars", "commodities", "railroads", "locations", "waybills")`; `parse_record(kind, raw) -> BaseModel`; exceptions `DataError`, `ReferenceBlocked(refs)`, `ValidationBlocked(refs)`, `DiskConflict(files)`; dataclasses `Validation(blocking, existing)`, `FileDiff(kind, filename, diff)`; `merge_raw(old_raw, old_dump, new_dump) -> dict`; `class WorkingCopy(BaseRepository)` with `records(kind)`, `get(kind, id)`, `has(kind, id)`, `industry_ids()`, all `BaseRepository` getters, `apply(kind, model)`, `apply_industry(location_id, industry)`, `referencers(kind, id)`, `delete(kind, id)`, `delete_industry(location_id, industry_id)`, `status(kind, id) -> "new" | "modified" | None`, `deleted_ids(kind)`, `dirty_kinds()`, `change_count()`, `validate() -> Validation`, `diffs() -> list[FileDiff]`, `conflicts() -> list[str]`, `save(*, overwrite=False) -> list[str]`, `reload_file(kind)`, `discard()`, and the attribute `aar_codes: list[tuple[str, str]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/conftest.py` (only the fixture this task needs):

```python
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def data_dir(tmp_path):
    """A private, writable copy of tests/fixtures."""
    target = tmp_path / "data"
    shutil.copytree(FIXTURES, target)
    return target
```

Create `tests/web/test_references.py`:

```python
from waybill_generator.models.car import Car
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.location import Industry, Location
from waybill_generator.models.railroad import Railroad
from waybill_generator.web.references import (
    NOT_REFERENCES,
    REFERENCES,
    SUGGESTIONS,
    WAYBILL_CLASSES,
    iter_refs,
)
from waybill_generator.web.working_copy import KINDS, WorkingCopy


def test_every_waybill_type_is_registered():
    assert set(WAYBILL_CLASSES) == {
        "LOADED", "EMPTY", "DEADHEAD", "MOW", "HOLD", "BAD_ORDER",
        "STOP_OFF", "TEMPORARY", "PERISHABLE", "LIVESTOCK",
    }


def test_every_id_like_field_is_classified():
    """A new *_id field (or routing list) must be added to REFERENCES / NOT_REFERENCES / SUGGESTIONS."""
    for cls in [Car, Commodity, Railroad, Location, Industry, *WAYBILL_CLASSES.values()]:
        for name in cls.model_fields:
            key = (cls.__name__, name)
            if name != "id" and name.endswith("_id"):
                assert key in REFERENCES or key in NOT_REFERENCES, f"unclassified id field {key}"
            if name == "routing" and cls.__name__ != "TemporaryWaybill":
                assert key in SUGGESTIONS, f"unclassified list field {key}"


def test_iter_refs_covers_waybills_and_nested_industries(data_dir):
    wc = WorkingCopy(data_dir)
    refs = list(iter_refs({kind: {r.id: r for r in wc.records(kind)} for kind in KINDS}))
    assert ("waybills", "waybill-1", "shipper_id", "industries", "LEW-GRAIN") in refs
    assert ("waybills", "hold-1", "industry_id", "industries", "LEW-GRAIN") in refs
    assert ("industries", "LEW-GRAIN", "ships", "commodities", "grain") in refs
    assert ("waybills", "waybill-1", "originating_railroad_id", "railroads", "PRR") in refs
    assert ("cars", "PRR-12345", "aar_code", "aar_codes", "XM") in refs
    # free-text fields are not references
    assert not any(r.field in ("routing", "stop_at") for r in refs)
```

Create `tests/web/test_working_copy.py`:

```python
import difflib

import pytest
import yaml

from waybill_generator.models.waybill import HoldWaybill, LoadedWaybill
from waybill_generator.web.working_copy import (
    DataError,
    DiskConflict,
    ReferenceBlocked,
    ValidationBlocked,
    WorkingCopy,
    merge_raw,
)


def changed_lines(diff_text: str) -> list[str]:
    return [line for line in diff_text.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def new_loaded(**overrides) -> LoadedWaybill:
    fields = {"id": "waybill-2", "originating_railroad_id": "PRR", "commodity_id": "coal",
              "shipper_id": "ALT-SHOP", "consignee_id": "LEW-GRAIN"}
    return LoadedWaybill(**{**fields, **overrides})


def test_loads_fixtures_without_changes(data_dir):
    wc = WorkingCopy(data_dir)
    assert wc.change_count() == 0 and wc.dirty_kinds() == []
    assert len(wc.get_cars()) == 2 and len(wc.get_waybills()) == 6


def test_repository_contract(data_dir):
    wc = WorkingCopy(data_dir)
    assert wc.get_car("PRR-12345").road == "PRR"
    assert wc.get_location("LEW").name == "Lewistown"
    assert wc.get_industry("LEW-GRAIN").name == "Lewistown Grain Elevator"
    assert wc.get_commodity("grain").name == "Grain"
    assert wc.get_railroad("PRR").form_number == "Form 1304"
    assert wc.get_waybill("waybill-1").waybill_type == "LOADED"
    assert len(wc.get_locations()) == 2 and len(wc.get_commodities()) == 2 and len(wc.get_railroads()) == 1
    for getter, missing in [(wc.get_car, "NOPE"), (wc.get_location, "NOPE"), (wc.get_industry, "NOPE"),
                            (wc.get_commodity, "NOPE"), (wc.get_railroad, "NOPE"), (wc.get_waybill, "NOPE")]:
        with pytest.raises(KeyError):
            getter(missing)


def test_existing_broken_references_are_reported_but_do_not_block(data_dir):
    validation = WorkingCopy(data_dir).validate()      # fixture deadhead-1 points at PHL and PGH
    assert validation.blocking == []
    assert {r.value for r in validation.existing} == {"PHL", "PGH"}


def test_noop_save_writes_nothing(data_dir):
    wc = WorkingCopy(data_dir)
    before = {p.name: p.read_text() for p in data_dir.glob("*.yaml")}
    assert wc.save() == []
    assert {p.name: p.read_text() for p in data_dir.glob("*.yaml")} == before


def test_edit_car_changes_one_line(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "repainted"}))
    assert wc.status("cars", "PRR-12345") == "modified" and wc.change_count() == 1
    (diff,) = wc.diffs()
    assert diff.filename == "cars.yaml" and "+++ b/data/cars.yaml" in diff.diff
    assert changed_lines(diff.diff) == ["+  notes: repainted"]


def test_edit_industry_changes_one_line_and_keeps_omitted_defaults_absent(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply_industry("LEW", wc.get_industry("LEW-GRAIN").model_copy(update={"car_capacity": 5}))
    (diff,) = wc.diffs()
    assert changed_lines(diff.diff) == ["-      car_capacity: 3", "+      car_capacity: 5"]


def test_new_waybill_is_saved_grouped_with_its_type_and_reloads_equal(data_dir):
    wc = WorkingCopy(data_dir)
    waybill = new_loaded(notes="new one", routing=["ALT"])
    wc.apply("waybills", waybill)
    assert wc.status("waybills", "waybill-2") == "new"
    assert wc.save() == ["waybills.yaml"]
    assert wc.change_count() == 0
    saved = yaml.safe_load((data_dir / "waybills.yaml").read_text())
    assert [r["id"] for r in saved][:3] == ["waybill-1", "waybill-2", "empty-1"]
    assert saved[1] == {"id": "waybill-2", "waybill_type": "LOADED", "originating_railroad_id": "PRR",
                        "commodity_id": "coal", "shipper_id": "ALT-SHOP", "consignee_id": "LEW-GRAIN",
                        "routing": ["ALT"], "notes": "new one"}
    assert WorkingCopy(data_dir).get("waybills", "waybill-2") == waybill


def test_new_broken_reference_blocks_save(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("waybills", new_loaded(commodity_id="nope"))
    assert [r.value for r in wc.validate().blocking] == ["nope"]
    with pytest.raises(ValidationBlocked):
        wc.save()


def test_touching_a_record_that_already_has_a_broken_reference_still_saves(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("waybills", wc.get("waybills", "deadhead-1").model_copy(update={"notes": "touched"}))
    assert wc.validate().blocking == []
    assert wc.save() == ["waybills.yaml"]


def test_fixing_a_broken_reference_by_adding_the_target_clears_the_warning(data_dir):
    wc = WorkingCopy(data_dir)
    from waybill_generator.models.location import Location
    wc.apply("locations", Location(id="PHL", name="Philadelphia"))
    assert {r.value for r in wc.validate().existing} == {"PGH"}


def test_delete_blocked_while_referenced(data_dir):
    wc = WorkingCopy(data_dir)
    with pytest.raises(ReferenceBlocked) as blocked:
        wc.delete("commodities", "grain")
    assert {(r.kind, r.record_id) for r in blocked.value.refs} == {("waybills", "waybill-1"), ("industries", "LEW-GRAIN")}
    assert wc.has("commodities", "grain")


def test_delete_unreferenced_car_and_save(data_dir):
    wc = WorkingCopy(data_dir)
    wc.delete("cars", "PRR-67890")
    assert wc.deleted_ids("cars") == ["PRR-67890"] and wc.change_count() == 1
    assert wc.save() == ["cars.yaml"]
    assert [c["id"] for c in yaml.safe_load((data_dir / "cars.yaml").read_text())] == ["PRR-12345"]


def test_delete_location_blocked_when_its_industries_are_used(data_dir):
    with pytest.raises(ReferenceBlocked):
        WorkingCopy(data_dir).delete("locations", "LEW")      # LEW-GRAIN ships on waybill-1


def test_delete_unused_location_succeeds(data_dir):
    wc = WorkingCopy(data_dir)
    from waybill_generator.models.location import Location
    wc.apply("locations", Location(id="XYZ", name="Xyz"))
    wc.delete("locations", "XYZ")
    assert not wc.has("locations", "XYZ") and wc.change_count() == 0


def test_industry_add_and_delete(data_dir):
    from waybill_generator.models.location import Industry
    wc = WorkingCopy(data_dir)
    wc.apply_industry("LEW", Industry(id="LEW-NEW", name="New Co", location_id="ignored"))
    assert wc.get_industry("LEW-NEW").location_id == "LEW"
    with pytest.raises(ReferenceBlocked):
        wc.delete_industry("LEW", "LEW-GRAIN")
    wc.delete_industry("LEW", "LEW-NEW")
    assert wc.change_count() == 0


def test_conflict_is_detected_and_can_be_overridden(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    (data_dir / "cars.yaml").write_text((data_dir / "cars.yaml").read_text() + "\n# edited elsewhere\n")
    assert wc.conflicts() == ["cars.yaml"]
    with pytest.raises(DiskConflict) as conflict:
        wc.save()
    assert conflict.value.files == ["cars.yaml"]
    assert wc.save(overwrite=True) == ["cars.yaml"]


def test_reload_file_and_discard_drop_staged_edits(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    wc.delete("cars", "PRR-67890")
    wc.reload_file("cars")
    assert wc.change_count() == 0
    wc.delete("cars", "PRR-67890")
    wc.discard()
    assert wc.change_count() == 0 and wc.has("cars", "PRR-67890")


def test_unreadable_files_raise_data_error_naming_the_file(data_dir):
    (data_dir / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    with pytest.raises(DataError, match="cars.yaml"):
        WorkingCopy(data_dir)
    (data_dir / "cars.yaml").write_text("- id: a\n  road: PRR\n")          # missing required fields
    with pytest.raises(DataError, match="cars.yaml: record 'a'"):
        WorkingCopy(data_dir)
    (data_dir / "cars.yaml").write_text("just: a mapping\n")
    with pytest.raises(DataError, match="cars.yaml"):
        WorkingCopy(data_dir)


def test_stage_failure_leaves_data_untouched(data_dir, monkeypatch):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "mine"}))
    wc.apply("commodities", wc.get("commodities", "grain").model_copy(update={"name": "Grains"}))
    before = {p.name: p.read_text() for p in data_dir.glob("*.yaml")}
    calls = []
    original = type(wc._files["cars"]).stage

    def flaky(self, text):
        calls.append(self.path.name)
        if len(calls) == 2:
            raise OSError("disk full")
        return original(self, text)

    monkeypatch.setattr(type(wc._files["cars"]), "stage", flaky)
    with pytest.raises(OSError):
        wc.save()
    assert {p.name: p.read_text() for p in data_dir.glob("*.yaml")} == before
    assert not list(data_dir.glob("*.tmp"))


def test_merge_raw_keeps_unchanged_keys_and_appends_new_ones():
    old_raw = {"id": "a", "name": "A", "icon": None}
    old_dump = {"id": "a", "name": "A", "icon": None, "state": "PA"}     # `state` is a default, absent in the file
    assert merge_raw(old_raw, old_dump, {**old_dump, "name": "B"}) == {"id": "a", "name": "B", "icon": None}
    assert merge_raw(old_raw, old_dump, {**old_dump, "state": "NY"}) == {"id": "a", "name": "A", "icon": None, "state": "NY"}
    assert merge_raw(old_raw, old_dump, {**old_dump, "icon": "x"})["icon"] == "x"
    assert "icon" not in merge_raw({"id": "a", "icon": "x"}, {"id": "a", "icon": "x"}, {"id": "a", "icon": None})


def test_merge_raw_for_a_new_record_drops_nones_and_puts_notes_last():
    dump = {"id": "a", "notes": "n", "x": None, "items": [{"id": "i", "notes": "m", "y": None, "z": 1}]}
    merged = merge_raw(None, {}, dump)
    assert list(merged) == ["id", "items", "notes"]
    assert merged["items"] == [{"id": "i", "z": 1, "notes": "m"}]


def test_hold_waybill_round_trip(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("waybills", HoldWaybill(id="hold-2", originating_railroad_id="PRR", industry_id="ALT-SHOP", waiting_for="parts"))
    wc.save()
    assert wc.get("waybills", "hold-2") == HoldWaybill(
        id="hold-2", originating_railroad_id="PRR", industry_id="ALT-SHOP", waiting_for="parts")


def test_diff_text_is_a_unified_diff(data_dir):
    wc = WorkingCopy(data_dir)
    wc.apply("cars", wc.get("cars", "PRR-12345").model_copy(update={"notes": "x"}))
    (diff,) = wc.diffs()
    assert list(difflib.unified_diff([], [])) == [] and diff.diff.startswith("--- a/data/cars.yaml")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_references.py tests/web/test_working_copy.py -q`

Expected: collection errors — `No module named 'waybill_generator.web.references'`.

- [ ] **Step 3: Implement `references.py`**

```python
"""Which model fields point at which collection.

Single source of truth for the searchable pickers (forms.py) and the
reference checks (working_copy.py).
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple, get_args

from pydantic import BaseModel

from waybill_generator.models.waybill import Waybill

# Every waybill class, keyed by its waybill_type literal ("LOADED", ...).
_UNION = get_args(Waybill)[0]
WAYBILL_CLASSES: dict[str, type[BaseModel]] = {
    cls.model_fields["waybill_type"].default: cls for cls in get_args(_UNION)
}

# (model class name, field name) -> collection the value(s) must exist in.
REFERENCES: dict[tuple[str, str], str] = {
    ("Car", "aar_code"): "aar_codes",
    ("Commodity", "acceptable_car_types"): "aar_codes",
    ("Location", "railroad_id"): "railroads",
    ("Industry", "ships"): "commodities",
    ("Industry", "receives"): "commodities",
    ("LoadedWaybill", "commodity_id"): "commodities",
    ("LoadedWaybill", "shipper_id"): "industries",
    ("LoadedWaybill", "consignee_id"): "industries",
    ("EmptyWaybill", "from_location_id"): "locations",
    ("EmptyWaybill", "to_location_id"): "locations",
    ("DeadheadWaybill", "from_location_id"): "locations",
    ("DeadheadWaybill", "to_location_id"): "locations",
    ("MoWWaybill", "from_location_id"): "locations",
    ("MoWWaybill", "to_location_id"): "locations",
    ("HoldWaybill", "industry_id"): "industries",
    ("BadOrderWaybill", "from_location_id"): "locations",
    ("BadOrderWaybill", "shop_location_id"): "locations",
    ("PerishableWaybill", "commodity_id"): "commodities",
}
for _cls in WAYBILL_CLASSES.values():
    REFERENCES[(_cls.__name__, "originating_railroad_id")] = "railroads"

# `*_id`-named fields that are deliberately NOT references (free text, or implied by nesting).
NOT_REFERENCES: set[tuple[str, str]] = {
    ("TemporaryWaybill", "from_location_id"),  # real data holds free text like "Burnham PA"
    ("TemporaryWaybill", "to_location_id"),
    ("Industry", "location_id"),               # always the parent location
}

# List fields that take free-form entries but offer suggestions from these collections.
SUGGESTIONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("LoadedWaybill", "routing"): ("locations", "railroads"),
    ("PerishableWaybill", "routing"): ("railroads", "locations"),
    ("LivestockWaybill", "routing"): ("railroads", "locations"),
}


class Ref(NamedTuple):
    kind: str       # collection of the referring record: cars, commodities, locations, industries, waybills
    record_id: str
    field: str
    target: str     # collection referred to
    value: str

    def describe(self) -> str:
        return f"{self.kind.removesuffix('s')} {self.record_id} ({self.field}: {self.value})"


_BY_MODEL: dict[str, list[tuple[str, str]]] = {}
for (_model, _field), _target in REFERENCES.items():
    _BY_MODEL.setdefault(_model, []).append((_field, _target))


def _refs_of(kind: str, record: BaseModel) -> Iterator[Ref]:
    for field, target in _BY_MODEL.get(type(record).__name__, ()):
        value = getattr(record, field)
        items = [] if value is None else value if isinstance(value, list) else [value]
        for item in items:
            yield Ref(kind, record.id, field, target, item)


def iter_refs(records: dict[str, dict[str, BaseModel]]) -> Iterator[Ref]:
    """Every reference held by the given records (kind -> id -> model)."""
    for kind, by_id in records.items():
        for record in by_id.values():
            yield from _refs_of(kind, record)
            if kind == "locations":
                for industry in record.industries:
                    yield from _refs_of("industries", industry)
```

- [ ] **Step 4: Implement `working_copy.py`**

```python
"""Mutable, in-memory copy of the data files that edits are staged into.

Nothing touches disk until ``save()``.  The YAML files stay the source of
truth: ``save()`` merges only the records that changed back into the files.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, TypeAdapter, ValidationError

from waybill_generator.models.car import Car
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.location import Industry, Location
from waybill_generator.models.railroad import Railroad
from waybill_generator.models.waybill import Waybill, WaybillBase
from waybill_generator.repository.base import BaseRepository

from .references import Ref, iter_refs
from .yaml_store import UnsupportedLayout, YamlFile

KINDS = ("cars", "commodities", "railroads", "locations", "waybills")
_MODELS = {"cars": Car, "commodities": Commodity, "railroads": Railroad, "locations": Location}
_waybills = TypeAdapter(Waybill)


def parse_record(kind: str, raw: dict) -> BaseModel:
    return _waybills.validate_python(raw) if kind == "waybills" else _MODELS[kind](**raw)


class DataError(Exception):
    """A data file could not be read (bad YAML, unsupported layout, or an invalid record)."""


class ReferenceBlocked(Exception):
    """Deleting a record that other records still reference."""

    def __init__(self, refs: list[Ref]):
        super().__init__(f"referenced by {len(refs)} record(s)")
        self.refs = refs


class ValidationBlocked(Exception):
    """Save refused because the edits introduced broken references."""

    def __init__(self, refs: list[Ref]):
        super().__init__(f"{len(refs)} broken reference(s)")
        self.refs = refs


class DiskConflict(Exception):
    """A file changed on disk since it was loaded."""

    def __init__(self, files: list[str]):
        super().__init__("changed on disk: " + ", ".join(files))
        self.files = files


@dataclass(frozen=True)
class Validation:
    blocking: list[Ref]   # broken references introduced by staged edits
    existing: list[Ref]   # broken references already present in the files on disk


@dataclass(frozen=True)
class FileDiff:
    kind: str
    filename: str
    diff: str


def _strip_none(value):
    if isinstance(value, dict):
        cleaned = {k: _strip_none(v) for k, v in value.items() if v is not None}
        if "notes" in cleaned:  # house style: notes last
            cleaned["notes"] = cleaned.pop("notes")
        return cleaned
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value


def _is_record_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) and "id" in v for v in value)


def merge_raw(old_raw: dict | None, old_dump: dict, new_dump: dict) -> dict:
    """Apply the difference between two model dumps onto a record as it appears in the file.

    Keys the user did not change keep exactly the form they have in the file
    (present-with-null stays, absent-with-default stays absent).  Nested lists
    of id'd records are merged record by record.
    """
    if old_raw is None:
        return _strip_none(new_dump)
    merged = dict(old_raw)
    for key, new_value in new_dump.items():
        old_value = old_dump.get(key)
        if new_value == old_value:
            continue
        if _is_record_list(new_value):
            raw_by_id = {r["id"]: r for r in old_raw.get(key) or [] if isinstance(r, dict) and "id" in r}
            dump_by_id = {r["id"]: r for r in old_value or []}
            merged[key] = [
                merge_raw(raw_by_id.get(r["id"]), dump_by_id.get(r["id"], {}), r) for r in new_value
            ]
        elif new_value is None:
            merged.pop(key, None)
        else:
            merged[key] = new_value
    return merged


class WorkingCopy(BaseRepository):
    def __init__(self, data_path: str | Path):
        self._path = Path(data_path)
        self._files = {}
        for kind in KINDS:
            try:
                self._files[kind] = YamlFile(
                    self._path / f"{kind}.yaml",
                    group_key=(lambda r: r.get("waybill_type")) if kind == "waybills" else None,
                )
            except (yaml.YAMLError, UnsupportedLayout) as exc:
                raise DataError(f"{kind}.yaml: {exc}") from exc
        self.aar_codes = self._load_aar_codes()
        self._records: dict[str, dict[str, BaseModel]] = {}
        self._orig_raw: dict[str, dict[str, dict]] = {}
        self._orig_model: dict[str, dict[str, BaseModel]] = {}
        for kind in KINDS:
            self._load_kind(kind)
        self._refresh_baseline()

    # ── loading ──────────────────────────────────────────────────────────
    def _load_aar_codes(self) -> list[tuple[str, str]]:
        path = self._path / "aar_codes.yaml"
        if not path.exists():
            return []
        rows = yaml.safe_load(path.read_text()) or []
        return [(r["code"], r.get("name", "")) for r in rows]

    def _load_kind(self, kind: str) -> None:
        raws = self._files[kind].records()
        models = {}
        for raw in raws:
            try:
                models[raw["id"]] = parse_record(kind, raw)
            except ValidationError as exc:
                raise DataError(f"{kind}.yaml: record {raw['id']!r}: {exc}") from exc
        self._orig_raw[kind] = {r["id"]: r for r in raws}
        self._orig_model[kind] = models
        self._records[kind] = dict(models)

    def _refresh_baseline(self) -> None:
        self._baseline = self._dangling(self._orig_model)

    def _reread(self, kind: str) -> None:
        try:
            self._files[kind].reload()
        except (yaml.YAMLError, UnsupportedLayout) as exc:
            raise DataError(f"{kind}.yaml: {exc}") from exc
        self._load_kind(kind)

    def reload_file(self, kind: str) -> None:
        """Re-read one file from disk, dropping its staged edits."""
        self._reread(kind)
        self._refresh_baseline()

    def discard(self) -> None:
        for kind in KINDS:
            self._reread(kind)
        self._refresh_baseline()

    # ── reads ────────────────────────────────────────────────────────────
    def records(self, kind: str) -> list[BaseModel]:
        return list(self._records[kind].values())

    def get(self, kind: str, record_id: str) -> BaseModel:
        return self._records[kind][record_id]

    def has(self, kind: str, record_id: str) -> bool:
        return record_id in self._records[kind]

    def industry_ids(self) -> set[str]:
        return {i.id for loc in self._records["locations"].values() for i in loc.industries}

    def get_cars(self) -> list[Car]:
        return self.records("cars")

    def get_car(self, id: str) -> Car:
        return self._get("cars", id, "Car")

    def get_locations(self) -> list[Location]:
        return self.records("locations")

    def get_location(self, id: str) -> Location:
        return self._get("locations", id, "Location")

    def get_commodities(self) -> list[Commodity]:
        return self.records("commodities")

    def get_commodity(self, id: str) -> Commodity:
        return self._get("commodities", id, "Commodity")

    def get_waybills(self) -> list[WaybillBase]:
        return self.records("waybills")

    def get_waybill(self, id: str) -> WaybillBase:
        return self._get("waybills", id, "Waybill")

    def get_railroads(self) -> list[Railroad]:
        return self.records("railroads")

    def get_railroad(self, id: str) -> Railroad:
        return self._get("railroads", id, "Railroad")

    def get_industry(self, id: str) -> Industry:
        for loc in self._records["locations"].values():
            for industry in loc.industries:
                if industry.id == id:
                    return industry
        raise KeyError(f"Industry not found: {id!r}")

    def _get(self, kind: str, record_id: str, label: str):
        try:
            return self._records[kind][record_id]
        except KeyError:
            raise KeyError(f"{label} not found: {record_id!r}") from None

    # ── edits ────────────────────────────────────────────────────────────
    def apply(self, kind: str, model: BaseModel) -> None:
        """Insert or replace a record (existing records keep their position)."""
        self._records[kind][model.id] = model

    def apply_industry(self, location_id: str, industry: Industry) -> None:
        location = self._records["locations"][location_id]
        industry = industry.model_copy(update={"location_id": location_id})
        industries = [industry if i.id == industry.id else i for i in location.industries]
        if all(i.id != industry.id for i in location.industries):
            industries.append(industry)
        self._records["locations"][location_id] = location.model_copy(update={"industries": industries})

    def referencers(self, kind: str, record_id: str) -> list[Ref]:
        """Records that would be left with a broken reference if this one were deleted."""
        targets = {(kind, record_id)} if kind in ("commodities", "railroads") else set()
        own_industries: set[str] = set()
        if kind == "locations":
            targets.add(("locations", record_id))
            own_industries = {i.id for i in self._records["locations"][record_id].industries}
            targets |= {("industries", i) for i in own_industries}
        return sorted(
            r for r in iter_refs(self._records)
            if (r.target, r.value) in targets and not (r.kind == "industries" and r.record_id in own_industries)
        )

    def delete(self, kind: str, record_id: str) -> None:
        blockers = self.referencers(kind, record_id)
        if blockers:
            raise ReferenceBlocked(blockers)
        del self._records[kind][record_id]

    def delete_industry(self, location_id: str, industry_id: str) -> None:
        blockers = sorted(
            r for r in iter_refs(self._records) if (r.target, r.value) == ("industries", industry_id)
        )
        if blockers:
            raise ReferenceBlocked(blockers)
        location = self._records["locations"][location_id]
        remaining = [i for i in location.industries if i.id != industry_id]
        self._records["locations"][location_id] = location.model_copy(update={"industries": remaining})

    # ── change tracking ──────────────────────────────────────────────────
    def status(self, kind: str, record_id: str) -> str | None:
        if record_id not in self._orig_model[kind]:
            return "new"
        return "modified" if self._records[kind][record_id] != self._orig_model[kind][record_id] else None

    def deleted_ids(self, kind: str) -> list[str]:
        return [i for i in self._orig_model[kind] if i not in self._records[kind]]

    def dirty_kinds(self) -> list[str]:
        return [k for k in KINDS if self._records[k] != self._orig_model[k]]

    def change_count(self) -> int:
        total = 0
        for kind in KINDS:
            total += len(self.deleted_ids(kind))
            total += sum(1 for rid in self._records[kind] if self.status(kind, rid))
        return total

    # ── validation ───────────────────────────────────────────────────────
    def _known(self, records: dict[str, dict[str, BaseModel]]) -> dict[str, set[str]]:
        return {
            "railroads": set(records["railroads"]),
            "locations": set(records["locations"]),
            "industries": {i.id for loc in records["locations"].values() for i in loc.industries},
            "commodities": set(records["commodities"]),
            "aar_codes": {code for code, _ in self.aar_codes},
        }

    def _dangling(self, records: dict[str, dict[str, BaseModel]]) -> set[Ref]:
        known = self._known(records)
        return {
            r for r in iter_refs(records)
            if known[r.target] and r.value not in known[r.target]
        }

    def validate(self) -> Validation:
        dangling = self._dangling(self._records)
        return Validation(
            blocking=sorted(dangling - self._baseline),
            existing=sorted(dangling & self._baseline),
        )

    # ── saving ───────────────────────────────────────────────────────────
    def _desired_raw(self, kind: str) -> list[dict]:
        desired = []
        for record_id, model in self._records[kind].items():
            old_model = self._orig_model[kind].get(record_id)
            desired.append(merge_raw(
                self._orig_raw[kind].get(record_id),
                old_model.model_dump(mode="json") if old_model else {},
                model.model_dump(mode="json"),
            ))
        return desired

    def diffs(self) -> list[FileDiff]:
        result = []
        for kind in self.dirty_kinds():
            file = self._files[kind]
            new_text = file.render(self._desired_raw(kind))
            name = file.path.name
            diff = "".join(difflib.unified_diff(
                file.text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                fromfile=f"a/data/{name}", tofile=f"b/data/{name}", n=2,
            ))
            result.append(FileDiff(kind, name, diff))
        return result

    def conflicts(self) -> list[str]:
        return [self._files[k].path.name for k in self.dirty_kinds() if self._files[k].changed_on_disk()]

    def save(self, *, overwrite: bool = False) -> list[str]:
        """Write every changed file. Returns the filenames written."""
        validation = self.validate()
        if validation.blocking:
            raise ValidationBlocked(validation.blocking)
        conflicts = self.conflicts()
        if conflicts and not overwrite:
            raise DiskConflict(conflicts)
        kinds = self.dirty_kinds()
        staged = []
        try:
            for kind in kinds:
                file = self._files[kind]
                staged.append((kind, file.stage(file.render(self._desired_raw(kind)))))
        except Exception:
            for _, tmp in staged:
                tmp.unlink(missing_ok=True)
            raise
        written = []
        for kind, tmp in staged:
            self._files[kind].commit(tmp)
            self._load_kind(kind)
            written.append(self._files[kind].path.name)
        self._refresh_baseline()
        return written
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web -q`

Expected: all pass (26 new tests plus Task 2's 17).

- [ ] **Step 6: Lint**

Run: `uv run ruff check waybill_generator/web tests/web`

Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/web/references.py \
  waybill_generator/web/working_copy.py \
  tests/web/conftest.py \
  tests/web/test_references.py \
  tests/web/test_working_copy.py
git commit -m "$(cat <<'EOF'
feat: add WorkingCopy with staged edits, reference checks, and minimal-diff save

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Generic form building and parsing

**Files:**
- Create: `waybill_generator/web/forms.py`
- Test: `tests/web/test_forms.py`

**Interfaces:**
- Consumes: `REFERENCES`, `SUGGESTIONS` (Task 3); a `WorkingCopy` (for `build_options`).
- Produces: `class FormField` (dataclass: `name, label, kind, required, value, error, readonly, options, selected, rank`); `initial_values(model_cls) -> dict`; `build_options(repo) -> dict[str, list[dict]]` (keys `industries`, `locations`, `commodities`, `railroads`, `aar_codes`; option dicts have `value`, `text`, `meta`, and for industries `ships`/`receives` as comma-joined strings); `build_fields(model_cls, values, errors, options, *, editing) -> list[FormField]`; `parse_form(model_cls, form) -> (values, errors)` where `form` has `.get(key)` and `.getlist(key)`; `build_model(model_cls, values) -> (model | None, errors)`.
- Field kinds: `text`, `number`, `checkbox`, `textarea`, `select`, `multiselect`, `tags` (free-entry list with suggestions).

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_forms.py`:

```python
from waybill_generator.models.car import Car
from waybill_generator.models.location import Industry
from waybill_generator.models.waybill import LoadedWaybill, TemporaryWaybill
from waybill_generator.web.forms import (
    build_fields,
    build_model,
    build_options,
    initial_values,
    parse_form,
)
from waybill_generator.web.references import REFERENCES, WAYBILL_CLASSES
from waybill_generator.web.working_copy import WorkingCopy


class FakeForm(dict):
    """Just enough of Starlette's FormData for parse_form."""

    def getlist(self, key):
        value = self.get(key, [])
        return value if isinstance(value, list) else [value]


def fields_by_name(model_cls, data_dir, values=None, errors=None, editing=False):
    options = build_options(WorkingCopy(data_dir))
    return {f.name: f for f in build_fields(model_cls, values or {}, errors or {}, options, editing=editing)}


def test_build_options_has_searchable_context(data_dir):
    options = build_options(WorkingCopy(data_dir))
    industry = next(o for o in options["industries"] if o["value"] == "LEW-GRAIN")
    assert industry["text"] == "Lewistown Grain Elevator"
    assert industry["meta"] == "LEW-GRAIN · Lewistown, PA · track 1"
    assert industry["ships"] == "grain" and industry["receives"] == ""
    assert next(o for o in options["commodities"] if o["value"] == "coal")["meta"] == "coal · AAR 01210 · cars: HM, GB"
    assert {"value": "XM", "text": "XM — Box Car", "meta": ""} in options["aar_codes"]
    assert options["railroads"] == [{"value": "PRR", "text": "Pennsylvania Railroad", "meta": "PRR"}]
    assert {o["value"] for o in options["locations"]} == {"LEW", "ALT"}


def test_every_waybill_type_builds_a_form_with_pickers_for_its_references(data_dir):
    options = build_options(WorkingCopy(data_dir))
    for wtype, cls in WAYBILL_CLASSES.items():
        fields = build_fields(cls, initial_values(cls), {}, options, editing=False)
        names = {f.name for f in fields}
        assert "id" in names and "waybill_type" not in names, wtype
        for f in fields:
            if (cls.__name__, f.name) in REFERENCES:
                assert f.kind in ("select", "multiselect"), (wtype, f.name)


def test_loaded_form_hides_display_only_fields_and_ranks_industries(data_dir):
    fields = fields_by_name(LoadedWaybill, data_dir)
    assert "to_city" not in fields and "shipper_name" not in fields
    assert fields["shipper_id"].rank == ("commodity_id", "ships")
    assert fields["consignee_id"].rank == ("commodity_id", "receives")
    assert fields["routing"].kind == "tags" and fields["notes"].kind == "textarea"
    assert fields["commodity_id"].required and not fields["stop_at"].required


def test_temporary_waybill_locations_are_free_text(data_dir):
    fields = fields_by_name(TemporaryWaybill, data_dir)
    assert fields["from_location_id"].kind == "text" and fields["to_location_id"].kind == "text"


def test_a_value_missing_from_the_data_stays_selectable(data_dir):
    fields = fields_by_name(LoadedWaybill, data_dir, values={"commodity_id": "produce", "routing": ["NYC"]})
    assert {"value": "produce", "text": "produce", "meta": "not in data"} in fields["commodity_id"].options
    assert fields["commodity_id"].selected == {"produce"}
    assert {"value": "NYC", "text": "NYC", "meta": "not in data"} in fields["routing"].options


def test_id_is_read_only_only_when_editing(data_dir):
    assert fields_by_name(Car, data_dir, editing=True)["id"].readonly
    assert not fields_by_name(Car, data_dir, editing=False)["id"].readonly


def test_industry_form_hides_its_parent_location(data_dir):
    fields = fields_by_name(Industry, data_dir)
    assert "location_id" not in fields and fields["ships"].kind == "multiselect"


def test_initial_values_use_model_defaults():
    assert initial_values(Car) == {"active": True}
    assert initial_values(LoadedWaybill)["routing"] == []


def test_parse_form_reports_blank_required_and_bad_numbers():
    values, errors = parse_form(Car, FakeForm({"road": "PRR", "car_number": "1", "aar_code": "XM",
                                               "capacity_tons": "", "capacity_cuft": "abc", "length_ft": "40"}))
    assert errors == {"id": "Required", "capacity_tons": "Required", "capacity_cuft": "Must be a whole number"}
    assert values["length_ft"] == 40 and values["notes"] is None and values["active"] is False


def test_parse_form_reads_checkboxes_lists_and_strips_blanks():
    values, errors = parse_form(Industry, FakeForm({"id": " X ", "name": "Xco", "ships": ["grain", " ", "coal"], "track": ""}))
    assert errors == {} and values["id"] == "X"
    assert values["ships"] == ["grain", "coal"] and values["receives"] == [] and values["track"] is None
    values, _ = parse_form(Car, FakeForm({"active": "on"}))
    assert values["active"] is True


def test_build_model_maps_pydantic_errors_to_fields():
    model, errors = build_model(Car, {"id": "a", "road": "PRR", "car_number": "1", "aar_code": "XM", "capacity_tons": "x"})
    assert model is None and "capacity_tons" in errors
    model, errors = build_model(Car, {"id": "a", "road": "PRR", "car_number": "1", "aar_code": "XM", "capacity_tons": 50})
    assert errors == {} and model.capacity_tons == 50
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_forms.py -q`

Expected: collection error — `No module named 'waybill_generator.web.forms'`.

- [ ] **Step 3: Implement `forms.py`**

```python
"""Generic HTML form building and parsing driven by the Pydantic models."""
from __future__ import annotations

import types
import typing
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined

from .references import REFERENCES, SUGGESTIONS

# Fields the generic form never renders; callers fill them in.
HIDDEN: set[tuple[str, str]] = {
    ("Industry", "location_id"),
    ("Location", "industries"),
    # LoadedWaybill display fields are resolved at render time, never stored.
    *(("LoadedWaybill", f) for f in
      ("to_city", "to_state", "consignee_name", "from_city", "from_state", "shipper_name")),
}
HIDDEN_NAMES = {"waybill_type"}          # rendered by the page itself, not as a generic field
TEXTAREAS = {"notes"}

# (model, field) -> (field holding the commodity, industry list to rank by)
RANKED: dict[tuple[str, str], tuple[str, str]] = {
    ("LoadedWaybill", "shipper_id"): ("commodity_id", "ships"),
    ("LoadedWaybill", "consignee_id"): ("commodity_id", "receives"),
}


@dataclass
class FormField:
    name: str
    label: str
    kind: str                     # text | number | checkbox | textarea | select | multiselect | tags
    required: bool
    value: Any
    error: str | None = None
    readonly: bool = False
    options: list[dict] = field(default_factory=list)
    selected: set[str] = field(default_factory=set)
    rank: tuple[str, str] | None = None


def _unwrap(annotation) -> tuple[Any, bool, bool]:
    """(base type, is_list, is_optional) for str, int, str | None, list[str], ..."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        args = typing.get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        base, is_list, _ = _unwrap(non_none[0])
        return base, is_list, len(non_none) < len(args)
    if origin is list:
        return typing.get_args(annotation)[0], True, False
    return annotation, False, False


def _label(name: str) -> str:
    return name.removesuffix("_id").replace("_", " ").capitalize()


def _skipped(model_cls: type[BaseModel], name: str) -> bool:
    return name in HIDDEN_NAMES or (model_cls.__name__, name) in HIDDEN


def initial_values(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Defaults to pre-fill on a blank form."""
    values: dict[str, Any] = {}
    for name, info in model_cls.model_fields.items():
        if info.default is not PydanticUndefined and info.default is not None:
            values[name] = list(info.default) if isinstance(info.default, list) else info.default
    return values


def build_options(repo) -> dict[str, list[dict]]:
    """Picker options per collection: value, text, and searchable meta text."""
    industries, locations = [], []
    for loc in repo.get_locations():
        locations.append({"value": loc.id, "text": loc.name, "meta": f"{loc.id} · {loc.state}"})
        for ind in loc.industries:
            meta = f"{ind.id} · {loc.name}, {loc.state}" + (f" · track {ind.track}" if ind.track else "")
            industries.append({
                "value": ind.id, "text": ind.name, "meta": meta,
                "ships": ",".join(ind.ships), "receives": ",".join(ind.receives),
            })
    commodities = []
    for com in repo.get_commodities():
        meta = com.id
        if com.aar_code:
            meta += f" · AAR {com.aar_code}"
        if com.acceptable_car_types:
            meta += f" · cars: {', '.join(com.acceptable_car_types)}"
        commodities.append({"value": com.id, "text": com.name, "meta": meta})
    return {
        "industries": industries,
        "locations": locations,
        "commodities": commodities,
        "railroads": [{"value": r.id, "text": r.name, "meta": r.id} for r in repo.get_railroads()],
        "aar_codes": [{"value": c, "text": f"{c} — {n}" if n else c, "meta": ""} for c, n in repo.aar_codes],
    }


def build_fields(
    model_cls: type[BaseModel],
    values: dict[str, Any],
    errors: dict[str, str],
    options: dict[str, list[dict]],
    *,
    editing: bool,
) -> list[FormField]:
    fields = []
    for name, info in model_cls.model_fields.items():
        if _skipped(model_cls, name):
            continue
        key = (model_cls.__name__, name)
        base, is_list, optional = _unwrap(info.annotation)
        value = values.get(name)
        target = REFERENCES.get(key)
        opts: list[dict] = []
        if target:
            kind = "multiselect" if is_list else "select"
            opts = list(options[target])
        elif key in SUGGESTIONS:
            kind = "tags"
            opts = [o for t in SUGGESTIONS[key] for o in options[t]]
        elif is_list:
            kind = "tags"
        elif base is bool:
            kind = "checkbox"
        elif base is int:
            kind = "number"
        elif name in TEXTAREAS:
            kind = "textarea"
        else:
            kind = "text"
        selected: set[str] = set()
        if kind in ("select", "multiselect", "tags"):
            selected = set(value or []) if is_list else ({value} if value else set())
            known = {o["value"] for o in opts}
            # keep values that aren't in the data (e.g. a pre-existing dangling reference)
            opts += [{"value": v, "text": v, "meta": "not in data"} for v in sorted(selected - known)]
        fields.append(FormField(
            name=name, label=_label(name), kind=kind,
            required=info.is_required() and not optional,
            value=value, error=errors.get(name), readonly=(name == "id" and editing),
            options=opts, selected=selected, rank=RANKED.get(key),
        ))
    return fields


class _Form(typing.Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def getlist(self, key: str) -> list[Any]: ...


def parse_form(model_cls: type[BaseModel], form: _Form) -> tuple[dict[str, Any], dict[str, str]]:
    """Form data -> (values for the model, errors by field). Hidden fields are left to the caller."""
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name, info in model_cls.model_fields.items():
        if _skipped(model_cls, name):
            continue
        base, is_list, optional = _unwrap(info.annotation)
        if is_list:
            values[name] = [v.strip() for v in form.getlist(name) if v.strip()]
        elif base is bool:
            values[name] = form.get(name) is not None
        else:
            raw = (form.get(name) or "").strip()
            if raw == "":
                if info.is_required() and not optional:
                    errors[name] = "Required"
                    values[name] = ""
                elif optional:
                    values[name] = None
                elif info.default is not PydanticUndefined:
                    values[name] = info.default
            elif base is int:
                try:
                    values[name] = int(raw)
                except ValueError:
                    errors[name] = "Must be a whole number"
                    values[name] = raw
            else:
                values[name] = raw
    return values, errors


def build_model(model_cls: type[BaseModel], values: dict[str, Any]) -> tuple[BaseModel | None, dict[str, str]]:
    try:
        return model_cls(**values), {}
    except ValidationError as exc:
        return None, {str(e["loc"][0]): e["msg"] for e in exc.errors() if e["loc"]}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/web -q`

Expected: all pass (11 new tests).

- [ ] **Step 5: Lint**

Run: `uv run ruff check waybill_generator/web tests/web`

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add waybill_generator/web/forms.py \
  tests/web/test_forms.py
git commit -m "$(cat <<'EOF'
feat: add generic model-driven form building and parsing

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Web shell, list pages, and `waybill serve`

**Files:**
- Create: `waybill_generator/web/entities.py`, `context.py`, `routes_records.py` (list page only for now), `app.py`
- Create: `waybill_generator/web/templates/base.html`, `list.html`; `waybill_generator/web/static/app.css`
- Modify: `tests/web/conftest.py` (add `client`, `follow`, `CAR_FORM`); `waybill_generator/cli.py` (append `serve`)
- Test: `tests/web/test_app_lists.py`, `tests/web/test_serve.py`

**Interfaces:**
- Consumes: `WorkingCopy` (Task 3), `build_fields`/`build_options` (Task 4), `_generate_location_id` from `waybill_generator/cli.py`.
- Produces:
  - `entities.py`: `Entity` (frozen dataclass: `kind, title, noun, columns, search, model, preserve, types, type_field`, method `model_class(existing, chosen_type)`); `ENTITIES: dict[str, Entity]` (waybills, cars, locations, commodities, railroads — nav order); `get_entity(kind) -> Entity` (404s); `waybill_summary(wc, waybill) -> str`; `cell(wc, record, attr)`; `suggest_id(wc, kind, values) -> str`.
  - `context.py`: `templates`, `WEB_DIR`, `wc_of(request)`, `render(request, name, status=200, **ctx)`, `redirect(url, flash=None)`, `blocked_message(refs)`, `form_page(request, *, kind, heading, model_cls, values, errors, editing, action, cancel_url, delete_url=None, **extra)`.
  - `app.py`: `create_app(data_path) -> FastAPI`; the working copy lives at `app.state.wc`.
  - CLI: `waybill serve [--port 8000] [--open]`.
  - Test helpers in `conftest.py`: fixtures `data_dir`, `client` (a `TestClient` with `follow_redirects=False`), function `follow(client, response)`, constant `CAR_FORM`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/web/conftest.py` with the full version:

```python
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from waybill_generator.web.app import create_app

FIXTURES = Path(__file__).parent.parent / "fixtures"

# A valid car form as a browser would post it (PRR-12345 in the fixtures).
CAR_FORM = {"road": "PRR", "car_number": "12345", "aar_code": "XM", "capacity_tons": "50",
            "capacity_cuft": "3020", "length_ft": "40", "active": "on"}


@pytest.fixture
def data_dir(tmp_path):
    """A private, writable copy of tests/fixtures."""
    target = tmp_path / "data"
    shutil.copytree(FIXTURES, target)
    return target


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(data_dir), follow_redirects=False)


def follow(client, response):
    """GET the page a 303 redirect points at."""
    assert response.status_code == 303, response.text[:300]
    return client.get(response.headers["location"])
```

Create `tests/web/test_app_lists.py`:

```python
def test_static_assets_are_served_from_the_package(client):
    for name in ("htmx.min.js", "tom-select.complete.min.js", "tom-select.default.min.css", "app.css"):
        assert client.get(f"/static/{name}").status_code == 200, name


def test_home_redirects_to_waybills(client):
    response = client.get("/")
    assert response.status_code == 303 and response.headers["location"] == "/waybills"


def test_waybill_list_shows_a_readable_summary_per_type(client):
    page = client.get("/waybills").text
    assert "Grain: Lewistown Grain Elevator → Altoona Shops" in page       # LOADED
    assert "Altoona → Lewistown" in page                                    # EMPTY
    assert "Lewistown → shop Altoona: Broken coupler" in page               # BAD_ORDER
    assert "PHL → PGH" in page                                              # DEADHEAD with unknown locations
    assert "Lewistown Grain Elevator waiting for Load order" in page        # HOLD
    assert "6 shown of 6" in page


def test_every_collection_lists(client):
    for kind, expected in [("cars", "PRR-12345"), ("locations", "Lewistown"), ("commodities", "Bituminous"),
                           ("railroads", "Form 1304")]:
        page = client.get(f"/{kind}").text
        assert expected in page, kind
        assert f'href="/{kind}/new"' in page


def test_search_and_type_filter(client):
    assert "badorder-1" not in client.get("/waybills?q=grain").text
    filtered = client.get("/waybills?type=BAD_ORDER").text
    assert "badorder-1" in filtered and "1 shown of 6" in filtered
    assert "No matches." in client.get("/cars?q=zzz").text


def test_unknown_collection_or_record_is_404(client):
    assert client.get("/nope").status_code == 404
    assert client.get("/cars/NOPE").status_code == 404


def test_nav_lists_all_collections_and_hides_unsaved_banner_when_clean(client):
    page = client.get("/cars").text
    for title in ("Waybills", "Cars", "Locations", "Commodities", "Railroads"):
        assert f">{title}</a>" in page
    assert "unsaved" not in page
```

Create `tests/web/test_serve.py`:

```python
import shutil

from click.testing import CliRunner

from tests.web.conftest import FIXTURES
from waybill_generator.cli import main


def test_serve_starts_uvicorn_on_loopback_only(monkeypatch):
    import uvicorn
    calls = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.update(kwargs))
    result = CliRunner().invoke(main, ["--data-path", str(FIXTURES), "serve", "--port", "9123"])
    assert result.exit_code == 0, result.output
    assert "http://127.0.0.1:9123" in result.output
    assert calls == {"host": "127.0.0.1", "port": 9123, "log_level": "warning"}


def test_serve_open_flag_opens_the_browser(monkeypatch):
    import webbrowser

    import uvicorn
    opened = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: None)
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
    CliRunner().invoke(main, ["--data-path", str(FIXTURES), "serve", "--open"])
    assert opened == ["http://127.0.0.1:8000"]


def test_serve_reports_unreadable_data_and_exits_nonzero(tmp_path):
    bad = tmp_path / "bad"
    shutil.copytree(FIXTURES, bad)
    (bad / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    result = CliRunner().invoke(main, ["--data-path", str(bad), "serve"])
    assert result.exit_code != 0
    assert "Cannot load data" in result.output and "cars.yaml" in result.output
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_app_lists.py tests/web/test_serve.py -q`

Expected: collection errors — `No module named 'waybill_generator.web.app'` / `serve` command missing.

- [ ] **Step 3: Implement `entities.py`**

```python
"""The five editable collections: how each is listed, searched, and edited."""
from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException
from pydantic import BaseModel

from waybill_generator.cli import _generate_location_id
from waybill_generator.models.car import Car
from waybill_generator.models.commodity import Commodity
from waybill_generator.models.location import Location
from waybill_generator.models.railroad import Railroad

from .references import WAYBILL_CLASSES
from .working_copy import WorkingCopy


@dataclass(frozen=True)
class Entity:
    kind: str
    title: str
    noun: str
    columns: tuple[tuple[str, str], ...]     # (attribute, header)
    search: tuple[str, ...]                  # attributes the search box matches
    model: type[BaseModel] | None = None     # None when the class depends on a chosen type
    preserve: tuple[str, ...] = ()           # fields the form doesn't edit; copied from the existing record
    types: dict[str, type[BaseModel]] | None = None   # selectable record types (waybills)
    type_field: str | None = None                     # the discriminator field ("waybill_type")

    def model_class(self, existing: BaseModel | None, chosen_type: str | None) -> type[BaseModel] | None:
        """The model class to edit: fixed, the existing record's, or the one for the chosen type."""
        if self.types is None:
            return self.model
        if existing is not None:
            return type(existing)
        return self.types.get(chosen_type or "")


ENTITIES: dict[str, Entity] = {e.kind: e for e in (
    Entity("waybills", "Waybills", "waybill",
           (("id", "ID"), ("waybill_type", "Type"), ("summary", "Summary")),
           ("id", "waybill_type", "notes"),
           types=WAYBILL_CLASSES, type_field="waybill_type"),
    Entity("cars", "Cars", "car",
           (("id", "ID"), ("aar_code", "Type"), ("capacity_tons", "Tons"), ("active", "Active")),
           ("id", "aar_code", "notes"), Car),
    Entity("locations", "Locations", "location",
           (("id", "ID"), ("name", "Name"), ("state", "State"), ("industry_count", "Industries")),
           ("id", "name"), Location, preserve=("industries",)),
    Entity("commodities", "Commodities", "commodity",
           (("id", "ID"), ("name", "Name"), ("aar_code", "Code")),
           ("id", "name", "aar_code"), Commodity),
    Entity("railroads", "Railroads", "railroad",
           (("id", "ID"), ("name", "Name"), ("form_number", "Form")),
           ("id", "name"), Railroad),
)}


def get_entity(kind: str) -> Entity:
    if kind not in ENTITIES:
        raise HTTPException(404, f"Unknown collection {kind!r}")
    return ENTITIES[kind]


def _name(getter, record_id: str) -> str:
    try:
        return getter(record_id).name
    except KeyError:
        return record_id


def waybill_summary(wc: WorkingCopy, w) -> str:
    def loc(i: str) -> str:
        return _name(wc.get_location, i)

    def ind(i: str) -> str:
        return _name(wc.get_industry, i)

    t = w.waybill_type
    if t == "LOADED":
        return f"{_name(wc.get_commodity, w.commodity_id)}: {ind(w.shipper_id)} → {ind(w.consignee_id)}"
    if t in ("EMPTY", "DEADHEAD", "MOW"):
        return f"{loc(w.from_location_id)} → {loc(w.to_location_id)}"
    if t == "BAD_ORDER":
        return f"{loc(w.from_location_id)} → shop {loc(w.shop_location_id)}" + (f": {w.defect}" if w.defect else "")
    if t == "HOLD":
        return f"{ind(w.industry_id)} waiting for {w.waiting_for}"
    if t == "STOP_OFF":
        return f"{w.at_location}: {w.for_reason}"
    if t == "TEMPORARY":
        return f"{w.from_location_id} → {w.to_location_id}: {w.commodity_desc}"
    return f"{w.shipper_name} → {w.consignee_name}"   # PERISHABLE, LIVESTOCK


def cell(wc: WorkingCopy, record, attr: str):
    """One list-table cell for a record attribute (or a computed column)."""
    if attr == "summary":
        return waybill_summary(wc, record)
    if attr == "industry_count":
        return len(record.industries)
    value = getattr(record, attr)
    if isinstance(value, bool):
        return "✓" if value else ""
    if isinstance(value, list):
        return ", ".join(value)
    return "" if value is None else value


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def suggest_id(wc: WorkingCopy, kind: str, values: dict) -> str:
    """A suggested id for a new record; empty when nothing sensible can be derived yet."""
    if kind == "waybills":
        nums = [int(m.group(1)) for r in wc.records("waybills") if (m := re.fullmatch(r"waybill-(\d+)", r.id))]
        return f"waybill-{max(nums, default=0) + 1}"
    if kind == "cars":
        road, number = values.get("road"), values.get("car_number")
        return f"{road}-{number}" if road and number else ""
    if kind == "locations":
        name = values.get("name")
        return _generate_location_id(name, {r.id for r in wc.records("locations")}) if name else ""
    if kind == "commodities":
        return _slug(values.get("name") or "")
    return ""
```

- [ ] **Step 4: Implement `context.py`**

```python
"""Shared request helpers for the web routes."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .entities import ENTITIES
from .forms import build_fields, build_options
from .references import Ref
from .working_copy import WorkingCopy

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")


def wc_of(request: Request) -> WorkingCopy:
    return request.app.state.wc


def render(request: Request, name: str, status: int = 200, **context):
    wc = wc_of(request)
    base = {
        "entities": list(ENTITIES.values()), "change_count": wc.change_count(),
        "flash": request.query_params.get("flash"), "wc": wc,
    }
    return templates.TemplateResponse(request, name, {**base, **context}, status_code=status)


def redirect(url: str, flash: str | None = None) -> RedirectResponse:
    """303 to `url`, optionally carrying a one-shot message shown on the next page."""
    if flash:
        url += ("&" if "?" in url else "?") + "flash=" + quote(flash)
    return RedirectResponse(url, status_code=303)


def blocked_message(refs: list[Ref]) -> str:
    shown = ", ".join(r.describe() for r in refs[:5])
    more = f" and {len(refs) - 5} more" if len(refs) > 5 else ""
    return f"Can't delete: still used by {shown}{more}"


def form_page(request: Request, *, kind: str, heading: str, model_cls: type[BaseModel], values: dict,
              errors: dict, editing: bool, action: str, cancel_url: str,
              delete_url: str | None = None, **extra):
    """Render the generic edit form (422 when `errors` is non-empty)."""
    fields = build_fields(model_cls, values, errors, build_options(wc_of(request)), editing=editing)
    return render(request, "edit.html", 422 if errors else 200, kind=kind, active=kind, heading=heading,
                  fields=fields, action=action, cancel_url=cancel_url, delete_url=delete_url, **extra)
```

- [ ] **Step 5: Implement the list route and app factory**

Create `waybill_generator/web/routes_records.py` (Task 6 replaces this file with the full version):

```python
"""List, create, edit, and delete records of any collection."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .context import render, wc_of
from .entities import cell, get_entity

router = APIRouter()


@router.get("/{kind}")
def list_page(request: Request, kind: str, q: str = "", type: str = ""):
    entity = get_entity(kind)
    wc = wc_of(request)
    needle = q.strip().lower()
    rows = []
    for record in wc.records(kind):
        if type and entity.type_field and getattr(record, entity.type_field, None) != type:
            continue
        haystack = " ".join(str(getattr(record, f, "") or "") for f in entity.search).lower()
        if needle and needle not in haystack:
            continue
        rows.append({
            "id": record.id, "status": wc.status(kind, record.id),
            "cells": [cell(wc, record, attr) for attr, _ in entity.columns],
        })
    return render(request, "list.html", entity=entity, rows=rows, q=q, type=type, active=kind,
                  deleted=wc.deleted_ids(kind), total=len(wc.records(kind)),
                  type_choices=list(entity.types) if entity.types else [])
```

Create `waybill_generator/web/app.py` (Tasks 7 and 8 each add one router):

```python
"""FastAPI app: server-rendered pages over a WorkingCopy of the data files."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import routes_records
from .context import WEB_DIR
from .working_copy import WorkingCopy


def create_app(data_path: str | Path) -> FastAPI:
    """Build the app. Raises DataError if a data file can't be read."""
    app = FastAPI(title="Mifflin Ops")
    app.state.wc = WorkingCopy(data_path)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/")
    def home():
        return RedirectResponse("/waybills", status_code=303)

    app.include_router(routes_records.router)
    return app
```

- [ ] **Step 6: Add the templates and stylesheet**

`waybill_generator/web/templates/base.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Mifflin Ops{% endblock %}</title>
  <link rel="stylesheet" href="/static/tom-select.default.min.css">
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js"></script>
  <script src="/static/tom-select.complete.min.js"></script>
  <script src="/static/pickers.js" defer></script>
</head>
<body>
<header class="bar">
  <span class="brand">🚂 Mifflin Ops</span>
  <nav>
    {% for e in entities %}<a href="/{{ e.kind }}" class="{{ 'on' if e.kind == active else '' }}">{{ e.title }}</a>{% endfor %}
  </nav>
  <span class="spacer"></span>
  {% if change_count %}
    <span class="dirty">{{ change_count }} unsaved change{{ '' if change_count == 1 else 's' }}</span>
    <a class="btn pri" href="/review">Review &amp; Save</a>
    <form method="post" action="/discard" class="inline" onsubmit="return confirm('Discard all unsaved changes?')">
      <button class="btn">Discard</button>
    </form>
  {% endif %}
</header>
{% if flash %}<div class="flash">{{ flash }}</div>{% endif %}
<main>{% block content %}{% endblock %}</main>
</body>
</html>
```

`waybill_generator/web/templates/list.html`:

```html
{% extends "base.html" %}
{% block title %}{{ entity.title }} · Mifflin Ops{% endblock %}
{% block content %}
<h1>{{ entity.title }}</h1>
<form method="get" class="row">
  <input type="search" name="q" value="{{ q }}" placeholder="Search {{ entity.title | lower }}…" class="grow">
  {% if type_choices %}
    <select name="type">
      <option value="">All types</option>
      {% for t in type_choices %}<option value="{{ t }}" {{ 'selected' if t == type else '' }}>{{ t }}</option>{% endfor %}
    </select>
  {% endif %}
  <button class="btn">Filter</button>
  <a class="btn pri" href="/{{ entity.kind }}/new">+ New {{ entity.noun }}</a>
</form>
<table>
  <thead><tr>{% for _, header in entity.columns %}<th>{{ header }}</th>{% endfor %}<th></th></tr></thead>
  <tbody>
  {% for row in rows %}
    <tr class="{{ row.status or '' }}">
      {% for value in row.cells %}
        <td>{% if loop.first %}<a href="/{{ entity.kind }}/{{ row.id }}">{{ value }}</a>{% else %}{{ value }}{% endif %}</td>
      {% endfor %}
      <td>{% if row.status %}<span class="tag {{ row.status }}">{{ row.status | upper }}</span>{% endif %}</td>
    </tr>
  {% else %}
    <tr><td colspan="{{ entity.columns | length + 1 }}" class="muted">No matches.</td></tr>
  {% endfor %}
  {% for rid in deleted %}
    <tr class="deleted"><td>{{ rid }}</td><td colspan="{{ entity.columns | length - 1 }}"></td><td><span class="tag deleted">DELETED</span></td></tr>
  {% endfor %}
  </tbody>
</table>
<p class="muted">{{ rows | length }} shown of {{ total }} · click an ID to edit</p>
{% endblock %}
```

`waybill_generator/web/static/app.css`:

```css
:root { --bg:#f5f5f7; --panel:#fff; --line:#d1d1d6; --text:#1d1d1f; --muted:#86868b; --accent:#0071e3; --warn:#ff9f0a; --ok:#34c759; --err:#ff3b30; }
@media (prefers-color-scheme: dark) { :root { --bg:#1d1d1f; --panel:#2d2d2f; --line:#424245; --text:#f5f5f7; --accent:#0a84ff; } }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.5 system-ui, sans-serif; background:var(--bg); color:var(--text); }
main { max-width: 1100px; margin: 0 auto; padding: 1rem 1.25rem 3rem; }
h1 { font-size: 1.4rem; margin: .5rem 0 1rem; } h2 { font-size: 1.1rem; margin-top: 2rem; }
.bar { display:flex; align-items:center; gap:1rem; padding:.6rem 1.25rem; background:var(--panel); border-bottom:1px solid var(--line); flex-wrap:wrap; }
.bar nav { display:flex; gap:1rem; } .bar nav a { color:var(--muted); text-decoration:none; padding-bottom:2px; }
.bar nav a.on { color:var(--accent); border-bottom:2px solid var(--accent); font-weight:600; }
.brand { font-weight:700; } .spacer { flex:1; } .inline { display:inline; margin:0; }
.dirty { background:rgba(255,159,10,.18); color:var(--warn); border:1px solid var(--warn); border-radius:999px; padding:.05rem .7rem; font-weight:600; font-size:.8rem; }
.btn { display:inline-block; border:1px solid var(--line); background:var(--panel); color:var(--text); border-radius:5px; padding:.3rem .8rem; font:inherit; text-decoration:none; cursor:pointer; }
.btn.pri { background:var(--accent); border-color:var(--accent); color:#fff; font-weight:600; } .btn.danger { color:var(--err); border-color:var(--err); }
.btn[disabled] { opacity:.5; cursor:not-allowed; }
.flash { background:rgba(0,113,227,.12); border-bottom:1px solid var(--accent); padding:.5rem 1.25rem; }
.row { display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; margin:.8rem 0; } .grow { flex:1; min-width:12rem; }
/* direct children only, so Tom Select's inner search <input> is not restyled */
.field > input, .field > textarea, .field > select { width:100%; }
.field > input, .field > textarea, .field > select, .row > input, .row > select { padding:.35rem .6rem; border:1px solid var(--line); border-radius:5px; background:var(--bg); color:var(--text); font:inherit; }
.row > input, .row > select { width:auto; }
table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:6px; }
th { text-align:left; font-size:.7rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); padding:.4rem .6rem; border-bottom:1px solid var(--line); }
td { padding:.4rem .6rem; border-bottom:1px solid var(--line); } td a { color:var(--accent); text-decoration:none; font-weight:600; }
tr.modified td { background:rgba(255,159,10,.10); } tr.new td { background:rgba(52,199,89,.12); } tr.deleted td { background:rgba(255,59,48,.10); text-decoration:line-through; color:var(--muted); }
.tag { font-size:.68rem; font-weight:700; padding:.05rem .4rem; border-radius:4px; background:var(--line); color:var(--muted); }
.tag.modified { background:rgba(255,159,10,.25); color:var(--warn); } .tag.new { background:rgba(52,199,89,.25); color:var(--ok); } .tag.deleted { background:rgba(255,59,48,.2); color:var(--err); }
.muted { color:var(--muted); }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:1rem 1.25rem; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:0 1.5rem; } .field { margin-bottom:.9rem; } .field.wide { grid-column:1 / -1; }
.field label { display:block; font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-bottom:.2rem; }
.field.has-error input, .field.has-error .ts-control { border-color:var(--err); } .hint { font-size:.75rem; color:var(--muted); } .hint.err { color:var(--err); }
.banner { border-radius:6px; padding:.5rem .8rem; margin-bottom:.8rem; } .banner.ok { background:rgba(52,199,89,.14); border:1px solid var(--ok); }
.banner.warn { background:rgba(255,159,10,.14); border:1px solid var(--warn); } .banner.err { background:rgba(255,59,48,.12); border:1px solid var(--err); }
.diff { font:12.5px ui-monospace, Menlo, monospace; border:1px solid var(--line); border-radius:6px; overflow:hidden; margin-bottom:1rem; background:var(--panel); }
.diff .h { background:var(--line); padding:.3rem .7rem; font-weight:600; } .diff .l { padding:0 .7rem; white-space:pre-wrap; }
.diff .a { background:rgba(52,199,89,.16); } .diff .d { background:rgba(255,59,48,.14); } .diff .c { color:var(--muted); }
.ts-wrapper .ts-control, .ts-wrapper.single .ts-control { background:var(--bg); color:var(--text); border-color:var(--line); border-radius:5px; box-shadow:none; }
.ts-control input, .ts-control .item { color:var(--text); }
.ts-dropdown { background:var(--panel); color:var(--text); border-color:var(--line); }
.ts-dropdown .active { background:rgba(0,113,227,.14); color:var(--text); }
.ts-dropdown .optgroup-header { background:var(--line); color:var(--muted); font-size:.68rem; text-transform:uppercase; letter-spacing:.06em; }
.ts-dropdown .n { font-weight:600; } .ts-dropdown .m { font-size:.75rem; color:var(--muted); }
@media (max-width: 700px) { .grid { grid-template-columns:1fr; } }
```

- [ ] **Step 7: Add the `serve` command**

Append to the end of `waybill_generator/cli.py` (after two blank lines):

```python
@main.command()
@click.option("--port", default=8000, show_default=True, type=int, help="Port to listen on")
@click.option("--open", "open_browser", is_flag=True, help="Open the UI in your browser")
@click.pass_context
def serve(ctx, port, open_browser):
    """Run the local web UI for editing data (binds 127.0.0.1 only)."""
    import uvicorn

    from waybill_generator.web.app import create_app
    from waybill_generator.web.working_copy import DataError

    try:
        app = create_app(ctx.obj["data_path"])
    except DataError as exc:
        raise click.ClickException(f"Cannot load data from {ctx.obj['data_path']}: {exc}") from exc
    url = f"http://127.0.0.1:{port}"
    click.echo(f"Serving {url}  (Ctrl+C to stop)")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest -q`

Expected: everything passes, including the existing suite (10 new tests).

- [ ] **Step 9: Lint**

Run: `uv run ruff check waybill_generator/web tests/web && uv run ruff check waybill_generator/cli.py --output-format concise | tail -1`

Expected: `All checks passed!` for the new dirs; `cli.py` still reports the same 4 fixable / 7 total findings it had before this task (none from `serve`).

- [ ] **Step 10: Commit**

```bash
git add waybill_generator/web \
  waybill_generator/cli.py \
  tests/web
git commit -m "$(cat <<'EOF'
feat: add web UI shell, list pages, and `waybill serve`

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Create, edit, and delete records (all collections)

**Files:**
- Replace: `waybill_generator/web/routes_records.py`
- Create: `waybill_generator/web/templates/edit.html`, `_fields.html`; `waybill_generator/web/static/pickers.js`
- Test: `tests/web/test_app_records.py`

**Interfaces:**
- Consumes: everything from Tasks 3–5.
- Produces (routes, all under `routes_records.router`, in this order): `GET /{kind}` list; `GET /{kind}/fields` (htmx fragment; 404 unless the collection has types; 422 on unknown type); `GET /{kind}/{rid}` (`rid == "new"` for a blank form); `POST /{kind}/{rid}` (create/apply; 422 re-renders with errors; 303 to the list with `flash`); `POST /{kind}/{rid}/delete` (blocked deletes redirect back to the record with a message).
- Behaviours to preserve: ids are immutable on edit; a blank id on a new car/location/commodity is derived from the form; a location's `industries` are preserved by the location form; the waybill type is fixed after creation.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_app_records.py`:

```python
from tests.web.conftest import CAR_FORM, follow


def test_new_waybill_form_suggests_the_next_id_and_is_wired_for_type_swaps(client):
    page = client.get("/waybills/new").text
    assert 'value="waybill-2"' in page                       # fixtures hold waybill-1 only
    assert 'hx-get="/waybills/fields"' in page and 'name="waybill_type"' in page
    assert "data-picker" in page and 'data-rank-field="commodity_id"' in page
    assert "commodity_id" in client.get("/waybills/new?waybill_type=LOADED").text
    assert "from_location_id" in client.get("/waybills/new?waybill_type=EMPTY").text


def test_type_fragment_swaps_fields_and_keeps_typed_values(client):
    fragment = client.get("/waybills/fields?waybill_type=EMPTY&id=waybill-9&notes=hello")
    assert fragment.status_code == 200 and "<html" not in fragment.text
    assert "from_location_id" in fragment.text and "commodity_id" not in fragment.text
    assert 'value="waybill-9"' in fragment.text and "hello" in fragment.text
    assert client.get("/waybills/fields?waybill_type=NOPE").status_code == 422
    assert client.get("/cars/fields").status_code == 404


def test_create_waybill_is_staged_and_marked_new(client):
    response = client.post("/waybills/new", data={
        "waybill_type": "LOADED", "id": "waybill-2", "originating_railroad_id": "PRR", "commodity_id": "coal",
        "shipper_id": "ALT-SHOP", "consignee_id": "LEW-GRAIN", "routing": ["ALT", "LJ"]})
    page = follow(client, response).text
    assert "Applied waybill waybill-2" in page and "1 unsaved change" in page and "NEW" in page
    assert client.get("/waybills/waybill-2").status_code == 200


def test_create_waybill_reports_missing_required_and_duplicate_ids(client):
    response = client.post("/waybills/new", data={"waybill_type": "LOADED", "id": "waybill-2",
                                                   "originating_railroad_id": "PRR", "commodity_id": "coal",
                                                   "shipper_id": "ALT-SHOP"})
    assert response.status_code == 422 and "Required" in response.text and 'value="waybill-2"' in response.text
    response = client.post("/waybills/new", data={"waybill_type": "HOLD", "id": "waybill-1",
                                                   "originating_railroad_id": "PRR", "industry_id": "LEW-GRAIN",
                                                   "waiting_for": "x"})
    assert response.status_code == 422 and "Already exists" in response.text
    assert client.post("/waybills/new", data={"waybill_type": "NOPE"}).status_code == 422


def test_editing_a_waybill_keeps_its_type_and_id(client):
    page = client.get("/waybills/hold-1").text
    assert 'value="HOLD"' in page and "readonly" in page and 'hx-get' not in page
    response = client.post("/waybills/hold-1", data={"originating_railroad_id": "PRR", "industry_id": "LEW-GRAIN",
                                                      "waiting_for": "Empty car", "id": "ignored"})
    assert "Applied waybill hold-1" in follow(client, response).text
    assert "Empty car" in client.get("/waybills").text


def test_car_form_reports_non_numeric_input(client):
    response = client.post("/cars/PRR-12345", data={**CAR_FORM, "capacity_tons": "fifty"})
    assert response.status_code == 422 and "Must be a whole number" in response.text


def test_new_car_id_is_derived_when_left_blank(client):
    response = client.post("/cars/new", data={**CAR_FORM, "car_number": "777"})
    assert "Applied car PRR-777" in follow(client, response).text


def test_new_commodity_and_location_ids_are_generated_from_the_name(client):
    assert "Applied commodity iron-ore" in follow(client, client.post("/commodities/new", data={"name": "Iron Ore"})).text
    assert "Applied location PHI" in follow(client, client.post("/locations/new", data={"name": "Philadelphia"})).text
    assert client.post("/railroads/new", data={"name": "Nickel Plate", "form_number": "F1"}).status_code == 422   # id can't be derived


def test_editing_a_location_keeps_its_industries(client):
    follow(client, client.post("/locations/LEW", data={"name": "Lewistown", "state": "PA", "on_layout": "on"}))
    assert "LEW-GRAIN" in client.get("/locations/LEW").text


def test_delete_is_blocked_while_referenced_and_allowed_otherwise(client):
    blocked = client.post("/commodities/grain/delete")
    assert blocked.headers["location"].startswith("/commodities/grain?flash=")
    assert "waybill-1" in follow(client, blocked).text
    assert "Deleted PRR-67890" in follow(client, client.post("/cars/PRR-67890/delete")).text
    assert "DELETED" in client.get("/cars").text
    assert client.post("/cars/NOPE/delete").status_code == 404


def test_the_picker_script_is_served(client):
    assert client.get("/static/pickers.js").status_code == 200
    assert "/static/pickers.js" in client.get("/waybills/new").text
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_app_records.py -q`

Expected: failures — the routes and templates don't exist yet (404 / assertion errors).

- [ ] **Step 3: Replace `routes_records.py` with the full version**

```python
"""List, create, edit, and delete records of any collection."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .context import blocked_message, form_page, redirect, render, wc_of
from .entities import cell, get_entity, suggest_id
from .forms import build_fields, build_model, build_options, initial_values, parse_form
from .working_copy import ReferenceBlocked

router = APIRouter()


@router.get("/{kind}")
def list_page(request: Request, kind: str, q: str = "", type: str = ""):
    entity = get_entity(kind)
    wc = wc_of(request)
    needle = q.strip().lower()
    rows = []
    for record in wc.records(kind):
        if type and entity.type_field and getattr(record, entity.type_field, None) != type:
            continue
        haystack = " ".join(str(getattr(record, f, "") or "") for f in entity.search).lower()
        if needle and needle not in haystack:
            continue
        rows.append({
            "id": record.id, "status": wc.status(kind, record.id),
            "cells": [cell(wc, record, attr) for attr, _ in entity.columns],
        })
    return render(request, "list.html", entity=entity, rows=rows, q=q, type=type, active=kind,
                  deleted=wc.deleted_ids(kind), total=len(wc.records(kind)),
                  type_choices=list(entity.types) if entity.types else [])


@router.get("/{kind}/fields")
def type_fields(request: Request, kind: str):
    """htmx fragment: the field block for the chosen record type (e.g. waybill type)."""
    entity = get_entity(kind)
    if not entity.types:
        raise HTTPException(404)
    model_cls = entity.types.get(request.query_params.get(entity.type_field, ""))
    if model_cls is None:
        raise HTTPException(422, f"Unknown {entity.type_field}")
    values, _ = parse_form(model_cls, request.query_params)
    values = {**initial_values(model_cls), **{k: v for k, v in values.items() if v not in (None, "", [])}}
    fields = build_fields(model_cls, values, {}, build_options(wc_of(request)), editing=False)
    return render(request, "_fields.html", fields=fields)


def _record_page(request: Request, kind: str, rid: str, model_cls, values: dict, errors: dict):
    entity = get_entity(kind)
    wc = wc_of(request)
    is_new = rid == "new"
    extra: dict = {"record_id": rid}
    if entity.types:
        extra.update(type_choices=list(entity.types), type_field=entity.type_field, is_new=is_new,
                     type_value=model_cls.model_fields[entity.type_field].default)
    if kind == "locations" and not is_new:
        extra["industries"] = wc.get_location(rid).industries
    return form_page(
        request, kind=kind, heading=(f"New {entity.noun}" if is_new else f"{entity.noun.capitalize()} {rid}"),
        model_cls=model_cls, values=values, errors=errors, editing=not is_new,
        action=f"/{kind}/{rid}", cancel_url=f"/{kind}",
        delete_url=None if is_new else f"/{kind}/{rid}/delete", **extra,
    )


@router.get("/{kind}/{rid}")
def edit_page(request: Request, kind: str, rid: str):
    entity = get_entity(kind)
    wc = wc_of(request)
    if rid == "new":
        chosen = request.query_params.get(entity.type_field or "", "")
        model_cls = entity.model_class(None, chosen or (next(iter(entity.types)) if entity.types else None))
        if model_cls is None:
            raise HTTPException(422, f"Unknown {entity.type_field}")
        values = initial_values(model_cls)
        if suggested := suggest_id(wc, kind, values):
            values["id"] = suggested
        return _record_page(request, kind, rid, model_cls, values, {})
    if not wc.has(kind, rid):
        raise HTTPException(404)
    record = wc.get(kind, rid)
    return _record_page(request, kind, rid, type(record), record.model_dump(mode="json"), {})


@router.post("/{kind}/{rid}")
async def save_record(request: Request, kind: str, rid: str):
    entity = get_entity(kind)
    wc = wc_of(request)
    form = await request.form()
    is_new = rid == "new"
    existing = None if is_new else (wc.get(kind, rid) if wc.has(kind, rid) else None)
    if not is_new and existing is None:
        raise HTTPException(404)
    model_cls = entity.model_class(existing, form.get(entity.type_field) if entity.type_field else None)
    if model_cls is None:
        raise HTTPException(422, f"Unknown {entity.type_field}")

    values, errors = parse_form(model_cls, form)
    if is_new and "id" in errors and (generated := suggest_id(wc, kind, values)):
        values["id"] = generated
        errors.pop("id")
    if is_new and values.get("id") and wc.has(kind, values["id"]):
        errors["id"] = "Already exists"
    if not is_new:
        values["id"] = rid           # ids are immutable once created
        errors.pop("id", None)
    if entity.type_field:
        values[entity.type_field] = model_cls.model_fields[entity.type_field].default
    for name in entity.preserve:     # fields the form doesn't edit (a location's industries)
        values[name] = getattr(existing, name) if existing else []

    model, more = build_model(model_cls, values) if not errors else (None, {})
    errors.update(more)
    if errors:
        return _record_page(request, kind, rid, model_cls, values, errors)
    wc.apply(kind, model)
    return redirect(f"/{kind}", f"Applied {entity.noun} {model.id}")


@router.post("/{kind}/{rid}/delete")
def delete_record(request: Request, kind: str, rid: str):
    get_entity(kind)
    try:
        wc_of(request).delete(kind, rid)
    except ReferenceBlocked as exc:
        return redirect(f"/{kind}/{rid}", blocked_message(exc.refs))
    except KeyError:
        raise HTTPException(404) from None
    return redirect(f"/{kind}", f"Deleted {rid}")
```

- [ ] **Step 4: Add the form templates**

`waybill_generator/web/templates/edit.html`:

```html
{% extends "base.html" %}
{% block title %}{{ heading }} · Mifflin Ops{% endblock %}
{% block content %}
<h1>{{ heading }}</h1>
<form method="post" action="{{ action }}" class="card">
  {% if type_choices %}
    {% if is_new %}
      <div class="field">
        <label for="f-{{ type_field }}">Type</label>
        <select id="f-{{ type_field }}" name="{{ type_field }}"
                hx-get="/{{ kind }}/fields" hx-target="#fields" hx-include="closest form" hx-trigger="change">
          {% for t in type_choices %}<option value="{{ t }}" {{ 'selected' if t == type_value else '' }}>{{ t }}</option>{% endfor %}
        </select>
        <div class="hint">Changing the type swaps the fields below.</div>
      </div>
    {% else %}
      <input type="hidden" name="{{ type_field }}" value="{{ type_value }}">
      <p><span class="tag">{{ type_value }}</span></p>
    {% endif %}
  {% endif %}
  <div id="fields" class="grid">{% include "_fields.html" %}</div>
  <div class="row">
    <button class="btn pri">Apply</button>
    <a class="btn" href="{{ cancel_url }}">Cancel</a>
    <span class="spacer"></span>
    {% if delete_url %}<button class="btn danger" formaction="{{ delete_url }}" formnovalidate>Delete</button>{% endif %}
  </div>
</form>
{% if industries is defined %}
  <h2>Industries</h2>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Track</th><th>Cap.</th><th>Ships</th><th>Receives</th></tr></thead>
    <tbody>
    {% for i in industries %}
      <tr>
        <td><a href="/locations/{{ record_id }}/industries/{{ i.id }}">{{ i.id }}</a></td>
        <td>{{ i.name }}</td><td>{{ i.track or '' }}</td><td>{{ i.car_capacity or '' }}</td>
        <td>{{ i.ships | join(', ') }}</td><td>{{ i.receives | join(', ') }}</td>
      </tr>
    {% else %}
      <tr><td colspan="6" class="muted">No industries yet.</td></tr>
    {% endfor %}
    </tbody>
  </table>
  <p><a class="btn" href="{{ action }}/industries/new">+ Add industry</a></p>
{% elif kind == "locations" and not delete_url %}
  <p class="muted">Apply this location first, then add its industries.</p>
{% endif %}
{% endblock %}
```

`waybill_generator/web/templates/_fields.html`:

```html
{% macro render_field(f) %}
<div class="field{{ ' has-error' if f.error else '' }}{{ ' wide' if f.kind in ('textarea', 'tags') else '' }}">
  <label for="f-{{ f.name }}">{{ f.label }}{% if f.required %} *{% endif %}</label>
  {% if f.kind == "textarea" %}
    <textarea id="f-{{ f.name }}" name="{{ f.name }}" rows="3">{{ f.value or "" }}</textarea>
  {% elif f.kind == "checkbox" %}
    <input type="checkbox" id="f-{{ f.name }}" name="{{ f.name }}" {{ 'checked' if f.value else '' }}>
  {% elif f.kind in ("select", "multiselect", "tags") %}
    <select id="f-{{ f.name }}" name="{{ f.name }}" data-picker placeholder="Search…"
            {{ 'multiple' if f.kind != 'select' else '' }}
            {% if f.kind == "tags" %}data-create="1"{% endif %}
            {% if f.rank %}data-rank-field="{{ f.rank[0] }}" data-rank-list="{{ f.rank[1] }}"{% endif %}>
      {% if f.kind == "select" %}<option value=""></option>{% endif %}
      {% for o in f.options %}
        <option value="{{ o.value }}" data-meta="{{ o.meta }}" data-ships="{{ o.ships or '' }}" data-receives="{{ o.receives or '' }}"
                {{ 'selected' if o.value in f.selected else '' }}>{{ o.text }}</option>
      {% endfor %}
    </select>
  {% else %}
    <input type="{{ 'number' if f.kind == 'number' else 'text' }}" id="f-{{ f.name }}" name="{{ f.name }}"
           value="{{ '' if f.value is none else f.value }}" {{ 'readonly' if f.readonly else '' }}>
  {% endif %}
  {% if f.error %}<div class="hint err">{{ f.error }}</div>{% endif %}
</div>
{% endmacro %}
{% for f in fields %}{{ render_field(f) }}{% endfor %}
```

- [ ] **Step 5: Add `pickers.js`**

`waybill_generator/web/static/pickers.js` — initialises Tom Select on every `select[data-picker]`, and floats industries that ship/receive the chosen commodity to the top of the shipper/consignee pickers (never hiding the rest). Pickers are initialised on `htmx:afterSettle`, **not** `afterSwap`: htmx resets the `class` of swapped-in elements that share an id with the old ones (e.g. `originating_railroad_id`), which would un-hide the native `<select>`.

```javascript
// Searchable pickers (Tom Select) for every <select data-picker>, plus commodity-aware ranking.
function initPickers(root) {
  root.querySelectorAll("select[data-picker]").forEach((el) => {
    if (el.tomselect) return;
    const ts = new TomSelect(el, {
      create: el.dataset.create === "1",
      maxOptions: null,
      plugins: el.multiple ? ["remove_button"] : ["clear_button"],
      searchField: ["text", "meta"],
      lockOptgroupOrder: true,
      render: {
        option: (d, esc) => `<div><span class="n">${esc(d.text)}</span><div class="m">${esc(d.meta || "")}</div></div>`,
        item: (d, esc) => `<div>${esc(d.text)}</div>`,
      },
    });
    if (el.dataset.rankField) wireRanking(el, ts);
  });
}

// Float industries that ship/receive the chosen commodity to the top; never hide the rest.
function wireRanking(el, ts) {
  const source = document.getElementById("f-" + el.dataset.rankField);
  if (!source) return;
  const list = el.dataset.rankList;                       // "ships" or "receives"
  const apply = () => {
    const commodity = source.value;
    const name = commodity && source.selectedOptions[0] ? source.selectedOptions[0].text : "";
    ts.addOptionGroup("match", { label: `${list === "ships" ? "Ships" : "Receives"} ${name}` });
    ts.addOptionGroup("other", { label: "Other industries" });
    Object.keys(ts.options).forEach((key) => {
      const o = ts.options[key];
      const listed = (o[list] || "").split(",").filter(Boolean);
      const group = !commodity ? undefined : listed.includes(commodity) ? "match" : "other";
      ts.updateOption(key, Object.assign({}, o, { optgroup: group }));
    });
    ts.refreshOptions(false);
  };
  source.addEventListener("change", apply);
  apply();
}

document.addEventListener("DOMContentLoaded", () => initPickers(document));
// After the type swap, not before: htmx "settles" swapped elements that share an id with the old
// ones (e.g. originating_railroad_id) by resetting their class, which would un-hide the native select.
document.body.addEventListener("htmx:afterSettle", (e) => initPickers(e.target));
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q`

Expected: everything passes (11 new tests).

- [ ] **Step 7: Lint**

Run: `uv run ruff check waybill_generator/web tests/web`

Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add waybill_generator/web \
  tests/web
git commit -m "$(cat <<'EOF'
feat: add record create/edit/delete forms with searchable pickers

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Location industries editor

**Files:**
- Create: `waybill_generator/web/routes_industries.py`
- Replace: `waybill_generator/web/app.py`
- Test: `tests/web/test_app_industries.py`

**Interfaces:**
- Consumes: `form_page`, `redirect`, `blocked_message`, `wc_of` (Task 5); `WorkingCopy.apply_industry` / `delete_industry` / `industry_ids` (Task 3); `_generate_industry_id` from `cli.py`.
- Produces routes: `GET /locations/{loc_id}/industries/{iid}` (`iid == "new"` for blank), `POST` same path (apply; id generated from the name when blank), `POST .../delete` (blocked while waybills use it). `create_app` includes `routes_industries.router` **before** `routes_records.router`.
- The location page already lists industries and links to these routes (Task 6's `edit.html`).

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_app_industries.py`:

```python
from tests.web.conftest import follow


def test_location_page_lists_industries_with_links(client):
    page = client.get("/locations/LEW").text
    assert "Industries" in page and "/locations/LEW/industries/LEW-GRAIN" in page
    assert "/locations/LEW/industries/new" in page
    assert "Apply this location first" in client.get("/locations/new").text


def test_add_edit_and_remove_an_industry(client):
    response = client.post("/locations/LEW/industries/new", data={
        "name": "Lewistown Cement Co.", "track": "2", "car_capacity": "2", "ships": ["grain"], "receives": ["coal"]})
    assert "Applied industry LEW-LEWIST" in follow(client, response).text              # id generated from the name
    assert "Lewistown Cement Co." in client.get("/locations/LEW").text
    page = client.get("/locations/LEW/industries/LEW-LEWIST").text
    assert "data-picker" in page and "readonly" in page
    follow(client, client.post("/locations/LEW/industries/LEW-LEWIST",
                               data={"name": "Lewistown Cement", "track": "2", "car_capacity": "3", "ships": ["grain"]}))
    assert "Lewistown Cement<" in client.get("/locations/LEW").text
    assert "Removed industry LEW-LEWIST" in follow(client, client.post("/locations/LEW/industries/LEW-LEWIST/delete")).text


def test_industry_validation_and_duplicates(client):
    response = client.post("/locations/LEW/industries/new", data={"track": "1"})
    assert response.status_code == 422 and "Required" in response.text
    response = client.post("/locations/LEW/industries/new", data={"id": "ALT-SHOP", "name": "Dup"})
    assert response.status_code == 422 and "Already exists" in response.text


def test_removing_an_industry_that_waybills_use_is_blocked(client):
    response = client.post("/locations/LEW/industries/LEW-GRAIN/delete")             # shipper on waybill-1
    assert "/industries/LEW-GRAIN?flash=" in response.headers["location"]
    assert "waybill-1" in follow(client, response).text


def test_unknown_location_or_industry_is_404(client):
    assert client.get("/locations/NOPE/industries/new").status_code == 404
    assert client.get("/locations/LEW/industries/NOPE").status_code == 404
    assert client.post("/locations/NOPE/industries/new", data={"name": "X"}).status_code == 404
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_app_industries.py -q`

Expected: failures — the industry routes return 404 / 405.

- [ ] **Step 3: Implement the router**

```python
"""Add, edit, and remove the industries nested under a location."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from waybill_generator.cli import _generate_industry_id
from waybill_generator.models.location import Industry

from .context import blocked_message, form_page, redirect, wc_of
from .forms import build_model, initial_values, parse_form
from .working_copy import ReferenceBlocked

router = APIRouter()


def _industry_page(request: Request, loc_id: str, iid: str, values: dict | None = None,
                   errors: dict | None = None):
    wc = wc_of(request)
    if not wc.has("locations", loc_id):
        raise HTTPException(404)
    is_new = iid == "new"
    if not is_new and iid not in {i.id for i in wc.get_location(loc_id).industries}:
        raise HTTPException(404)
    if values is None:
        values = initial_values(Industry) if is_new else wc.get_industry(iid).model_dump(mode="json")
    return form_page(
        request, kind="locations", heading=("New industry" if is_new else f"Industry {iid}"),
        model_cls=Industry, values=values, errors=errors or {}, editing=not is_new,
        action=f"/locations/{loc_id}/industries/{iid}", cancel_url=f"/locations/{loc_id}",
        delete_url=None if is_new else f"/locations/{loc_id}/industries/{iid}/delete",
    )


@router.get("/locations/{loc_id}/industries/{iid}")
def industry_form(request: Request, loc_id: str, iid: str):
    return _industry_page(request, loc_id, iid)


@router.post("/locations/{loc_id}/industries/{iid}")
async def industry_save(request: Request, loc_id: str, iid: str):
    wc = wc_of(request)
    if not wc.has("locations", loc_id):
        raise HTTPException(404)
    form = await request.form()
    is_new = iid == "new"
    values, errors = parse_form(Industry, form)
    if is_new and "id" in errors and values.get("name"):
        values["id"] = _generate_industry_id(loc_id, values["name"], wc.industry_ids())
        errors.pop("id")
    if not is_new:
        values["id"] = iid
        errors.pop("id", None)
    elif values.get("id") in wc.industry_ids():
        errors["id"] = "Already exists"
    values["location_id"] = loc_id
    model, more = build_model(Industry, values) if not errors else (None, {})
    errors.update(more)
    if errors:
        return _industry_page(request, loc_id, iid, values, errors)
    wc.apply_industry(loc_id, model)
    return redirect(f"/locations/{loc_id}", f"Applied industry {model.id}")


@router.post("/locations/{loc_id}/industries/{iid}/delete")
def industry_delete(request: Request, loc_id: str, iid: str):
    try:
        wc_of(request).delete_industry(loc_id, iid)
    except ReferenceBlocked as exc:
        return redirect(f"/locations/{loc_id}/industries/{iid}", blocked_message(exc.refs))
    return redirect(f"/locations/{loc_id}", f"Removed industry {iid}")
```

- [ ] **Step 4: Register it in `app.py`**

Replace `waybill_generator/web/app.py`:

```python
"""FastAPI app: server-rendered pages over a WorkingCopy of the data files."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import routes_industries, routes_records
from .context import WEB_DIR
from .working_copy import WorkingCopy


def create_app(data_path: str | Path) -> FastAPI:
    """Build the app. Raises DataError if a data file can't be read."""
    app = FastAPI(title="Mifflin Ops")
    app.state.wc = WorkingCopy(data_path)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/")
    def home():
        return RedirectResponse("/waybills", status_code=303)

    # Order matters: the nested industry paths must be registered before the catch-all
    # /{kind}/... routes.
    app.include_router(routes_industries.router)
    app.include_router(routes_records.router)
    return app
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest -q`

Expected: everything passes (5 new tests).

- [ ] **Step 6: Lint**

Run: `uv run ruff check waybill_generator/web tests/web`

Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add waybill_generator/web \
  tests/web
git commit -m "$(cat <<'EOF'
feat: add industries editor under each location

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Review & Save, Discard, Reload

**Files:**
- Create: `waybill_generator/web/routes_review.py`, `waybill_generator/web/templates/review.html`
- Replace: `waybill_generator/web/app.py`
- Test: `tests/web/test_app_review.py`

**Interfaces:**
- Consumes: `WorkingCopy.validate / diffs / conflicts / save / discard / reload_file` (Task 3).
- Produces routes: `GET /review`; `POST /save` (form field `overwrite` present ⇒ overwrite a changed-on-disk file; redirects to `/review` with a flash); `POST /discard` (re-read everything; redirect to `/waybills`); `POST /reload/{kind}` (re-read one file, dropping its staged edits). `create_app` includes `routes_review.router` **first** so these fixed paths win over `/{kind}/…`.
- The header's **Review & Save** link and **Discard** button (already in `base.html`) start working.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_app_review.py`:

```python
import yaml
from fastapi.testclient import TestClient

from tests.web.conftest import CAR_FORM, follow
from waybill_generator.web.app import create_app


def stage_a_car_edit(client, notes="mine"):
    client.post("/cars/PRR-12345", data={"road": "PRR", "car_number": "12345", "aar_code": "XM",
                                          "capacity_tons": "50", "notes": notes})


def test_review_with_nothing_staged(client):
    assert "No unsaved changes." in client.get("/review").text


def test_review_shows_diff_validation_and_existing_warnings(client):
    stage_a_car_edit(client)
    page = client.get("/review").text
    assert "data/cars.yaml" in page and "+  notes: mine" in page
    assert "No new broken references" in page and "Save 1 file to YAML" in page
    assert "pre-existing broken reference" in page and "PHL" in page          # fixture deadhead-1


def test_new_broken_reference_blocks_saving(client):
    follow(client, client.post("/waybills/new", data={
        "waybill_type": "HOLD", "id": "hold-9", "originating_railroad_id": "PRR",
        "industry_id": "NOPE-IND", "waiting_for": "x"}))
    page = client.get("/review").text
    assert "Can't save" in page and "NOPE-IND" in page and "disabled" in page
    assert "Not saved" in follow(client, client.post("/save", data={})).text


def test_save_writes_and_clears_the_unsaved_banner(client, data_dir):
    stage_a_car_edit(client)
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={})).text
    assert "notes: mine" in (data_dir / "cars.yaml").read_text()
    assert "unsaved" not in client.get("/cars").text
    assert "Nothing to save" in follow(client, client.post("/save", data={})).text


def test_disk_conflict_offers_reload_or_overwrite(client, data_dir):
    stage_a_car_edit(client)
    (data_dir / "cars.yaml").write_text((data_dir / "cars.yaml").read_text() + "\n# edited elsewhere\n")
    page = client.get("/review").text
    assert "Changed on disk" in page and "Reload cars.yaml from disk" in page and "Overwrite" in page
    assert "Not saved" in follow(client, client.post("/save", data={})).text
    assert "edited elsewhere" in (data_dir / "cars.yaml").read_text()
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={"overwrite": "on"})).text
    assert "edited elsewhere" not in (data_dir / "cars.yaml").read_text()


def test_reload_drops_that_files_staged_edits(client):
    stage_a_car_edit(client)
    assert "Reloaded cars.yaml" in follow(client, client.post("/reload/cars")).text
    assert "unsaved" not in client.get("/cars").text
    assert client.post("/reload/nope").status_code == 404


def test_discard_drops_everything_staged(client):
    stage_a_car_edit(client)
    client.post("/cars/PRR-67890/delete")
    assert "Discarded all unsaved changes" in follow(client, client.post("/discard")).text
    assert "unsaved" not in client.get("/cars").text and "PRR-67890" in client.get("/cars").text


def test_unreadable_file_on_disk_is_reported_on_reload(client, data_dir):
    (data_dir / "cars.yaml").write_text("- id: a\n  x: [unclosed\n")
    assert "Reload failed" in follow(client, client.post("/reload/cars")).text
    assert "Reload failed" in follow(client, client.post("/discard")).text


def test_edit_car_is_visible_in_review_and_saves_to_yaml(client, data_dir):
    follow(client, client.post("/cars/PRR-12345", data={**CAR_FORM, "notes": "repainted"}))
    assert "+  notes: repainted" in client.get("/review").text
    assert "Saved cars.yaml" in follow(client, client.post("/save", data={})).text
    assert yaml.safe_load((data_dir / "cars.yaml").read_text())[0]["notes"] == "repainted"
    assert "unsaved" not in client.get("/cars").text




def test_a_value_missing_from_the_data_survives_an_edit(data_dir):
    (data_dir / "waybills.yaml").write_text((data_dir / "waybills.yaml").read_text() + """
- id: perishable-1
  waybill_type: PERISHABLE
  originating_railroad_id: PRR
  commodity_id: produce
  shipper_name: Growers Assoc.
  consignee_name: Fresh Foods
  to_city: New York
  to_state: NY
  from_city: Lewistown
  from_state: PA
  routing: [PRR, NYC, NH]
""")
    client = TestClient(create_app(data_dir), follow_redirects=False)
    page = client.get("/waybills/perishable-1").text
    assert 'value="produce"' in page and "not in data" in page
    form = {"originating_railroad_id": "PRR", "commodity_id": "produce", "shipper_name": "Growers Assoc.",
            "consignee_name": "Fresh Foods", "to_city": "New York", "to_state": "NY", "from_city": "Lewistown",
            "from_state": "PA", "routing": ["PRR", "NYC", "NH"], "notes": "checked"}
    follow(client, client.post("/waybills/perishable-1", data=form))
    assert "Saved waybills.yaml" in follow(client, client.post("/save", data={})).text
    text = (data_dir / "waybills.yaml").read_text()
    assert "commodity_id: produce" in text and "routing: [PRR, NYC, NH]" in text   # untouched keys keep their form
    assert text.rstrip().endswith("notes: checked")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/web/test_app_review.py -q`

Expected: failures — `/review`, `/save`, `/discard`, `/reload/...` return 404 / 405.

- [ ] **Step 3: Implement the router**

```python
"""Review staged changes, save them to YAML, or throw them away."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .context import redirect, render, wc_of
from .entities import get_entity
from .working_copy import DataError, DiskConflict, ValidationBlocked

router = APIRouter()


@router.get("/review")
def review(request: Request):
    wc = wc_of(request)
    return render(request, "review.html", validation=wc.validate(), diffs=wc.diffs(),
                  conflicts=wc.conflicts())


@router.post("/save")
async def save(request: Request):
    form = await request.form()
    try:
        written = wc_of(request).save(overwrite=form.get("overwrite") is not None)
    except (ValidationBlocked, DiskConflict):
        return redirect("/review", "Not saved — see below")
    return redirect("/review", f"Saved {', '.join(written)}" if written else "Nothing to save")


@router.post("/discard")
def discard(request: Request):
    try:
        wc_of(request).discard()
    except DataError as exc:
        return redirect("/waybills", f"Reload failed: {exc}")
    return redirect("/waybills", "Discarded all unsaved changes")


@router.post("/reload/{kind}")
def reload_file(request: Request, kind: str):
    get_entity(kind)
    try:
        wc_of(request).reload_file(kind)
    except DataError as exc:
        return redirect("/review", f"Reload failed: {exc}")
    return redirect("/review", f"Reloaded {kind}.yaml from disk")
```

- [ ] **Step 4: Add the review template**

`waybill_generator/web/templates/review.html`:

```html
{% extends "base.html" %}
{% block title %}Review &amp; Save · Mifflin Ops{% endblock %}
{% block content %}
<h1>Review &amp; Save</h1>
{% if not diffs %}
  <p class="muted">No unsaved changes.</p>
{% else %}
  {% if validation.blocking %}
    <div class="banner err"><b>Can't save — these broken references are new:</b>
      <ul>{% for r in validation.blocking %}<li>{{ r.describe() }} → no such {{ r.target | replace('_', ' ') | replace('ies', 'y') | replace('ses', 's') }} “{{ r.value }}”</li>{% endfor %}</ul>
    </div>
  {% else %}
    <div class="banner ok">✓ No new broken references.</div>
  {% endif %}
  {% if conflicts %}
    <div class="banner warn">⚠ Changed on disk since it was loaded: <b>{{ conflicts | join(', ') }}</b>
      {% for d in diffs if d.filename in conflicts %}
        <form method="post" action="/reload/{{ d.kind }}" class="inline"><button class="btn">Reload {{ d.filename }} from disk</button></form>
      {% endfor %}
    </div>
  {% endif %}
  {% for d in diffs %}
    <div class="diff">
      <div class="h">data/{{ d.filename }}</div>
      {% for line in d.diff.splitlines() %}
        {% if line.startswith('+++') or line.startswith('---') %}{% else %}
        <div class="l {{ 'a' if line.startswith('+') else 'd' if line.startswith('-') else 'c' }}">{{ line }}</div>
        {% endif %}
      {% endfor %}
    </div>
  {% endfor %}
  <form method="post" action="/save" class="row">
    <button class="btn pri" {{ 'disabled' if validation.blocking else '' }}>Save {{ diffs | length }} file{{ '' if diffs | length == 1 else 's' }} to YAML</button>
    {% if conflicts %}<label><input type="checkbox" name="overwrite"> Overwrite the changed-on-disk file(s) anyway</label>{% endif %}
    <a class="btn" href="/">Back</a>
  </form>
{% endif %}
{% if validation.existing %}
  <details>
    <summary>{{ validation.existing | length }} pre-existing broken reference{{ '' if validation.existing | length == 1 else 's' }} (already in your files; not blocking)</summary>
    <ul>{% for r in validation.existing %}<li>{{ r.describe() }} → “{{ r.value }}” not found in {{ r.target }}</li>{% endfor %}</ul>
  </details>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Register the router (final `app.py`)**

Replace `waybill_generator/web/app.py`:

```python
"""FastAPI app: server-rendered pages over a WorkingCopy of the data files."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import routes_industries, routes_records, routes_review
from .context import WEB_DIR
from .working_copy import WorkingCopy


def create_app(data_path: str | Path) -> FastAPI:
    """Build the app. Raises DataError if a data file can't be read."""
    app = FastAPI(title="Mifflin Ops")
    app.state.wc = WorkingCopy(data_path)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/")
    def home():
        return RedirectResponse("/waybills", status_code=303)

    # Order matters: fixed paths (/review, /save, ...) and the nested industry paths
    # must be registered before the catch-all /{kind}/... routes.
    app.include_router(routes_review.router)
    app.include_router(routes_industries.router)
    app.include_router(routes_records.router)
    return app
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest -q`

Expected: everything passes (275 tests in total at the time of writing).

- [ ] **Step 7: Lint**

Run: `uv run ruff check waybill_generator/web tests/web`

Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add waybill_generator/web \
  tests/web
git commit -m "$(cat <<'EOF'
feat: add Review & Save with diffs, conflict handling, and discard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Documentation, browser smoke test, and squash

**Files:**
- Modify: `CLAUDE.md`, `README.md`
- Scratch only (outside the repo): a Playwright harness and `ui-smoke.js`

- [ ] **Step 1: Document the command in `CLAUDE.md`**

In the **Key Commands** block, after the `waybill list waybills` line, add:

```bash
uv run waybill serve [--port 8000] [--open]   # local web UI: edit data, review diff, save to YAML
```

After the **Industry Database Browser** section, add a new section:

```markdown
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
```

- [ ] **Step 2: Document it in `README.md`**

After the **Data Files** section (before **Printing Cards**), add:

````markdown
## Web UI (editing data)

Prefer forms to hand-editing YAML? Start the local UI:

```bash
uv run waybill serve            # http://127.0.0.1:8000  (add --open to launch a browser)
```

Every reference field (commodity, shipper, consignee, locations, …) is a type-to-search dropdown,
and industries that ship or receive the chosen commodity are listed first. Edits are staged in
memory — the header shows how many are unsaved. **Review & Save** shows a diff of exactly what will
change in each YAML file (nothing else is touched, including your comments) and writes it when you
say so; **Discard** throws staged edits away. If a file changed on disk while you were editing, you
are asked whether to reload it or overwrite it.
````

- [ ] **Step 3: Run the manual browser smoke test**

The JS (pickers, htmx type swap, ranking) is not covered by pytest. Verify it in a real headless Chromium, using a scratch harness **outside the repo** (`$SCRATCH` = any temp directory, e.g. the session scratchpad):

```bash
export SCRATCH=<scratch dir>
mkdir -p $SCRATCH/pw $SCRATCH/shots && cd $SCRATCH/pw
npm init -y >/dev/null && npm install playwright-core
# A Chromium build is usually already cached; otherwise: npx playwright-core install chromium
CHROME="$(find ~/Library/Caches/ms-playwright ~/.cache/ms-playwright -type f -name chrome-headless-shell 2>/dev/null | head -1)"
echo "$CHROME"
```

Create `$SCRATCH/pw/ui-smoke.js`:

```javascript
// Manual browser smoke test for the web UI (kept OUT of the repo; run against a scratch copy of data/).
// usage: node ui-smoke.js <chromium-executable> <base-url> <screenshot-dir>
const { chromium } = require('playwright-core');
const [EXE, BASE, OUT] = process.argv.slice(2);
const results = [];
const check = (name, ok, detail = '') => { results.push(ok); console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? '  ' + detail : '')); };

(async () => {
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  const pickers = (scope) => page.evaluate((s) => ({
    selects: document.querySelectorAll(`${s} select[data-picker]`).length,
    wrappers: document.querySelectorAll(`${s} .ts-wrapper`).length,
    visibleNative: [...document.querySelectorAll(`${s} select[data-picker]`)].filter((e) => !e.classList.contains('ts-hidden-accessible')).length,
  }), scope);

  // 1. list page
  await page.goto(BASE + '/waybills');
  check('waybill list renders rows', (await page.locator('tbody tr').count()) > 5);

  // 2. pickers initialise, and survive an htmx type swap (no duplicate native <select>)
  await page.goto(BASE + '/waybills/new');
  await page.waitForSelector('.ts-wrapper');
  let p = await pickers('#fields');
  check('LOADED form: every select is a picker', p.selects > 0 && p.selects === p.wrappers && p.visibleNative === 0, JSON.stringify(p));
  await page.selectOption('#f-waybill_type', 'EMPTY');
  await page.waitForSelector('#f-from_location_id');
  await page.waitForFunction(() => document.querySelectorAll('#fields .ts-wrapper').length === document.querySelectorAll('#fields select[data-picker]').length);
  p = await pickers('#fields');
  check('after swap to EMPTY: commodity field gone', (await page.locator('#f-commodity_id').count()) === 0);
  check('after swap: pickers re-initialised, no visible native select', p.selects === p.wrappers && p.visibleNative === 0, JSON.stringify(p));
  await page.selectOption('#f-waybill_type', 'LOADED');
  await page.waitForSelector('#f-commodity_id');
  await page.waitForFunction(() => document.querySelectorAll('#fields .ts-wrapper').length === document.querySelectorAll('#fields select[data-picker]').length);
  p = await pickers('#fields');
  check('swap back to LOADED: still one control per field', p.selects === p.wrappers && p.visibleNative === 0, JSON.stringify(p));

  // 3. commodity-aware ranking + type-to-search on the consignee picker
  await page.evaluate(() => document.getElementById('f-commodity_id').tomselect.setValue('limestone'));
  await page.evaluate(() => document.getElementById('f-consignee_id').tomselect.open());
  const DD = '#f-consignee_id + .ts-wrapper .ts-dropdown';
  await page.waitForSelector(DD + ' .option', { state: 'visible' });
  const groups = await page.evaluate((dd) => [...document.querySelectorAll(dd + ' .optgroup')].map((g) => ({
    header: g.querySelector('.optgroup-header').textContent, options: [...g.querySelectorAll('.option .n')].map((n) => n.textContent) })), DD);
  check('ranked group comes first and is labelled', groups.length === 2 && /^Receives Limestone/.test(groups[0].header) && groups[0].options.length > 0, JSON.stringify(groups[0]));
  check('other industries are listed, not hidden', groups[1].options.length > 5 && !groups[1].options.includes(''));
  await page.screenshot({ path: OUT + '/ranked-dropdown.png' });
  await page.keyboard.type('lew');
  await page.waitForTimeout(400);
  const hits = await page.evaluate((dd) => [...document.querySelectorAll(dd + ' .option .n')].map((n) => n.textContent), DD);
  check('typing "lew" narrows to Lewistown industries', hits.length > 0 && hits.every((h) => /lewistown/i.test(h)), JSON.stringify(hits));
  await page.keyboard.press('Enter');
  check('Enter picks the top match', (await page.evaluate(() => document.getElementById('f-consignee_id').value)) !== '');

  // 4. apply stages the record; the header counts it
  await page.evaluate(() => {
    document.getElementById('f-originating_railroad_id').tomselect.setValue('PRR');
    document.getElementById('f-shipper_id').tomselect.setValue(document.getElementById('f-shipper_id').options[1].value);
  });
  await page.click('form.card button.pri');
  await page.waitForURL(/flash=/);
  check('apply redirects to the list with a NEW row', (await page.locator('tr.new').count()) === 1);
  check('header shows the unsaved-changes counter', /unsaved change/.test(await page.locator('.dirty').textContent()));

  // 5. review page shows a diff and saving clears the counter
  await page.goto(BASE + '/review');
  check('review shows an added-line diff', (await page.locator('.diff .l.a').count()) > 0);
  await page.click('button:has-text("to YAML")');
  await page.waitForURL(/flash=Saved/);
  check('save clears the unsaved counter', (await page.locator('.dirty').count()) === 0);

  // 6. multi-select chips render for an industry's ships
  await page.goto(BASE + '/locations/LEW/industries/LEW-GRAIN');
  await page.waitForSelector('#f-ships + .ts-wrapper');
  check('multi-select shows chips', (await page.locator('#f-ships + .ts-wrapper .item').count()) > 0);

  check('no JavaScript errors', errors.length === 0, JSON.stringify(errors));
  await browser.close();
  if (results.includes(false)) process.exit(1);
})().catch((e) => { console.error('SMOKE ERROR:', e.message); process.exit(1); });
```

Run it against a **scratch copy** of your data (it saves a waybill, so never point it at `data/`):

```bash
cd <repo root>
cp -R data $SCRATCH/smoke-data
uv run waybill --data-path $SCRATCH/smoke-data serve --port 8766 &
sleep 4
node $SCRATCH/pw/ui-smoke.js "$CHROME" http://127.0.0.1:8766 $SCRATCH/shots
kill %1
git status --short          # data/ must be untouched
```

Expected: 15 lines starting `PASS`, none `FAIL`, exit code 0. If a check fails, fix the app (not the check). Failures worth knowing about: a native `<select>` visible next to its picker (pickers initialised on `afterSwap` instead of `afterSettle`), or a stray input style leaking into Tom Select's internal search box (form-control CSS must target `.field > input`, not bare `input`). Open `$SCRATCH/shots/ranked-dropdown.png`: expect a "Receives Limestone" group (Standard Steel Works, Lewistown Cement Co.) above "Other industries".

- [ ] **Step 4: Full verification**

Run: `uv run pytest -q && uv run ruff check waybill_generator/web tests/web`

Expected: all tests pass; `All checks passed!`. Also confirm `cli.py` gained no new ruff findings: `uv run ruff check waybill_generator/cli.py --output-format concise | tail -1` reports the same count as at the base commit.

- [ ] **Step 5: Commit the docs**

```bash
git add CLAUDE.md \
  README.md
git commit -m "$(cat <<'EOF'
docs: document the waybill serve web UI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: Squash the phase into one commit (project workflow)**

The project convention is one commit per feature phase on `main`. Only if the commits are **unpushed** (`git status -sb` shows no upstream or "ahead"), squash everything since the base hash recorded in Task 1 Step 1 (the commit *after* the docs commit):

```bash
git log --oneline <BASE>..HEAD        # expect the 9 task commits, nothing else
git reset --soft <BASE>
git commit -m "$(cat <<'EOF'
feat: add local web UI for editing waybill data (phase 1)

`waybill serve` runs a FastAPI/htmx UI over a staged in-memory copy of data/*.yaml:
searchable pickers, generated forms for all waybill types, a nested industries editor,
and Review & Save that splices only changed records back into the YAML files
(comments and untouched records stay byte-identical).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
git log --oneline -3 && uv run pytest -q
```

Expected: one new commit on top of `<BASE>`; the suite still passes. If you are not sure the commits are unpushed, skip this step and ask.

---

## Self-review against the spec

| Spec requirement | Task |
|---|---|
| Staged working copy; Apply vs Save to YAML; Discard | 3, 5, 6, 8 |
| `YamlFile`: minimal diffs, comments/sections/untouched records byte-identical, temp-file-then-rename, unsupported layouts rejected | 2 |
| `WorkingCopy` implements `BaseRepository`; dirty tracking; new/modified/deleted; reference-blocked deletes | 3 |
| Baseline-relative `validate()`; new broken references block Save; existing ones warn | 3, 8 |
| Disk-conflict check with Reload / Overwrite | 3, 8 |
| Startup refuses unreadable data with file + message | 3, 5 |
| Generic model-driven forms; all 10 waybill types; picker-mapping completeness test | 3, 4 |
| Searchable pickers (name/id/city/track/AAR), rich rows, chips, keyboard nav, vendored offline | 1, 6 |
| Commodity-aware ranking (ranked, never filtered) | 6 (verified in 9) |
| Values missing from the data stay selectable ("not in data") | 4, 6, 8 |
| List pages: search, waybill type filter, new/modified/deleted marks | 5 |
| Waybill type swap via htmx | 6 |
| Suggested ids (waybill-N, `{road}-{number}`, location/industry helpers) | 5, 6, 7 |
| Locations with nested industries editor | 6, 7 |
| Review & Save page: diff per file, validation, conflict banner | 8 |
| `waybill serve` on 127.0.0.1 only; docs in CLAUDE.md / README | 5, 9 |
| Browser smoke test outside the suite | 9 |
| Deferred to Phase 2 (own plan): `resolve_card`, card preview, session builder, Generate | - |
