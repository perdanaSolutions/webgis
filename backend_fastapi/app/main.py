from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.core.config import settings
from app.core.mtls import MtlsGuardMiddleware
from app.core.database import engine
from app.core.map_cache import MapRedisCacheMiddleware, set_store_versions_reader
from app.core.middleware import DropEmptyQueryParamsMiddleware
from app.core.redis_client import shutdown as close_redis
from app.core.redis_client import startup as open_redis
from app.core.client_ip import ClientIpMiddleware
from app.core.maintenance import MaintenanceMiddleware, get_status as get_maintenance_status
from app.db.ensure_activity_ip import ensure_activity_ip_required
from app.services.data_version import ensure_data_store_versions, read_store_versions
from app.api.v1.api import api_router
from fastapi.exceptions import HTTPException as FastAPIHTTPException
import logging

logger = logging.getLogger("app.errors")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_activity_ip_required(engine)
    ensure_data_store_versions(engine)
    set_store_versions_reader(read_store_versions)
    await open_redis()
    yield
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# =================================================================
# HANDLER KUSTOM UNTUK FORMAT ERROR VALIDATION (PYDANTIC)
# =================================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    custom_errors = []
    
    for error in exc.errors():
        # Mengambil nama field yang bermasalah. 
        # error['loc'] biasanya berbentuk tuple, misal ('body', 'username') atau ('query', 'page')
        field_name = error["loc"][-1] if error["loc"] else "unknown"
        
        custom_errors.append({
            "type": error.get("type"),
            "field": field_name,
            "msg": error.get("msg"),
            "input": error.get("input", None)
        })
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"errors": custom_errors} # <--- Format sesuai permintaanmu
    )

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    # Jika isi detail sudah berbentuk dictionary dan memiliki key "errors", langsung kembalikan rasponya
    if isinstance(exc.detail, dict) and "errors" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Jaga-jaga jika ada HTTPException standar string dari library lain, kita bungkus otomatis
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "errors": [
                {
                    "type": "server_error",
                    "field": "global",
                    "msg": str(exc.detail),
                    "input": None
                }
            ]
        }
    )

# =================================================================
# MIDDLEWARE & ROUTER
# =================================================================
# Paling dalam: query kosong sudah dibuang, header CORS masih ditambahkan di luar.
# =================================================================
# CATCH-ALL ERROR 500 (paling DALAM) agar respons error tetap lewat
# CORSMiddleware dan membawa header Access-Control-*. Tanpa ini Starlette
# menangani exception di ServerErrorMiddleware (paling luar) sehingga
# browser melihat 500 sebagai "CORS error".
# Middleware ASGI murni (bukan BaseHTTPMiddleware) agar streaming aman.
# =================================================================
class CatchAllErrorsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_wrapper(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal Server Error"},
            )
            await response(scope, receive, send)


# Ditambahkan PERTAMA = middleware paling dalam.
app.add_middleware(CatchAllErrorsMiddleware)
app.add_middleware(MapRedisCacheMiddleware)
# Di luar cache: cache menyimpan JSON mentah, kompresi diterapkan juga pada respons HIT.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(DropEmptyQueryParamsMiddleware)
app.add_middleware(ClientIpMiddleware)
# Mode maintenance (master.app_settings): di dalam CORS agar 503 tetap membawa header CORS.
app.add_middleware(MaintenanceMiddleware)
if settings.MTLS_ENFORCE:
    app.add_middleware(MtlsGuardMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGIN_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get(f"{settings.API_V1_STR}/system/maintenance", tags=["System"])
async def maintenance_status():
    """Publik, tanpa login. Dibaca dashboard untuk menampilkan halaman maintenance."""
    status = await get_maintenance_status()
    return {"maintenance": bool(status.get("maintenance")), "message": status.get("message") or ""}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Welcome to GIS Plantation API"}
