from fastapi import APIRouter
from app.api.v1.endpoints import auth, role, permission, spatial, user, activity_log, menu, sawit, slope, landuse, jalan, jembatan, akses_data, database_tables, geo_dinamic

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
api_router.include_router(database_tables.router, prefix="/database", tags=["Database Metadata"])

api_router.include_router(akses_data.router, prefix="/akses-data", tags=["Akses Data GIS"])

# # Router Permission Management (Baru)
# api_router.include_router(permission.router, prefix="/permissions", tags=["Permission Management"])

api_router.include_router(geo_dinamic.router, prefix="/spatial", tags=["Upload Dinamis"])

# Router Blok Spasial
# api_router.include_router(blok.router, prefix="/blocks", tags=["Blocks & Filters"])
api_router.include_router(spatial.router, prefix="/spatial", tags=["Spatial Data & Maps"])

# Router Sawit
api_router.include_router(sawit.router, prefix="/spatial/sawit", tags=["Spatial Sawit"])

# slope
api_router.include_router(slope.router, prefix="/spatial/slope", tags=["Spatial Slope"])

# landuse
api_router.include_router(landuse.router, prefix="/spatial/landuse", tags=["Spatial Landuse"])

# jalan
api_router.include_router(jalan.router, prefix="/spatial/jalan", tags=["Spatial Jalan"])

# jembatan
api_router.include_router(jembatan.router, prefix="/spatial/jembatan", tags=["Spatial Jembatan"])