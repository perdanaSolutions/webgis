"""
Data seed untuk mendaftarkan jenis geo "lama" (tabel & endpoint SUDAH ADA
sebelum sistem jenis-dinamis dibuat) ke katalog `geo_jenis`, supaya muncul
di `GET /geo/catalog` bersama jenis-jenis dinamis.

PENTING: modul ini TIDAK melakukan dispatch/proxy apa pun ke endpoint lama.
Isinya murni "alamat" -- kode, tabel, dan URL asli yang SUDAH BERJALAN --
yang disalin apa adanya ke kolom `geo_jenis.endpoints` lewat
`geo_dynamic_service.register_legacy_jenis`. FE nanti memanggil URL itu
langsung (mis. `POST /sawit/upload-analyze`), bukan lewat router ini.

STATUS ENDPOINT YANG SUDAH DIKONFIRMASI (dari kode yang sudah dibangun
sebelumnya di percakapan ini):
  - blok : /blok-geometry/upload-analyze, /blok-geometry/upload-execute, /geojson
  - tph  : /tph/upload-analyze, /tph/upload-execute, /tph/geojson

BELUM DIKONFIRMASI (perlu diisi dengan URL ASLI yang sebenarnya kamu
pakai -- jangan diasumsikan ikut pola `/{kode}/...` begitu saja, karena
`blok` di atas ternyata polanya beda sendiri, "/blok-geometry/...", bukan
"/blok/..."):
  - sawit, jalan, jembatan, landuse, slope

Cara mengisi: ganti nilai "endpoints" di bawah dengan path yang benar-benar
kamu pakai di router masing-masing, lalu jalankan `seed_default_legacy_jenis`
sekali (lewat endpoint `POST /geo/jenis/seed-legacy` atau skrip CLI/startup).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

DEFAULT_LEGACY_JENIS = [
    {
        "kode": "blok",
        "nama": "Blok Kebun",
        "deskripsi": "Master data & geometri polygon blok kebun (PT/Estate/Afdeling/Blok).",
        "table_name": "geo_blok",
        "geometry_type": "POLYGON",
        "relasi_blok": False,  # blok ITU SENDIRI yang jadi induk hierarki, bukan turunan blok lain
        "endpoints": {
            "upload_analyze": "/blok-geometry/upload-analyze",
            "upload_execute": "/blok-geometry/upload-execute",
            "geojson": "/geojson",
            "list": "/blok",
            "cleanup_period": "/cleanup-period",  # catatan: ini cleanup GABUNGAN semua tabel per periode, bukan khusus blok
        },
    },
    {
        "kode": "tph",
        "nama": "TPH",
        "deskripsi": "Titik Tempat Pengumpulan Hasil.",
        "table_name": "geo_tph",
        "geometry_type": "POINT",
        "relasi_blok": True,
        "endpoints": {
            "upload_analyze": "/tph/upload-analyze",
            "upload_execute": "/tph/upload-execute",
            "geojson": "/tph/geojson",
            "cleanup_period": "/cleanup-period",
        },
    },
    # --- TODO: lengkapi 5 jenis di bawah dengan URL ASLI yang sebenarnya kamu pakai ---
    {
        "kode": "sawit",
        "nama": "Pokok Sawit",
        "deskripsi": "Titik pokok kelapa sawit per blok.",
        "table_name": "geo_sawit",
        "geometry_type": "POINT",
        "relasi_blok": True,
        "endpoints": {
            "upload_analyze": "/sawit/upload-analyze",
            "upload_execute": "/sawit/upload-execute",
            "geojson": "/sawit/geojson",
        },
    },
    {
        "kode": "slope",
        "nama": "Slope",
        "deskripsi": "Slope.",
        "table_name": "geo_slope",
        "geometry_type": "POLYGON",
        "relasi_blok": True,
        "endpoints": {
            "upload_analyze": "/slope/upload-analyze",
            "upload_execute": "/slope/upload-execute",
            "geojson": "/slope/geojson",
        },
    },
    {
        "kode": "landuse",
        "nama": "landuse",
        "deskripsi": "landuse.",
        "table_name": "geo_landuse",
        "geometry_type": "MultiPolygon",
        "relasi_blok": True,
        "endpoints": {
            "upload_analyze": "/landuse/upload-analyze",
            "upload_execute": "/landuse/upload-execute",
            "geojson": "/landuse/geojson",
        },
    },
    {
        "kode": "jalan",
        "nama": "jalan",
        "deskripsi": "jalan.",
        "table_name": "geo_jalan",
        "geometry_type": "MultiLineString",
        "relasi_blok": True,
        "endpoints": {
            "upload_analyze": "/jalan/upload-analyze",
            "upload_execute": "/jalan/upload-execute",
            "geojson": "/jalan/geojson",
        },
    },
    {
        "kode": "jembatan",
        "nama": "jembatan",
        "deskripsi": "jembatan.",
        "table_name": "geo_jembatan",
        "geometry_type": "POINT",
        "relasi_blok": True,
        "endpoints": {
            "upload_analyze": "/jembatan/upload-analyze",
            "upload_execute": "/jembatan/upload-execute",
            "geojson": "/jembatan/geojson",
        },
    },
    # {
    #     "kode": "jalan", "nama": "Jalan", "table_name": "geo_jalan",
    #     "geometry_type": "LINESTRING", "relasi_blok": False,
    #     "endpoints": {"upload_analyze": "...", "upload_execute": "...", "geojson": "..."},
    # },
    # {
    #     "kode": "jembatan", "nama": "Jembatan", "table_name": "geo_jembatan",
    #     "geometry_type": "POINT", "relasi_blok": False,
    #     "endpoints": {"upload_analyze": "...", "upload_execute": "...", "geojson": "..."},
    # },
    # {
    #     "kode": "landuse", "nama": "Land Use", "table_name": "geo_landuse",
    #     "geometry_type": "POLYGON", "relasi_blok": False,
    #     "endpoints": {"upload_analyze": "...", "upload_execute": "...", "geojson": "..."},
    # },
    # {
    #     "kode": "slope", "nama": "Kelerengan (Slope)", "table_name": "geo_slope",
    #     "geometry_type": "POLYGON", "relasi_blok": False,
    #     "endpoints": {"upload_analyze": "...", "upload_execute": "...", "geojson": "..."},
    # },
]


def seed_default_legacy_jenis(db: Session) -> list:
    """
    Daftarkan semua entri di `DEFAULT_LEGACY_JENIS` ke `geo_jenis`.
    Idempotent -- entri yang kode-nya sudah terdaftar akan dilewati, bukan error.
    """
    from app.services import geo_dynamic_service as service  # import lokal, hindari circular import

    hasil = []
    for item in DEFAULT_LEGACY_JENIS:
        existing = db.execute(text("SELECT id FROM geo_jenis WHERE kode = :k"), {"k": item["kode"]}).fetchone()
        if existing:
            hasil.append({"kode": item["kode"], "status": "sudah_terdaftar"})
            continue
        service.register_legacy_jenis(
            db=db,
            kode=item["kode"],
            nama=item["nama"],
            table_name=item["table_name"],
            geometry_type=item["geometry_type"],
            relasi_blok=item["relasi_blok"],
            endpoints=item["endpoints"],
            deskripsi=item.get("deskripsi"),
        )
        hasil.append({"kode": item["kode"], "status": "berhasil_didaftarkan"})
    return hasil