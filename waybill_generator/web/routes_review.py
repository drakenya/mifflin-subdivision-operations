"""Review staged changes, save them to YAML, or throw them away."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .context import redirect, render, wc_of
from .entities import get_entity
from .working_copy import DataError, DiskConflict, SaveIncomplete, ValidationBlocked

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
    except SaveIncomplete as exc:
        return redirect("/review", f"Save incomplete — {exc}")
    except (DataError, OSError) as exc:
        return redirect("/review", f"Not saved — {exc}")
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
