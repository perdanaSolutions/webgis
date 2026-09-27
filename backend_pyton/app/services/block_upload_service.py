"""
Upload GeoJSON batas blok: mendaftarkan master (PT -> estate -> afdeling -> blok)
yang belum ada, lalu menyimpan poligon ke spatial.block_boundaries per periode.

Catatan model v3:
- Master tidak berperiode; hanya batas blok yang berperiode (PK block_id + period),
  jadi upload ulang periode yang sama menimpa poligon blok tersebut.
- Area TIDAK disimpan di master (area melekat ke area statement), sehingga
  properti `Area` hanya dilaporkan di ringkasan analisis.
- PT baru dibuat dengan kode = nama yang dinormalisasi (maks 20 karakter)
  karena GeoJSON hanya membawa nama PT, bukan kode perusahaan.
"""
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.upload.batch import final_status, finish_batch, start_batch
from app.services.upload.resolvers import BlockIndex, RefResolver
from app.utils.geojson import geometry_to_ewkb, parse_features
from app.utils.parsing import clean_str, norm_key
from app.utils.period import period_label, to_period
from app.utils.sql import quote_table

TARGET_TABLE = "spatial.block_boundaries"


@dataclass
class BlockFeature:
    area: str | None
    company: str | None
    estate_code: str
    estate_name: str
    division: str
    block: str
    block_type: str | None
    geom: str | None


def _read_feature(props: dict, geometry: dict | None) -> BlockFeature | None:
    estate_code = clean_str(props.get("EstID") or props.get("Est") or props.get("Estate"))
    division, block = clean_str(props.get("Afdeling")), clean_str(props.get("Blok"))
    if not (estate_code and division and block):
        return None
    return BlockFeature(
        area=clean_str(props.get("Area")),
        company=clean_str(props.get("PT")),
        estate_code=estate_code,
        estate_name=clean_str(props.get("Estate")) or estate_code,
        division=division,
        block=block,
        block_type=clean_str(props.get("Kategori") or props.get("TipeBlok")),
        geom=geometry_to_ewkb(geometry, "MULTIPOLYGON"),
    )


