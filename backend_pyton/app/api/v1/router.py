from fastapi import APIRouter

from app.api.v1.endpoints import (
    access,
    activity_logs,
    auth,
    database,
    geo_catalog,
    layers,
    menus,
    permissions,
    roles,
    spatial,
    trx_imports,
    users,
)

api_router = APIRouter()

# Auth & manajemen pengguna
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["User Management"])
api_router.include_router(roles.router, prefix="/roles", tags=["Role Management"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permission Management"])
api_router.include_router(menus.router, prefix="/menus", tags=["Menu Management"])
api_router.include_router(access.router, prefix="/akses-data", tags=["Akses Role"])
api_router.include_router(activity_logs.router, prefix="/logs", tags=["Audit Logs"])
api_router.include_router(database.router, prefix="/database", tags=["Database Metadata"])

# Spasial (urutan: route literal dulu, lalu layer & katalog)
api_router.include_router(spatial.router, prefix="/spatial", tags=["Spatial Data & Maps"])
api_router.include_router(layers.router, prefix="/spatial")
api_router.include_router(geo_catalog.router, prefix="/spatial", tags=["Katalog & Layer Dinamis"])

# Impor transaksi Excel
api_router.include_router(trx_imports.areal_statement_router, prefix="/areal-statement", tags=["Areal Statement"])
api_router.include_router(trx_imports.production_router, prefix="/pokok-produksi", tags=["Produksi TBS"])
api_router.include_router(trx_imports.rotation_router, prefix="/trx-rotasi-pusingan", tags=["Rotasi Pusingan"])
