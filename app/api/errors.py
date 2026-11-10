import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.usage import QuotaExceeded

logger = logging.getLogger(__name__)

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "internal_error",
}


def _code(status_code: int) -> str:
    return STATUS_CODES.get(status_code, "error")


async def http_exception_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", _code(exc.status_code)))
        message = str(detail.get("message", detail.get("detail", "")))
        details: Any = detail.get("details")
    else:
        code = _code(exc.status_code)
        message = str(detail)
        details = None
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": message, "details": details},
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "loc": list(error.get("loc", [])),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "La solicitud no es válida",
            "details": details,
        },
    )


async def quota_exception_handler(
    _request: Request, exc: QuotaExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": str(exc),
            "details": {
                "used": exc.used,
                "limit": exc.limit,
                "required": exc.required,
            },
        },
    )


async def unhandled_exception_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Error no controlado", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "Error interno del servidor",
            "details": None,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(  # type: ignore[arg-type]
        StarletteHTTPException, http_exception_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(  # type: ignore[arg-type]
        RequestValidationError, validation_exception_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(  # type: ignore[arg-type]
        QuotaExceeded, quota_exception_handler  # type: ignore[arg-type]
    )
    app.add_exception_handler(Exception, unhandled_exception_handler)
