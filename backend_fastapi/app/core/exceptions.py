"""
Format error seragam untuk seluruh API (dipertahankan dari backend lama agar FE tidak berubah):

    {"errors": [{"type": "...", "field": "...", "msg": "...", "input": ...}]}
"""
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def error_body(msg: str, type_: str = "server_error", field: str = "global", input_: Any = None) -> dict:
    return {"errors": [{"type": type_, "field": field, "msg": msg, "input": input_}]}


class AppError(HTTPException):
    """HTTPException dengan `type`/`field` eksplisit untuk format error standar."""

    def __init__(self, status_code: int, msg: str, type_: str = "bad_request", field: str = "global", input_: Any = None):
        super().__init__(status_code=status_code, detail=error_body(msg, type_, field, input_))


def not_found(msg: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, msg, type_="not_found")


def bad_request(msg: str, field: str = "global") -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, msg, type_="bad_request", field=field)


def conflict(msg: str, field: str = "global") -> AppError:
    return AppError(status.HTTP_409_CONFLICT, msg, type_="conflict", field=field)


def forbidden(msg: str) -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, msg, type_="forbidden")


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {
            "type": err.get("type"),
            "field": err["loc"][-1] if err.get("loc") else "unknown",
            "msg": err.get("msg"),
            "input": err.get("input"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"errors": errors}, custom_encoder={bytes: lambda b: None}),
    )


async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "errors" in exc.detail:
        content = exc.detail
    else:
        content = error_body(str(exc.detail), type_="http_error")
    return JSONResponse(status_code=exc.status_code, content=content, headers=getattr(exc, "headers", None))


async def _integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("IntegrityError pada %s: %s", request.url.path, exc.orig)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=error_body(f"Data bentrok dengan constraint database: {exc.orig}".strip(), type_="integrity_error"),
    )


async def _dbapi_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    logger.exception("Database error pada %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(f"Kesalahan database: {exc.orig}".strip(), type_="database_error"),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error pada %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("Terjadi kesalahan pada server.", type_="server_error"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(IntegrityError, _integrity_handler)
    app.add_exception_handler(DBAPIError, _dbapi_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
