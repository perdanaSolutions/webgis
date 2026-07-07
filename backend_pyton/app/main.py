from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from fastapi.exceptions import HTTPException as FastAPIHTTPException

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to GIS Plantation API"}