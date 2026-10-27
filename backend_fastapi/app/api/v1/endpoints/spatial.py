"""
Endpoint spasial untuk peta: hierarki, GeoJSON, detail blok, histori, dan upload batas blok.

Query memakai skema gis_db_v3 (master.*, spatial.*, trx.*). Nama route dan
bentuk response mengikuti kontrak frontend yang sudah ada.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field

from app.api import deps
from app.api.params import read_upload
from app.core.exceptions import bad_request
from app.schemas.spatial import PaginatedResponse
from app.services import (
    area_statement_summary_service, block_detail_service, block_upload_service, hierarchy_service, history_service, map_service, master_service,
    user_access,
)
from app.services.block_filter import BlockFilter
from app.services.layers.catalog_service import generic_tables
from app.services.upload import runner
from app.services.upload.runner import UploadInput
from app.utils.period import as_of_period

router = APIRouter()


@router.get("/grup", response_model=PaginatedResponse, summary="Daftar grup (TPA, SGA) untuk filter peta")
def get_group_list(
    search: Optional[str] = Query(None, description="Cari kode atau nama grup"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    return hierarchy_service.list_groups(
        db, search, page, limit, extra_clause=user_access.hierarchy_clause(db, current_user, "estate"),
    )


class GroupChange(BaseModel):
    kode_grup: str = Field(..., min_length=1, description="Kode/nama grup yang sudah terdaftar (mis. TPA, SGA)")


class AreaChange(BaseModel):
    kode_area: str = Field(..., min_length=1, description="Kode/nama area yang sudah terdaftar (mis. KUTIM4)")


@router.put("/pt/{kode_pt}/grup", summary="Ganti grup PT (koreksi manual master)",
            description="Grup resmi berasal dari upload GeoJSON blok; endpoint ini untuk koreksi satu PT. "
                        "Hanya grup yang sudah terdaftar. Butuh permission `upload:geojson`.")
def put_company_group(kode_pt: str, payload: GroupChange, db: deps.DbSession, current_user: deps.CanUploadGeojson):
    return master_service.set_company_group(db, current_user, kode_pt, payload.kode_grup)


@router.put("/estate/{kode_est}/area", summary="Ganti area saat ini estate (koreksi manual master)",
            description="Area resmi berasal dari upload GeoJSON blok; riwayat area per bulan di areal statement tidak "
                        "berubah. Hanya area yang sudah terdaftar. Butuh permission `upload:geojson`.")
def put_estate_area(kode_est: str, payload: AreaChange, db: deps.DbSession, current_user: deps.CanUploadGeojson):
    return master_service.set_estate_area(db, current_user, kode_est, payload.kode_area)


@router.get("/area", response_model=PaginatedResponse)
def get_area_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode area"),
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
    kode_pt: Optional[str] = Query(None, description="Kode/ID PT: hanya area estate PT ini"),

    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    # Master area di v3 tidak berperiode; bulan/tahun diterima agar query lama tetap valid.
    del bulan, tahun
    return hierarchy_service.list_areas(
        db, search, page, limit, extra_clause=user_access.hierarchy_clause(db, current_user, "area"), grup=kode_grup,
        kode_pt=kode_pt,
    )


@router.get("/pt", response_model=PaginatedResponse)
def get_pt_list(
    search: Optional[str] = Query(None, description="Cari nama atau kode PT"),
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
    kode_pt: Optional[str] = Query(None),
    area_id: Optional[str] = Query(None, description="Kode atau ID area"),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del bulan, tahun
    return hierarchy_service.list_companies(
        db, search, kode_pt, area_id, page, limit,
        extra_clause=user_access.hierarchy_clause(db, current_user, "company"), grup=kode_grup,
    )


@router.get("/estate", response_model=PaginatedResponse)
def get_estate_list(
    search: Optional[str] = Query(None),
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
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
    del bulan, tahun
    return hierarchy_service.list_estates(
        db, search, kode_pt, kode_est, area_id, page, limit,
        extra_clause=user_access.hierarchy_clause(db, current_user, "estate"), grup=kode_grup,
    )


@router.get("/afdeling", response_model=PaginatedResponse)
def get_afdeling_list(
    search: Optional[str] = Query(None),
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
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
    del bulan, tahun
    return hierarchy_service.list_divisions(
        db, search, kode_pt, kode_est, kode_afd, page, limit,
        extra_clause=user_access.hierarchy_clause(db, current_user, "division"), grup=kode_grup,
    )


@router.get("/blok", response_model=PaginatedResponse)
def get_blok_list(
    search: Optional[str] = Query(None),
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    tahun_tanam: Optional[int] = Query(None, ge=0, le=2100, description="Filter tahun tanam blok (0 = belum ditanam)"),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    flt = BlockFilter(grup=kode_grup, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok)
    user_access.apply_data_scope(db, current_user, flt)
    return hierarchy_service.list_blocks(db, search, flt, as_of_period(bulan, tahun), page, limit, tahun_tanam)


@router.get("/periode-terakhir", summary="Periode terakhir yang sudah diupload (default filter Periode)",
            description="Bulan/tahun default untuk filter Periode di peta: periode produksi TBS terakhir "
                        "pada wilayah yang difilter; bila belum ada produksi, areal statement terakhir, lalu batas "
                        "blok terakhir. `per_data` berisi periode terakhir tiap jenis data. Mengikuti hak akses user.")
def get_latest_period(
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
    area_id: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    flt = BlockFilter(grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd)
    user_access.apply_data_scope(db, current_user, flt)
    return map_service.latest_periods(db, flt, user_access.transaction_keys(db, current_user))


_GEOJSON_DOC = """
Batas blok (poligon terbaru s/d bulan/tahun) beserta ringkasan transaksi per blok.

