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
