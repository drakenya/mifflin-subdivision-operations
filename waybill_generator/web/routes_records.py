"""List, create, edit, and delete records of any collection."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .context import blocked_message, form_page, redirect, render, wc_of
from .entities import cell, get_entity, id_error, suggest_id
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


@router.get("/{kind}/suggest-id")
def suggest_id_route(request: Request, kind: str):
    """The id the form would generate from the fields typed so far (JSON, for the locked id field)."""
    get_entity(kind)
    return {"id": suggest_id(wc_of(request), kind, dict(request.query_params))}


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
    id_mode = "manual" if request.query_params.get("id_manual") == "1" else "locked"
    return render(request, "_fields.html", fields=fields, id_mode=id_mode, id_suggest_url=f"/{kind}/suggest-id")


def _record_page(request: Request, kind: str, rid: str, model_cls, values: dict, errors: dict,
                 id_manual: bool = False):
    entity = get_entity(kind)
    wc = wc_of(request)
    is_new = rid == "new"
    extra: dict = {"record_id": rid, "id_mode": ("manual" if id_manual else "locked") if is_new else "fixed",
                   "id_suggest_url": f"/{kind}/suggest-id" if is_new else None}
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
    elif is_new and values.get("id") and (message := id_error(str(values["id"]))):
        errors["id"] = message
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
        return _record_page(request, kind, rid, model_cls, values, errors, id_manual=form.get("id_manual") == "1")
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
