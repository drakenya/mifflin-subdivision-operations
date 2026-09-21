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


class SaveIncomplete(Exception):
    """A rename failed partway through saving several files."""

    def __init__(self, written: list[str], failed: str, unwritten: list[str]):
        super().__init__(
            f"saved {', '.join(written) or 'nothing'}; failed on {failed}; "
            f"not saved: {', '.join(unwritten) or 'none'}"
        )
        self.written = written
        self.failed = failed
        self.unwritten = unwritten


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
        try:
            rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            return [(r["code"], r.get("name", "")) for r in rows]
        except (yaml.YAMLError, KeyError, TypeError, AttributeError) as exc:
            raise DataError(f"aar_codes.yaml: {type(exc).__name__}: {exc}") from exc

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
        old = self._files[kind]
        try:
            fresh = YamlFile(old.path, group_key=old.group_key)   # raises before anything changes
        except (yaml.YAMLError, UnsupportedLayout) as exc:
            raise DataError(f"{kind}.yaml: {exc}") from exc
        self._files[kind] = fresh
        try:
            self._load_kind(kind)      # builds all models before assigning any state
        except DataError:
            self._files[kind] = old    # keep the old file state (and its digest) on failure
            raise

    def reload_file(self, kind: str) -> None:
        """Re-read one file from disk, dropping its staged edits."""
        aar_codes = self._load_aar_codes()   # aar_codes.yaml is hand-edited; a bad read raises first
        self._reread(kind)
        self.aar_codes = aar_codes
        self._refresh_baseline()

    def discard(self) -> None:
        aar_codes = self._load_aar_codes()
        for kind in KINDS:
            self._reread(kind)
        self.aar_codes = aar_codes
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
                desired = self._desired_raw(kind)
                text = file.render(desired)
                parsed = yaml.safe_load(text) or []
                if (len(parsed) != len(desired)
                        or {r["id"]: r for r in parsed} != {d["id"]: d for d in desired}):
                    raise DataError(f"{file.path.name}: refusing to write; "
                                    "the rendered text does not match the intended records")
                staged.append((kind, file.stage(text)))
        except Exception:
            for _, tmp in staged:
                tmp.unlink(missing_ok=True)
            raise
        written: list[str] = []
        for index, (kind, tmp) in enumerate(staged):
            try:
                self._files[kind].commit(tmp)
            except OSError as exc:
                remaining = staged[index + 1:]
                for _, leftover in [(kind, tmp), *remaining]:
                    leftover.unlink(missing_ok=True)
                self._refresh_baseline()
                raise SaveIncomplete(
                    written,
                    self._files[kind].path.name,
                    [self._files[k].path.name for k, _ in remaining],
                ) from exc
            self._load_kind(kind)
            written.append(self._files[kind].path.name)
        self._refresh_baseline()
        return written
