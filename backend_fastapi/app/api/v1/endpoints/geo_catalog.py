"""
Katalog jenis data geo & layer dinamis (dipasang di bawah /spatial).

URUTAN ROUTE PENTING: path literal (/geo/catalog, /geo/jenis, ...) harus
didaftarkan sebelum /geo/{kode} supaya tidak tertangkap sebagai kode.
"""
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.deps import CanUploadGeojson, CurrentUser, DbSession
from app.api.params import (
    BlockFilterDep, Bulan, BulanWajib, Limit, Page, Tahun, TahunWajib, UploadedFile, read_upload,
)
from app.services import user_access
from app.services.block_filter import BlockFilter
from app.services.layers import catalog_service

router = APIRouter(prefix="/geo")


class KolomSchema(BaseModel):
    nama_properti: str
    nama_kolom: str
    tipe: str = Field(description="boolean | integer | float | date | text")
    nullable: bool = True


class JenisCreateRequest(BaseModel):
    kode: str
    nama: str
    deskripsi: str | None = None
    geometry_type: str = Field(description="POINT | LINESTRING | POLYGON | MULTIPOINT | MULTILINESTRING | MULTIPOLYGON")
    relasi_blok: bool = Field(True, description="Data terikat ke blok (hierarki kebun)?")
    kolom: list[KolomSchema]


class LegacyJenisRegisterRequest(BaseModel):
    kode: str
    nama: str
    deskripsi: str | None = None
    table_name: str = Field(description="Tabel fisik yang sudah ada, format schema.tabel (mis. spatial.roads)")
    geometry_type: str
    relasi_blok: bool = True
    endpoints: dict[str, str] = Field(description="Wajib: upload_analyze, upload_execute, geojson")


BlokParam = Annotated[str | None, Query(description="Alias lama untuk kode_blok (ID/kode blok)")]


@router.get("/catalog", summary="Katalog seluruh jenis data geo (LEGACY & GENERIC) beserta endpoint-nya")
def catalog(db: DbSession, user: CurrentUser, search: Annotated[str | None, Query()] = None):
    layers = catalog_service.list_layers(db, search)
    if not layers and not (search and search.strip()):
        catalog_service.seed_legacy(db)
        layers = catalog_service.list_layers(db, search)
    allowed = user_access.transaction_keys(db, user)
    if allowed is not None:
        def granted(layer: dict) -> bool:
            keys = {
                str(layer.get("kode") or "").strip().lower(),
                str(layer.get("table_name") or "").strip().lower(),
            }
            keys.discard("")
            return bool(keys & allowed)

        layers = [layer for layer in layers if granted(layer)]
    return [
        {k: layer[k] for k in ("kode", "nama", "deskripsi", "table_name", "geometry_type", "relasi_blok", "handler_type", "endpoints")}
        for layer in layers
    ]


@router.post("/jenis/analyze-sample", summary="Analisis GeoJSON contoh -> usulan skema kolom & tipe geometry")
def analyze_sample(_: CanUploadGeojson, file: UploadedFile):
    return catalog_service.analyze_sample(read_upload(file))


@router.get("/jenis", summary="Daftar semua jenis")
def list_jenis(db: DbSession, _: CurrentUser, search: Annotated[str | None, Query()] = None):
    return catalog_service.list_layers(db, search)


@router.post("/jenis", summary="Buat jenis GENERIC baru (CREATE TABLE spatial.geo_dyn_<kode>)")
def create_jenis(payload: JenisCreateRequest, db: DbSession, user: CanUploadGeojson):
    return catalog_service.create_layer(
        db, kode=payload.kode, nama=payload.nama, deskripsi=payload.deskripsi, geometry_type=payload.geometry_type,
        relasi_blok=payload.relasi_blok, kolom=[k.model_dump() for k in payload.kolom], created_by=str(user.id),
    )


@router.post("/jenis/register-legacy", summary="Daftarkan jenis dengan tabel & endpoint yang sudah ada")
def register_legacy(payload: LegacyJenisRegisterRequest, db: DbSession, _: CanUploadGeojson):
    return catalog_service.register_legacy(db, **payload.model_dump())


@router.post("/jenis/seed-legacy", summary="Daftarkan jenis bawaan (blok, tph, sawit, ...) -- idempoten")
def seed_legacy(db: DbSession, _: CanUploadGeojson):
    return {"hasil": catalog_service.seed_legacy(db)}


@router.post("/{kode}/upload-analyze", summary="[GENERIC] TAHAP 1: analisis data sebelum diunggah")
def generic_analyze(kode: str, db: DbSession, _: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib,
                    file: UploadedFile):
    layer = catalog_service.get_generic_layer(db, kode)
    return catalog_service.analyze_generic(db, layer, read_upload(file), bulan, tahun)


@router.post("/{kode}/upload-execute", summary="[GENERIC] TAHAP 2: simpan data")
def generic_execute(kode: str, db: DbSession, user: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib,
                    file: UploadedFile):
    layer = catalog_service.get_generic_layer(db, kode)
    result = catalog_service.execute_generic(db, layer, read_upload(file), file.filename, bulan, tahun, user.id)
    return {"status": "success", "data": result}


def _scoped_filter(db, user, layer: dict, flt: BlockFilter, blok_id: str | None) -> BlockFilter:
    """Filter hierarki + scope wilayah user (seperti layer bawaan). `blok_id` = alias lama untuk kode_blok."""
    if blok_id and not flt.blok:
        flt.blok = blok_id.strip() or None
    if layer["relasi_blok"]:
        user_access.apply_data_scope(db, user, flt)
    return flt


@router.get("/{kode}/geojson", summary="[GENERIC] GeoJSON FeatureCollection")
def generic_geojson(kode: str, db: DbSession, user: CurrentUser, flt: BlockFilterDep, bulan: Bulan = None,
                    tahun: Tahun = None, blok_id: BlokParam = None):
    user_access.require_layer(db, user, kode)
    layer = catalog_service.get_generic_layer(db, kode)
    return catalog_service.generic_geojson(db, layer, bulan, tahun, _scoped_filter(db, user, layer, flt, blok_id))


@router.delete("/{kode}/cleanup-period", summary="[GENERIC] Hapus data satu periode")
def generic_cleanup(kode: str, db: DbSession, _: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib):
    layer = catalog_service.get_generic_layer(db, kode)
    return catalog_service.generic_cleanup(db, layer, bulan, tahun)


@router.get("/{kode}", summary="[GENERIC] Daftar data (tanpa geometry) dengan pagination")
def generic_list(kode: str, db: DbSession, user: CurrentUser, flt: BlockFilterDep, page: Page = 1, limit: Limit = 10,
                 bulan: Bulan = None, tahun: Tahun = None, blok_id: BlokParam = None):
    user_access.require_layer(db, user, kode)
    layer = catalog_service.get_generic_layer(db, kode)
    return catalog_service.generic_list(db, layer, page, limit, bulan, tahun,
                                        _scoped_filter(db, user, layer, flt, blok_id))
