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
