"""Uniform error body: {"error": {"code", "message"}} (see UI/UX brief, API contracts)."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiException(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def _api(_: Request, exc: ApiException):
        return JSONResponse(status_code=exc.status,
                            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = f"{where}: {first.get('msg', 'invalid request')}" if where else "invalid request"
        return JSONResponse(status_code=422,
                            content={"error": {"code": "invalid_request", "message": msg}})
