"""Basemap Foto Udara: proxy WMS ke GeoServer (remote+token atau SERVER_LOCAL)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from app.api import deps
from app.services import foto_udara_service as fu

router = APIRouter()


@router.get(
    "/foto-udara/status",
    summary="Status basemap Foto Udara (konfigurasi, mode lokal/remote, layer, cakupan)",
)
async def foto_udara_status(current_user=Depends(deps.get_current_user_released)):
    return await fu.status()


@router.get(
    "/foto-udara/wms",
    summary="Ubin WMS GetMap Foto Udara lewat backend",
    description="Parameter WMS GetMap biasa (bbox, width, height, srs/crs, format, layers, version). "
                "SERVER_LOCAL=false: token digilink ditambahkan backend. SERVER_LOCAL=true: IP_LOCAL_FOTO_UDARA tanpa token. "
                "Gambar di-cache di Redis. Gagal: JSON {reason, message} dengan HTTP 404/400/424.",
)
async def foto_udara_wms(request: Request, current_user=Depends(deps.get_current_user_released)):
    try:
        body, ctype, hit = await fu.get_tile(dict(request.query_params))
    except fu.FotoUdaraError as exc:
        return JSONResponse({"reason": exc.reason, "message": exc.message}, status_code=exc.status)
    return Response(body, media_type=ctype, headers={
        "Cache-Control": "private, max-age=86400",
        "X-Foto-Udara-Cache": "HIT" if hit else "MISS",
    })
