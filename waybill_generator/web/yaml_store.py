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
    parsed = yaml.safe_load(text)
    if parsed is None:
        parsed = []
    if not isinstance(parsed, list):
        raise UnsupportedLayout("expected a top-level list of mappings that each have an id")
    if len(parsed) != len(starts) or not all(isinstance(r, dict) and "id" in r for r in parsed):
        raise UnsupportedLayout("expected a top-level list of mappings that each have an id")
    ids = [r["id"] for r in parsed]
    if len(set(ids)) != len(ids):
        raise UnsupportedLayout(f"duplicate id(s): {sorted({i for i in ids if ids.count(i) > 1}, key=str)}")
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
        self.text = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        self.digest = _digest(self.text)
        self._header, self._segments = _split(self.text)

    def records(self) -> list[dict]:
        return [copy.deepcopy(s.raw) for s in self._segments]

    def changed_on_disk(self) -> bool:
        current = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
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
        tmp.write_text(new_text, encoding="utf-8")
        return tmp

    def commit(self, tmp: Path) -> None:
        os.replace(tmp, self.path)
        self.reload()
