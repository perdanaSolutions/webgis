"""
Endpoint spasial untuk peta: hierarki, GeoJSON, detail blok, histori, dan upload batas blok.

Query memakai skema gis_db_v3 (master.*, spatial.*, trx.*). Nama route dan
bentuk response mengikuti kontrak frontend yang sudah ada.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api import deps
from app.api.params import read_upload
from app.schemas.spatial import PaginatedResponse
from app.services import block_detail_service, block_upload_service, hierarchy_service, history_service, map_service
from app.services.block_filter import BlockFilter
from app.services.layers.catalog_service import generic_tables
from app.utils.period import as_of_period

router = APIRouter()


@router.get("/area", response_model=PaginatedResponse)
def get_area_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode area"),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    # Master area di v3 tidak berperiode; bulan/tahun diterima agar query lama tetap valid.
    del bulan, tahun, current_user
    return hierarchy_service.list_areas(db, search, page, limit)


@router.get("/pt", response_model=PaginatedResponse)
def get_pt_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode PT"),
    kode_pt: Optional[str] = Query(None),
    area_id: Optional[str] = Query(None, description="Kode atau ID area"),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del bulan, tahun, current_user
    return hierarchy_service.list_companies(db, search, kode_pt, area_id, page, limit)


@router.get("/estate", response_model=PaginatedResponse)
def get_estate_list(
    search: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    area_id: Optional[str] = Query(None, description="Kode atau ID area"),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del bulan, tahun, current_user
    return hierarchy_service.list_estates(db, search, kode_pt, kode_est, area_id, page, limit)


@router.get("/afdeling", response_model=PaginatedResponse)
def get_afdeling_list(
    search: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del bulan, tahun, current_user
    return hierarchy_service.list_divisions(db, search, kode_pt, kode_est, kode_afd, page, limit)


@router.get("/blok", response_model=PaginatedResponse)
def get_blok_list(
    search: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    flt = BlockFilter(kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok)
    return hierarchy_service.list_blocks(db, search, flt, as_of_period(bulan, tahun), page, limit)


@router.get("/geojson")
def get_blocks_geojson(
    area_id: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    flt = BlockFilter(
        area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok, ownership=ownership,
    )
    return map_service.blocks_geojson(db, flt, as_of_period(bulan, tahun))


@router.get("/blok/detail", summary="Atribut popup peta blok")
def get_blok_detail(
    blok_id: str = Query(..., description="ID numerik, kode blok, atau ID lama"),
    tahun_tanam: Optional[int] = Query(None, ge=1900),
    ownership: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    return block_detail_service.get_block_detail(
        db, blok_id, tahun_tanam=tahun_tanam, ownership=ownership, bulan=bulan, tahun=tahun,
    )


@router.get("/history/tables", summary="Daftar tabel untuk GET /history")
def get_history_tables(current_user=Depends(deps.get_current_user)):
    del current_user
    return history_service.list_history_tables()


@router.get("/history", summary="Histori transaksi per wilayah")
def get_history_data(
    table: str = Query("trx_produksi_tbs"),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    tahun_tanam: Optional[int] = Query(None, ge=1900, le=2100),
    area_id: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    blok_id: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    flt = BlockFilter(
        area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd,
        blok=blok_id or kode_blok, ownership=ownership,
    )
    return history_service.get_history(db, table, tahun if tahun is not None else tahun_tanam, flt)


@router.get("/tph/geojson", summary="Titik TPH sebagai GeoJSON")
def get_tph_geojson(
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    kategori: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    flt = BlockFilter(kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok)
    return map_service.tph_geojson(db, flt, kategori, bulan, tahun)


@router.post("/blok-geometry/upload-analyze", summary="Analisis GeoJSON batas blok")
def upload_geometry_analyze(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=1900, le=2100),
    file: UploadFile = File(...),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    return block_upload_service.analyze(db, read_upload(file), bulan, tahun)


@router.post("/blok-geometry/upload-execute", summary="Simpan GeoJSON batas blok")
def upload_blok_geometry(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=1900, le=2100),
    file: UploadFile = File(...),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    result = block_upload_service.execute(db, read_upload(file), file.filename, bulan, tahun, current_user.id)
    return {"status": "success", "data": result}


@router.delete("/cleanup-period", summary="Hapus data spasial satu periode")
def delete_period_data(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    return block_upload_service.cleanup_period(db, bulan, tahun, generic_tables(db))
