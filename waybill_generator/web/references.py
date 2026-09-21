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