**Rentang `produksi_tbs`** ditentukan `bulan`, `tahun`, dan `year_to_date`:

| year_to_date | bulan | Data yang diproses |
|---|---|---|
| true | diisi (mis. 10) | Januari s/d Oktober tahun itu |
| true | kosong | Januari s/d bulan berjalan (tahun lalu: s/d Desember) |
| false | diisi | bulan itu saja |
| false | kosong | bulan terakhir yang sudah diupload di tahun itu (blok yang difilter) |

`areal_statement` (dan luas tanam untuk yield) = statement terbaru di tahun yang sama s/d akhir rentang.
`produksi_tbs.periode_awal` / `periode_akhir` / `year_to_date` menjelaskan rentang yang dipakai.

**Pembanding:** bila `bulan_comparison` dan `tahun_comparison` diisi, tiap blok mendapat
`produksi_tbs_comparison` (struktur sama dengan `produksi_tbs`, aturan `year_to_date` sama) untuk
membandingkan `kategori_budget` / `kategori_sensus`. Keduanya harus diisi bersamaan.
"""


@router.get("/blok/options", summary="Opsi dropdown blok (ringan, semua blok dalam hak akses, satu request)")
def get_blok_options(
    kode_grup: Optional[str] = Query(None),
    area_id: Optional[str] = Query(None, description="Kode/ID area. Kosong = semua area dalam hak akses"),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    flt = BlockFilter(grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd)
    user_access.apply_data_scope(db, current_user, flt)
    return {"data": map_service.block_options(db, flt)}


@router.get("/geojson", summary="GeoJSON batas blok + ringkasan transaksi", description=_GEOJSON_DOC)
def get_blocks_geojson(
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
    area_id: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    year_to_date: bool = Query(False, description="true = akumulasi Januari s/d bulan (lihat tabel di atas)"),
    bulan_comparison: Optional[int] = Query(None, ge=1, le=12,
                                            description="Bulan pembanding (wajib bersama tahun_comparison)"),
    tahun_comparison: Optional[int] = Query(None, ge=1900, le=2100,
                                            description="Tahun pembanding (wajib bersama bulan_comparison)"),
    simplify: Optional[float] = Query(None, ge=0, le=20,
                                      description="Sederhanakan garis batas (meter, maks 20) untuk tampilan lingkup "
                                                  "luas. Kosong/0 = geometri asli."),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    if (bulan_comparison is None) != (tahun_comparison is None):
        raise bad_request("bulan_comparison dan tahun_comparison harus diisi bersamaan.",
                          field="bulan_comparison" if bulan_comparison is None else "tahun_comparison")
    flt = BlockFilter(
        grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok,
        ownership=ownership,
    )
    user_access.apply_data_scope(db, current_user, flt)
    hide_keys = user_access.hidden_feature_keys(db, current_user)
    comparison = (bulan_comparison, tahun_comparison) if bulan_comparison is not None else None
    return map_service.blocks_geojson(db, flt, bulan, tahun, year_to_date=year_to_date, comparison=comparison,
                                      hide_keys=hide_keys, simplify_m=simplify)


@router.get("/blok/detail", summary="Atribut popup peta blok")
def get_blok_detail(
    blok_id: str = Query(..., description="ID numerik, kode blok, atau ID lama"),
    tahun_tanam: Optional[int] = Query(None, ge=0, le=2100, description="0 = belum ditanam"),
    ownership: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    year_to_date: bool = Query(False, description="true = TBS/janjang/BJR Januari s/d bulan periode (sama dengan GeoJSON)"),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    block_id = block_detail_service.resolve_block_id(db, blok_id)
    user_access.ensure_block_in_scope(db, current_user, block_id)
    detail = block_detail_service.get_block_detail(
        db, blok_id, tahun_tanam=tahun_tanam, ownership=ownership, bulan=bulan, tahun=tahun,
        year_to_date=year_to_date,
    )
    return user_access.redact_block_detail(db, current_user, detail)


@router.get("/history/tables", summary="Daftar tabel untuk GET /history")
def get_history_tables(db=Depends(deps.get_db), current_user=Depends(deps.get_current_user)):
    rows = history_service.list_history_tables()
    allowed = user_access.transaction_keys(db, current_user)
    if allowed is None:
        return rows
    return [row for row in rows if row["physical_table"] in allowed or row["table"] in allowed]


@router.get("/history/tahun-tanam", summary="Daftar tahun filter histori dari semua tabel schema trx")
def get_history_planting_years(
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA) saat ini milik PT. Kosong = semua"),
    area_id: Optional[str] = Query(
        None, description="Kode/ID area. Memakai area SAAT INI estate (master), bukan AreaCode per bulan di areal statement",
    ),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    blok_id: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    user_access.require_transaction(db, current_user, "trx_areal_statement", "trx.area_statements")
    flt = BlockFilter(
        grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd,
        blok=blok_id or kode_blok, ownership=ownership,
    )
    user_access.apply_data_scope(db, current_user, flt)
    years = history_service.list_planting_years(db, flt)
    return {"data": years, "total": len(years)}


@router.get("/layer-data/areal", summary="Rincian Areal Tanam dan Areal Non-Tanam/Landuse untuk Layer Data",
            description="Satu respons untuk scope filter: `areal_tanam` (total, per status TM/TBM/LC, per tahun tanam), "
                        "`populasi` (per kelas kerapatan pokok >136, 130-135, <130 pokok/ha), `tidak_tertanam_dalam_blok` "
                        "(luas tanah blok dikurangi luas tanam), `areal_non_tanam` (per baris laporan dan per kategori landuse, dengan jumlah poligon) dan `total` "
                        "(areal tanam + non-tanam, persen). `persen` = terhadap totalnya sendiri, `persen_grand_total` = "
                        "terhadap grand total areal. Areal tanam memakai snapshot areal statement, non-tanam memakai snapshot "
                        "landuse; keduanya terbaru s/d bulan/tahun dan periodenya dilaporkan terpisah di `periode`. "
                        "Bagian tanpa hak akses (transaksi areal statement / layer landuse) atau tanpa data bernilai null; "
                        "403 bila keduanya tidak diizinkan.")
def get_layer_data_areal(
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA) saat ini milik PT. Kosong = semua"),
    area_id: Optional[str] = Query(None, description="Kode/ID area (area saat ini estate)"),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    blok_id: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    tanam_allowed = user_access.transaction_granted(db, current_user, "trx_areal_statement", "trx.area_statements")
    non_tanam_allowed = user_access.layer_allowed(db, current_user, "landuse")
    if not (tanam_allowed or non_tanam_allowed):
        user_access.require_transaction(db, current_user, "trx_areal_statement", "trx.area_statements")
    flt = BlockFilter(
        grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd,
        blok=blok_id or kode_blok, ownership=ownership,
    )
    user_access.apply_data_scope(db, current_user, flt)
    return area_statement_summary_service.layer_data_areal(db, flt, as_of_period(bulan, tahun), tanam_allowed, non_tanam_allowed)


@router.get("/history", summary="Histori transaksi per wilayah")
def get_history_data(
    table: str = Query("trx_produksi_tbs"),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    bulan: Optional[int] = Query(
        None, ge=1, le=12,
        description="Filter bulan: hanya periode bulan itu (bersama `tahun` = satu periode; tanpa `tahun` = bulan "
                    "itu di tiap tahun). Areal statement = snapshot s/d bulan itu. Baris respons per bulan.",
    ),
    tahun_tanam: Optional[int] = Query(
        None, ge=0, le=2100,
        description="Filter tahun transaksi. Tabel trx yang punya planting_year disaring kolom itu; selain itu tahun kolom period.",
    ),
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA) saat ini milik PT. Kosong = semua"),
    area_id: Optional[str] = Query(
        None, description="Kode/ID area. Memakai area SAAT INI estate (master), bukan AreaCode per bulan di areal statement",
    ),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    blok_id: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    gap_bulan: Optional[int] = Query(None, ge=1, le=12, description="Periode ringkasan GAP produksi (dengan gap_tahun); kosong = terbaru"),
    gap_tahun: Optional[int] = Query(None, ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    legacy_key, physical = history_service.resolve_history_table(table)
    user_access.require_transaction(db, current_user, legacy_key, physical)
    flt = BlockFilter(
        grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd,
        blok=blok_id or kode_blok, ownership=ownership,
    )
    user_access.apply_data_scope(db, current_user, flt)
    # tahun_tanam mengikuti kolom tabel: planting_year bila ada, selain itu tahun period.
    # `tahun` tetap drill bulanan tahun kalender untuk tabel tanpa planting_year.
    return history_service.get_history(
        db, table, tahun, flt, period_year=tahun_tanam, gap_as_of=as_of_period(gap_bulan, gap_tahun),
        bulan=bulan,
    )


@router.get("/tph/geojson", summary="Titik TPH sebagai GeoJSON")
def get_tph_geojson(
    kode_grup: Optional[str] = Query(None, description="Kode/ID grup (TPA, SGA). Kosong = semua"),
    area_id: Optional[str] = Query(None),
    kode_pt: Optional[str] = Query(None),
    kode_est: Optional[str] = Query(None),
    kode_afd: Optional[str] = Query(None),
    kode_blok: Optional[str] = Query(None),
    ownership: Optional[str] = Query(None),
    tahun_tanam: Optional[int] = Query(None, ge=0, le=2100),
    kategori: Optional[str] = Query(None),
    bulan: Optional[int] = Query(None, ge=1, le=12),
    tahun: Optional[int] = Query(None, ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    user_access.require_layer(db, current_user, "tph")
    flt = BlockFilter(
        grup=kode_grup, area=area_id, kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd, blok=kode_blok,
        ownership=ownership, tahun_tanam=None if tahun_tanam is None else str(tahun_tanam),
    )
    user_access.apply_data_scope(db, current_user, flt)
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
    return runner.blok(db, runner.ANALYZE, UploadInput(read_upload(file), file.filename, bulan, tahun))


@router.post("/blok-geometry/upload-execute", summary="Simpan GeoJSON batas blok")
def upload_blok_geometry(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=1900, le=2100),
    file: UploadFile = File(...),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    return runner.blok(db, runner.EXECUTE, UploadInput(read_upload(file), file.filename, bulan, tahun, current_user.id))


@router.delete("/cleanup-period", summary="Hapus data spasial satu periode")
def delete_period_data(
    bulan: int = Query(..., ge=1, le=12),
    tahun: int = Query(..., ge=1900, le=2100),
    db=Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    del current_user
    return block_upload_service.cleanup_period(db, bulan, tahun, generic_tables(db))
