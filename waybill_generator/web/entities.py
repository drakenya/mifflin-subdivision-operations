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

# Ids become URL path segments (/cars/{id}); '&' is legal there and real road marks need it (B&O).
ID_PATTERN = re.compile(r"[A-Za-z0-9._&-]+")
RESERVED_IDS = {"new", "fields", "suggest-id"}


def clean_id(text: str) -> str:
    """`text` without any character ID_PATTERN would reject (so a generated id is always usable)."""
    return re.sub(r"[^A-Za-z0-9._&-]", "", text)


def id_error(record_id: str) -> str | None:
    """A message if `record_id` can't be used in a URL path (or collides with a reserved route)."""
    if record_id in RESERVED_IDS or not ID_PATTERN.fullmatch(record_id):
        return "Use only letters, digits, '.', '_', '&' and '-' (not 'new', 'fields' or 'suggest-id')"
    return None


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
    """A suggested, URL-safe id for a new record; empty when nothing sensible can be derived yet."""
    return clean_id(_suggested(wc, kind, values))


def _suggested(wc: WorkingCopy, kind: str, values: dict) -> str:
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
    if kind == "railroads":
        return "".join(word[0] for word in (values.get("name") or "").split()).upper()
    return ""
