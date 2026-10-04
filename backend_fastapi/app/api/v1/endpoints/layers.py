"""
Router layer bawaan, dibangkitkan dari LayerSpec (satu factory, bukan 5 file salinan).

Setiap layer mendapat path yang dicatat di spatial.layer_types.endpoints:
    POST /{kode}/upload-analyze, POST /{kode}/upload-execute, GET /{kode}/geojson
plus GET /{kode}/list, DELETE /{kode}/cleanup-period, dan alias lama
POST /{kode}/analyze & POST /{kode}/upload.
"""
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CanUploadGeojson, CurrentUser, DbSession
from app.api.params import BlockFilterDep, Bulan, BulanWajib, Tahun, TahunTanam, TahunWajib, UploadedFile, read_upload
from app.services import user_access
from app.services.layers import layer_service, sawit_service
from app.services.layers.specs import LAYER_SPECS, SAWIT_LABEL, LayerSpec

BlokParam = Annotated[str | None, Query(description="Filter opsional per blok (ID/kode)")]


def _layer_router(spec: LayerSpec, include_geojson: bool = True) -> APIRouter:
    router = APIRouter(prefix=f"/{spec.code}", tags=[f"Layer {spec.label}"])

    def analyze(db: DbSession, _: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib, file: UploadedFile):
        result = layer_service.analyze(db, spec, read_upload(file), bulan, tahun)
        return {"status": "success", "message": f"Analisis file GeoJSON {spec.code} berhasil.", "data": result}

    def execute(db: DbSession, user: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib, file: UploadedFile):
        stats = layer_service.execute(db, spec, read_upload(file), file.filename, bulan, tahun, user.id)
        return {"status": "success", "message": f"Proses upload spasial {spec.code} periode {bulan}-{tahun} selesai.",
                "detail": stats}

    def list_rows(db: DbSession, user: CurrentUser, bulan: BulanWajib, tahun: TahunWajib, blok_id: BlokParam = None):
        user_access.require_layer(db, user, spec.code)
        return layer_service.list_rows(db, spec, bulan, tahun, blok_id)

    def geojson(db: DbSession, user: CurrentUser, flt: BlockFilterDep, bulan: Bulan = None, tahun: Tahun = None):
        user_access.require_layer(db, user, spec.code)
        user_access.apply_data_scope(db, user, flt)
        return layer_service.geojson(db, spec, flt, bulan, tahun)

    def cleanup(db: DbSession, _: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib):
        return layer_service.cleanup(db, spec, bulan, tahun)

    router.add_api_route("/upload-analyze", analyze, methods=["POST"], summary=f"{spec.label} TAHAP 1: analisis")
    router.add_api_route("/upload-execute", execute, methods=["POST"], summary=f"{spec.label} TAHAP 2: simpan")
    router.add_api_route("/analyze", analyze, methods=["POST"], include_in_schema=False)
    router.add_api_route("/upload", execute, methods=["POST"], include_in_schema=False)
    router.add_api_route("/list", list_rows, methods=["GET"], summary=f"Daftar {spec.label} per periode")
    if include_geojson:
        router.add_api_route("/geojson", geojson, methods=["GET"], summary=f"GeoJSON {spec.label}")
    router.add_api_route("/cleanup-period", cleanup, methods=["DELETE"], summary=f"Hapus {spec.label} satu periode")
    return router


def _sawit_router() -> APIRouter:
    router = APIRouter(prefix="/sawit", tags=[f"Layer {SAWIT_LABEL}"])

    def analyze(db: DbSession, _: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib, file: UploadedFile):
        result = sawit_service.analyze(db, read_upload(file), bulan, tahun)
        return {"status": "success", "message": "Analisis file GeoJSON sawit berhasil.", "data": result}

    def execute(db: DbSession, user: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib, file: UploadedFile):
        stats = sawit_service.execute(db, read_upload(file), file.filename, bulan, tahun, user.id)
        return {"status": "success", "message": f"Proses bulk upload spasial sawit periode {bulan}-{tahun} selesai.",
                "detail": stats}

    def list_rows(db: DbSession, user: CurrentUser, bulan: BulanWajib, tahun: TahunWajib, blok_id: BlokParam = None,
                  tahun_tanam: TahunTanam = None):
        user_access.require_layer(db, user, "sawit")
        return sawit_service.list_rows(db, bulan, tahun, blok_id, tahun_tanam)

    def geojson(db: DbSession, user: CurrentUser, flt: BlockFilterDep, bulan: Bulan = None, tahun: Tahun = None):
        user_access.require_layer(db, user, "sawit")
        user_access.apply_data_scope(db, user, flt)
        return sawit_service.geojson(db, flt, bulan, tahun)

    def cleanup(db: DbSession, _: CanUploadGeojson, bulan: BulanWajib, tahun: TahunWajib):
        return sawit_service.cleanup(db, bulan, tahun)

    router.add_api_route("/upload-analyze", analyze, methods=["POST"], summary="SAWIT TAHAP 1: analisis")
    router.add_api_route("/upload-execute", execute, methods=["POST"], summary="SAWIT TAHAP 2: simpan")
    router.add_api_route("/analyze", analyze, methods=["POST"], include_in_schema=False)
    router.add_api_route("/upload", execute, methods=["POST"], include_in_schema=False)
    router.add_api_route("/list", list_rows, methods=["GET"], summary="Daftar pokok sawit per periode")
    router.add_api_route("/geojson", geojson, methods=["GET"], summary="GeoJSON pokok sawit")
    router.add_api_route("/cleanup-period", cleanup, methods=["DELETE"], summary="Hapus sensus sawit satu periode")
    return router


router = APIRouter()
router.include_router(_sawit_router())
for _spec in LAYER_SPECS.values():
    # GeoJSON TPH punya properti khusus (tph_id, nama_blok, ...) -> ditangani spatial.py.
    router.include_router(_layer_router(_spec, include_geojson=_spec.code != "tph"))
