from __future__ import annotations

import logging
from importlib.resources import as_file, files
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from zarrvis import __version__
from zarrvis.api import build_api_router
from zarrvis.errors import register_exception_handlers
from zarrvis.security import HostHeaderMiddleware, TokenMiddleware

logger = logging.getLogger(__name__)


def _static_dir() -> Path:
    resource = files("zarrvis") / "static"
    with as_file(resource) as path:
        return Path(path)


def create_app(
    *,
    root: Path,
    token: str,
    initial_path: str | None = None,
    allow_remote: bool = False,
) -> FastAPI:
    app = FastAPI(
        title="zarrvis",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.root = root.resolve()
    app.state.token = token
    app.state.initial_path = initial_path
    app.state.allow_remote = allow_remote

    app.add_middleware(TokenMiddleware, token=token)
    app.add_middleware(HostHeaderMiddleware)

    register_exception_handlers(app)

    app.include_router(build_api_router(), prefix="/api")

    static_dir = _static_dir()
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/", include_in_schema=False)
        async def _index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app