def analyze(db: Session, content: bytes, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    features = parse_features(content)
    index = BlockIndex.load(db)
    existing_boundaries = set(db.execute(
        text("SELECT block_id FROM spatial.block_boundaries WHERE period = :p"), {"p": period}
    ).scalars())

    new_blocks = overwrite = invalid = invalid_geom = 0
    areas, companies, estates, divisions, blocks = set(), set(), set(), set(), set()
    for feature in features:
        item = _read_feature(feature.get("properties") or {}, feature.get("geometry"))
        if item is None:
            invalid += 1
            continue
        if item.geom is None:
            invalid_geom += 1
            continue
        areas.add(norm_key(item.area))
        companies.add(norm_key(item.company))
        estates.add(norm_key(item.estate_code))
        divisions.add((norm_key(item.estate_code), norm_key(item.division)))
        blocks.add((norm_key(item.estate_code), norm_key(item.division), norm_key(item.block)))
        block_id = index.resolve((item.estate_code,), item.division, item.block)
        if block_id is None:
            new_blocks += 1
        elif block_id in existing_boundaries:
            overwrite += 1

    valid = len(features) - invalid - invalid_geom
    return {
        "tipe_upload": "GEOMETRI_BLOK_AND_MASTER_DATA",
        "periode": period_label(period),
        "total_fitur": len(features),
        "data_baru_di_periode_ini": valid - overwrite,
        "data_akan_ditimpa_di_periode_ini": overwrite,
        "blok_baru_di_master": new_blocks,
        "data_tidak_valid": invalid,
        "data_geometri_invalid": invalid_geom,
        "ringkasan_struktur_data": {
            "jumlah_master_area": len(areas - {""}),
            "jumlah_perusahaan_pt": len(companies - {""}),
            "jumlah_estate": len(estates),
            "jumlah_afdeling": len(divisions),
            "jumlah_blok": len(blocks),
        },
    }


@dataclass
class _MasterCache:
    companies: dict[str, int] = field(default_factory=dict)   # kode/nama ternormalisasi -> id
    estates: dict[str, tuple[int, int]] = field(default_factory=dict)  # kode estate -> (id, company_id)
    divisions: dict[tuple[int, str], int] = field(default_factory=dict)
    created: dict[str, int] = field(default_factory=lambda: {"perusahaan": 0, "estate": 0, "afdeling": 0, "blok": 0})

    @classmethod
    def load(cls, db: Session) -> "_MasterCache":
        cache = cls()
        for r in db.execute(text("SELECT id, code, name FROM master.companies")).mappings():
            for key in (r["code"], r["name"]):
                if key:
                    cache.companies.setdefault(norm_key(key), r["id"])
        for r in db.execute(text("SELECT id, code, company_id FROM master.estates")).mappings():
            cache.estates[norm_key(r["code"])] = (r["id"], r["company_id"])
        for r in db.execute(text("SELECT id, estate_id, code FROM master.divisions")).mappings():
            cache.divisions[(r["estate_id"], norm_key(r["code"]))] = r["id"]
        return cache


def _ensure_master(db: Session, cache: _MasterCache, index: BlockIndex, block_type_id: int | None, item: BlockFeature) -> int:
    estate = cache.estates.get(norm_key(item.estate_code))
    if estate is None:
        company_key = norm_key(item.company)
        if not company_key:
            raise ValueError(f"Estate '{item.estate_code}' belum terdaftar dan properti PT kosong.")
        company_id = cache.companies.get(company_key)
        if company_id is None:
            company_id = db.execute(
                text("INSERT INTO master.companies (code, name) VALUES (:code, :name) RETURNING id"),
                {"code": company_key[:20], "name": item.company},
            ).scalar_one()
            cache.companies[company_key] = company_id
            cache.created["perusahaan"] += 1
        estate_id = db.execute(
            text("INSERT INTO master.estates (company_id, code, name) VALUES (:c, :code, :name) RETURNING id"),
            {"c": company_id, "code": item.estate_code[:20], "name": item.estate_name[:100]},
        ).scalar_one()
        estate = (estate_id, company_id)
        cache.estates[norm_key(item.estate_code)] = estate
        index.estate_ids[norm_key(item.estate_code)] = estate_id
        cache.created["estate"] += 1

    estate_id = estate[0]
    division_id = cache.divisions.get((estate_id, norm_key(item.division)))
    if division_id is None:
        division_id = db.execute(
            text("INSERT INTO master.divisions (estate_id, code) VALUES (:e, :code) RETURNING id"),
            {"e": estate_id, "code": item.division[:20]},
        ).scalar_one()
        cache.divisions[(estate_id, norm_key(item.division))] = division_id
        cache.created["afdeling"] += 1

    block_id = index.resolve((item.estate_code,), item.division, item.block)
    if block_id is None:
        block_id = db.execute(
            text("INSERT INTO master.blocks (division_id, code, block_type_id) VALUES (:d, :code, :t) RETURNING id"),
            {"d": division_id, "code": item.block[:20], "t": block_type_id},
        ).scalar_one()
        index.add(estate_id, item.division, item.block, block_id)
        cache.created["blok"] += 1
    elif block_type_id is not None:
        db.execute(
            text("UPDATE master.blocks SET block_type_id = :t WHERE id = :id AND block_type_id IS DISTINCT FROM :t"),
            {"t": block_type_id, "id": block_id},
        )
    return block_id


def execute(db: Session, content: bytes, filename: str | None, bulan: int, tahun: int, user_id: UUID | None) -> dict:
    period = to_period(bulan, tahun)
    batch_id = start_batch(db, source_type="GEOJSON_UPLOAD", target_table=TARGET_TABLE, source_name=filename,
                           user_id=user_id, period=period, metadata={"layer": "blok"})
    features = parse_features(content)
    index, cache = BlockIndex.load(db), _MasterCache.load(db)
    block_types = RefResolver(db, "block_types")

    success, invalid, failed, last_error = 0, 0, 0, None
    saved_blocks: set[int] = set()
    for feature in features:
        item = _read_feature(feature.get("properties") or {}, feature.get("geometry"))
        if item is None or item.geom is None:
            invalid += 1
            continue
        block_type_id = block_types.resolve(item.block_type)  # di luar savepoint: id ref tetap valid
        savepoint = db.begin_nested()
        try:
            block_id = _ensure_master(db, cache, index, block_type_id, item)
            db.execute(
                text("""
                    INSERT INTO spatial.block_boundaries (block_id, period, geom, upload_batch_id)
                    VALUES (:b, :p, CAST(:g AS geometry), :batch)
                    ON CONFLICT (block_id, period) DO UPDATE SET geom = EXCLUDED.geom, upload_batch_id = EXCLUDED.upload_batch_id
                """),
                {"b": block_id, "p": period, "g": item.geom, "batch": str(batch_id)},
            )
            savepoint.commit()
            success += 1
            saved_blocks.add(block_id)
        except Exception as exc:  # satu fitur gagal tidak membatalkan fitur lain
            savepoint.rollback()
            failed += 1
            last_error = str(exc).splitlines()[0][:500]
            # Master yang baru dibuat di savepoint ini ikut batal -> muat ulang cache agar id-nya tidak basi.
            created = cache.created
            index, cache = BlockIndex.load(db), _MasterCache.load(db)
            cache.created = created
    db.commit()

    status = final_status(success, len(features))
    stats = {
        "sukses_master_perusahaan_baru": cache.created["perusahaan"],
        "sukses_master_estate_baru": cache.created["estate"],
        "sukses_master_afdeling_baru": cache.created["afdeling"],
        "sukses_master_blok_baru": cache.created["blok"],
        "sukses_geometri_polygon_blok": success,
        "blok_unik_tersimpan": len(saved_blocks),
        "properti_atau_geometri_invalid": invalid,
        "sistem_error_baris": failed,
        "tipe_blok_baru": block_types.created,
    }
    finish_batch(db, batch_id, status, success,
                 last_error or (None if status == "SUCCESS" else "Sebagian fitur tidak valid."), {"detail_statistik": stats})
    return {"batch_id": str(batch_id), "total_fitur_diproses": len(features), "status_proses": status, "detail_status": stats}


def cleanup_period(db: Session, bulan: int, tahun: int, generic_tables: list[tuple[str, str]]) -> dict:
    """Hapus seluruh data spasial berperiode untuk (bulan, tahun). Master tidak disentuh (tidak berperiode di v3)."""
    period = to_period(bulan, tahun)
    tables = [
        ("geometri_polygon_blok", "spatial.block_boundaries"),
        ("geometri_point_tph", "spatial.tph_points"),
        ("geo_jalan", "spatial.roads"),
        ("geo_jembatan", "spatial.bridges"),
        ("geo_landuse", "spatial.landuse_polygons"),
        ("geo_sawit", "spatial.tree_censuses"),
        ("geo_slope", "spatial.slope_polygons"),
        *generic_tables,
    ]
    deleted = {}
    for label, table in tables:
        deleted[label] = db.execute(text(f"DELETE FROM {quote_table(table)} WHERE period = :p"), {"p": period}).rowcount
    db.commit()
    return {
        "status": "success",
        "periode": period_label(period),
        "detail_terhapus": deleted,
        "catatan": "Master PT/estate/afdeling/blok tidak dihapus karena di gis_db_v3 master tidak berperiode.",
    }
