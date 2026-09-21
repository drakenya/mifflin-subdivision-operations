"""Add, edit, and remove the industries nested under a location."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from waybill_generator.cli import _generate_industry_id
from waybill_generator.models.location import Industry

from .context import blocked_message, form_page, redirect, wc_of
from .entities import clean_id, id_error
from .forms import build_model, initial_values, parse_form
from .working_copy import ReferenceBlocked

router = APIRouter()


def _require_industry(wc, loc_id: str, iid: str) -> None:
    """Raise 404 if location doesn't exist or industry doesn't belong to that location."""
    if not wc.has("locations", loc_id):
        raise HTTPException(404)
    if iid not in {i.id for i in wc.get_location(loc_id).industries}:
        raise HTTPException(404)


def _industry_page(request: Request, loc_id: str, iid: str, values: dict | None = None,
                   errors: dict | None = None, id_manual: bool = False):
    wc = wc_of(request)
    if not wc.has("locations", loc_id):
        raise HTTPException(404)
    is_new = iid == "new"
    if not is_new:
        _require_industry(wc, loc_id, iid)
    if values is None:
        values = initial_values(Industry) if is_new else wc.get_industry(iid).model_dump(mode="json")
    return form_page(
        request, kind="locations", heading=("New industry" if is_new else f"Industry {iid}"),
        model_cls=Industry, values=values, errors=errors or {}, editing=not is_new,
        action=f"/locations/{loc_id}/industries/{iid}", cancel_url=f"/locations/{loc_id}",
        delete_url=None if is_new else f"/locations/{loc_id}/industries/{iid}/delete",
        id_mode=("manual" if id_manual else "locked") if is_new else "fixed",
        id_suggest_url=f"/locations/{loc_id}/industries/suggest-id" if is_new else None,
    )


@router.get("/locations/{loc_id}/industries/suggest-id")
def industry_suggest_id(request: Request, loc_id: str, name: str = ""):
    """The id the form would generate from the name typed so far (JSON, for the locked id field)."""
    wc = wc_of(request)
    if not wc.has("locations", loc_id):
        raise HTTPException(404)
    generated = _generate_industry_id(loc_id, name.strip(), wc.industry_ids()) if name.strip() else ""
    return {"id": clean_id(generated)}


@router.get("/locations/{loc_id}/industries/{iid}")
def industry_form(request: Request, loc_id: str, iid: str):
    return _industry_page(request, loc_id, iid)


@router.post("/locations/{loc_id}/industries/{iid}")
async def industry_save(request: Request, loc_id: str, iid: str):
    wc = wc_of(request)
    if not wc.has("locations", loc_id):
        raise HTTPException(404)
    is_new = iid == "new"
    if not is_new:
        _require_industry(wc, loc_id, iid)
    form = await request.form()
    values, errors = parse_form(Industry, form)
    if is_new and "id" in errors and values.get("name"):
        values["id"] = clean_id(_generate_industry_id(loc_id, values["name"], wc.industry_ids()))
        errors.pop("id")
    if not is_new:
        values["id"] = iid
        errors.pop("id", None)
    elif values.get("id") in wc.industry_ids():
        errors["id"] = "Already exists"
    elif values.get("id") and (message := id_error(str(values["id"]))):
        errors["id"] = message
    values["location_id"] = loc_id
    model, more = build_model(Industry, values) if not errors else (None, {})
    errors.update(more)
    if errors:
        return _industry_page(request, loc_id, iid, values, errors, id_manual=form.get("id_manual") == "1")
    wc.apply_industry(loc_id, model)
    return redirect(f"/locations/{loc_id}", f"Applied industry {model.id}")


@router.post("/locations/{loc_id}/industries/{iid}/delete")
def industry_delete(request: Request, loc_id: str, iid: str):
    wc = wc_of(request)
    _require_industry(wc, loc_id, iid)
    try:
        wc.delete_industry(loc_id, iid)
    except ReferenceBlocked as exc:
        return redirect(f"/locations/{loc_id}/industries/{iid}", blocked_message(exc.refs))
    return redirect(f"/locations/{loc_id}", f"Removed industry {iid}")
