from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from zarrvis.errors import Forbidden, NotFound

logger = logging.getLogger(__name__)

ALLOWED_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _is_remote(path: str) -> bool:
    return "://" in path


def resolve_local_path(raw: str, root: Path) -> Path:
    candidate = Path(raw).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise NotFound(f"cannot resolve path: {raw}") from exc
    root_resolved = root.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise Forbidden(
            "path escapes allowlist root",
            hint=f"paths must be under {root_resolved}",
        ) from exc
    if not resolved.exists():
        raise NotFound(f"path does not exist: {resolved}")
    return resolved


def validate_path(raw: str, *, root: Path, allow_remote: bool) -> str | Path:
    """Return either a resolved local Path or a validated remote URL string."""
    if _is_remote(raw):
        if not allow_remote:
            raise Forbidden(
                "remote paths are disabled",
                hint="start zarrvis with --allow-remote",
            )
        return raw
    return resolve_local_path(raw, root)


class HostHeaderMiddleware(BaseHTTPMiddleware):
    """Defend against DNS-rebinding by rejecting unknown Host headers."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        host_header = request.headers.get("host", "")
        hostname = host_header.split(":", 1)[0].strip("[]").lower()
        if hostname and hostname not in ALLOWED_HOSTNAMES:
            logger.warning("rejecting request with Host=%r", host_header)
            return JSONResponse(
                status_code=421,
                content={
                    "error": {
                        "code": "Forbidden",
                        "message": f"unexpected Host header: {host_header}",
                        "hint": "zarrvis only serves localhost/127.0.0.1",
                    }
                },
            )
        return await call_next(request)


class TokenMiddleware(BaseHTTPMiddleware):
    """Require a shared token on /api/* routes.

    The token is injected by the CLI and appears both in the URL opened in the
    browser (so the SPA can read it) and on every API call via the
    ``X-ZarrVis-Token`` header or the ``token`` query parameter.
    """

    def __init__(self, app: FastAPI, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        provided = request.headers.get("x-zarrvis-token") or request.query_params.get("token")
        if provided != self._token:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "Unauthorized",
                        "message": "missing or invalid session token",
                    }
                },
            )
        return await call_next(request)
