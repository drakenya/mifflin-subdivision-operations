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
