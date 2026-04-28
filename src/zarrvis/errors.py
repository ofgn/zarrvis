from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ZarrVisError(Exception):
    code: str = "Error"
    http_status: int = 500

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.hint:
            payload["hint"] = self.hint
        return {"error": payload}


class NotFound(ZarrVisError):
    code = "NotFound"
    http_status = 404


class Forbidden(ZarrVisError):
    code = "Forbidden"
    http_status = 403


class Unsupported(ZarrVisError):
    code = "Unsupported"
    http_status = 415


class OutOfRange(ZarrVisError):
    code = "OutOfRange"
    http_status = 400


class BadRequest(ZarrVisError):
    code = "BadRequest"
    http_status = 400


class RemoteTimeout(ZarrVisError):
    code = "RemoteTimeout"
    http_status = 504


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ZarrVisError)
    async def _handle_zarrvis_error(_: Request, exc: ZarrVisError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_payload())

    @app.exception_handler(FileNotFoundError)
    async def _handle_fnf(_: Request, exc: FileNotFoundError) -> JSONResponse:
        err = NotFound(str(exc) or "file not found")
        return JSONResponse(status_code=err.http_status, content=err.to_payload())

    @app.exception_handler(PermissionError)
    async def _handle_perm(_: Request, exc: PermissionError) -> JSONResponse:
        err = Forbidden(str(exc) or "permission denied")
        return JSONResponse(status_code=err.http_status, content=err.to_payload())
