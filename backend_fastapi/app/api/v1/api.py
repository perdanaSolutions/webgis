from fastapi import APIRouter
from app.api.v1.endpoints import (
    access,
    activity_log,
    auth,
    database,
    geo_catalog,
    layers,
    menu,
    role,
    spatial,
    trx_imports,
    user,
)

api_router = APIRouter()

# Router Auth
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/users", tags=["User Management"])

# Kelompok Audit & Monitoring (Baru)
api_router.include_router(activity_log.router, prefix="/logs", tags=["Audit Logs"])

# Router Role Management
api_router.include_router(role.router, prefix="/roles", tags=["Role Management"])

api_router.include_router(menu.router, prefix="/menus", tags=["Menu Management"])

# Daftarkan endpoint tables di bawah prefix /database
api_router.include_router(database.router, prefix="/database", tags=["Database Metadata"])

api_router.include_router(access.router, prefix="/akses-data", tags=["Akses Data GIS"])

# # Router Permission Management (Baru)
# api_router.include_router(permission.router, prefix="/permissions", tags=["Permission Management"])

# Route literal (/area, /geojson, /blok/detail) didaftarkan sebelum /{kode}.
api_router.include_router(spatial.router, prefix="/spatial", tags=["Spatial Data & Maps"])
api_router.include_router(layers.router, prefix="/spatial")
api_router.include_router(geo_catalog.router, prefix="/spatial", tags=["Katalog & Layer Dinamis"])

api_router.include_router(trx_imports.areal_statement_router, prefix="/areal-statement", tags=["Areal Statement"])
api_router.include_router(trx_imports.production_router, prefix="/pokok-produksi", tags=["Pokok Produksi"])
api_router.include_router(trx_imports.rotation_router, prefix="/trx-rotasi-pusingan", tags=["trx-rotasi-pusingan"])

