from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints.blok import router as blok_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

# Setup CORS agar Frontend (React/Vue/Next.js) bisa manggil API ini tanpa terkena block
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Di produksi, ganti dengan domain frontend asli kamu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan router dengan prefix v1
app.include_router(blok_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Welcome to GIS Plantation API Engine"}