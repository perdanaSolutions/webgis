from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.core.config import settings
from app.core.database import engine
from app.core.map_cache import MapRedisCacheMiddleware
from app.core.middleware import DropEmptyQueryParamsMiddleware
from app.core.redis_client import shutdown as close_redis
from app.core.redis_client import startup as open_redis
from app.core.client_ip import ClientIpMiddleware
from app.db.ensure_activity_ip import ensure_activity_ip_required
from app.api.v1.api import api_router
from fastapi.exceptions import HTTPException as FastAPIHTTPException


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_activity_ip_required(engine)
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
app.add_middleware(MapRedisCacheMiddleware)
# Di luar cache: cache menyimpan JSON mentah, kompresi diterapkan juga pada respons HIT.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(DropEmptyQueryParamsMiddleware)
app.add_middleware(ClientIpMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGIN_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Welcome to GIS Plantation API"}