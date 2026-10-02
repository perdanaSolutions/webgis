"""
Pokok sawit di v3 = 2 tabel:
  spatial.palm_trees    : pohon fisik (objectid unik + titik), tidak berperiode
  spatial.tree_censuses : sensus per periode (blok, kategori, diameter, jarak)

Upload: COPY ke tabel staging sementara, lalu upsert pohon (berdasarkan
objectid) dan ganti sensus periode itu -- semuanya dalam satu transaksi.
"""
import json
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_filter import BlockFilter
from app.services.layers.specs import SAWIT_LABEL
from app.services.map_service import resolve_period
from app.services.upload.batch import final_status, finish_batch, start_batch
from app.services.upload import report as upload_report
from app.services.upload.copy import copy_rows
from app.services.upload.report import UploadReport, geometry_problem, missing_block_attributes
from app.services.upload.resolvers import (
    BlockIndex, BlockMatchReport, RefResolver, block_label, geojson_block_keys, match_blocks,
)
from app.utils.geojson import feature_collection, geometry_to_ewkb, parse_features
from app.utils.parsing import json_safe, to_float, to_int
from app.utils.period import period_label, to_period

TABLE = "spatial.tree_censuses"
_STAGE_COLUMNS = ["objectid", "block_id", "category_id", "diameter", "spacing", "geom"]


@dataclass
class PreparedSawit:
    total: int = 0
    rows: dict[int, dict] = field(default_factory=dict)  # objectid -> row
    invalid_props: int = 0
    invalid_geom: int = 0
    duplicates: int = 0
    match: BlockMatchReport = field(default_factory=BlockMatchReport)
    new_categories: list[str] = field(default_factory=list)
    unknown_categories: list[str] = field(default_factory=list)
    report: UploadReport = field(default_factory=UploadReport)


def _prepare(db: Session, content: bytes, create_refs: bool) -> PreparedSawit:
    features = parse_features(content)
    categories = RefResolver(db, "tree_categories", create_missing=create_refs)
    result = PreparedSawit(total=len(features), report=UploadReport(total=len(features)))
    report = result.report

    candidates: list[tuple[int, tuple, dict]] = []
    for i, feature in enumerate(features):
        props = feature.get("properties") or {}
        keys = geojson_block_keys(props)
        objectid = to_int(props.get("OBJECTID"))
        diameter, spacing = to_float(props.get("Diameter")), to_float(props.get("Jarak"))
        category = props.get("Kategori")
        if keys is None:
            result.invalid_props += 1
            report.reject(i, "ATRIBUT_BLOK_KOSONG", missing_block_attributes(props))
            continue
        problems = [msg for bad, msg in (
            (objectid is None, "OBJECTID kosong"),
            (not category, "Kategori kosong"),
            ((diameter or 0) < 0, f"Diameter negatif ({diameter})"),
            ((spacing or 0) < 0, f"Jarak negatif ({spacing})"),
        ) if bad]
        if problems:
            result.invalid_props += 1
            report.reject(i, "NILAI_TIDAK_VALID", "; ".join(problems))
            continue
        geom = geometry_to_ewkb(feature.get("geometry"), "POINT")
        if geom is None:
            result.invalid_geom += 1
            report.reject(i, "GEOMETRI_TIDAK_VALID", geometry_problem(feature.get("geometry"), "POINT"))
            continue
        category_id = categories.resolve(category)
        if category_id is None and create_refs:
            result.invalid_props += 1
            report.reject(i, "NILAI_TIDAK_VALID", f"Kategori '{category}' tidak bisa disimpan")
            continue
        candidates.append((i, keys, {
            "objectid": objectid, "category_id": category_id,
            "diameter": diameter, "spacing": spacing, "geom": geom,
        }))

    block_ids, result.match = match_blocks(db, BlockIndex.load(db), [(k, r["geom"]) for _, k, r in candidates])
    indexes: dict[int, int] = {}  # objectid -> fitur_index yang dipakai
    for (i, keys, row), block_id in zip(candidates, block_ids):
        if block_id is None:
            report.reject(i, "BLOK_TIDAK_DITEMUKAN", f"Blok {block_label(keys)} tidak ada di master.")
            continue
        row["block_id"] = block_id
        if row["objectid"] in result.rows:
            result.duplicates += 1
            report.reject(indexes[row["objectid"]], "OBJECTID_GANDA",
                          f"OBJECTID {row['objectid']} juga dipakai data #{i + 1}; data #{i + 1} yang dipakai.")
        result.rows[row["objectid"]] = row
        indexes[row["objectid"]] = i
    result.new_categories = categories.created
    result.unknown_categories = categories.unknown
    return result


def analyze(db: Session, content: bytes, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    prepared = _prepare(db, content, create_refs=False)
    blocks = sorted({r["block_id"] for r in prepared.rows.values()})
    will_replace = db.execute(
        text(f"SELECT count(*) FROM {TABLE} WHERE period = :p AND block_id = ANY(:b)"), {"p": period, "b": blocks}
    ).scalar_one() if blocks else 0
    notices = [{
        "kode": "NILAI_REFERENSI_BARU", "level": "INFO", "jumlah": len(prepared.unknown_categories),
        "pesan": "Kategori pokok berikut belum terdaftar dan akan DIBUAT otomatis saat upload: "
                 f"{', '.join(prepared.unknown_categories[:20])}. Pastikan bukan salah ketik.",
    }] if prepared.unknown_categories else []
    detail = upload_report.build(
        db, prepared.report, layer=SAWIT_LABEL, period=period, ready=len(prepared.rows),
        block_ids=[r["block_id"] for r in prepared.rows.values()], replaced=will_replace, match=prepared.match,
        notices=notices,
    )
    return {
        "tipe_upload": "SPATIAL_POINT_SAWIT",
        "periode": period_label(period),
        "status_analisis": detail["status_analisis"],
        "kesimpulan": detail["kesimpulan"],
        "total_data_sawit": prepared.total,
        "sawit_siap_diunggah": len(prepared.rows),
        "sawit_tertahan_karena_blok_belum_ada": prepared.match.missing,
        "data_properti_invalid": prepared.invalid_props,
        "data_geometri_invalid": prepared.invalid_geom,
        "duplikat_objectid_dalam_file": prepared.duplicates,
        "data_periode_ini_akan_diganti": will_replace,
        **prepared.match.as_dict(),
        "contoh_blok_tidak_ditemukan": prepared.match.unmatched_samples,
        "peringatan": detail["peringatan"],
        "rincian": detail["rincian"],
    }


def execute(db: Session, content: bytes, filename: str | None, bulan: int, tahun: int, user_id: UUID | None) -> dict:
    period = to_period(bulan, tahun)
    batch_id = start_batch(db, source_type="GEOJSON_UPLOAD", target_table=TABLE, source_name=filename,
                           user_id=user_id, period=period, metadata={"layer": "sawit"})
    try:
        prepared = _prepare(db, content, create_refs=True)
        replaced = 0
        if prepared.rows:
            db.execute(text("""
                CREATE TEMP TABLE _sawit_stage (
                    objectid bigint PRIMARY KEY, block_id bigint, category_id smallint,
                    diameter double precision, spacing double precision, geom geometry(Point, 4326)
                ) ON COMMIT DROP
            """))
            copy_rows(db, "_sawit_stage", _STAGE_COLUMNS,
                      ([r[c] for c in _STAGE_COLUMNS] for r in prepared.rows.values()))
            db.execute(text("""
                INSERT INTO spatial.palm_trees (objectid, geom)
                SELECT objectid, geom FROM _sawit_stage
                ON CONFLICT (objectid) DO UPDATE SET geom = EXCLUDED.geom
                WHERE NOT ST_Equals(spatial.palm_trees.geom, EXCLUDED.geom)
            """))
            replaced = db.execute(text("""
                DELETE FROM spatial.tree_censuses tc
                WHERE tc.period = :p AND (
                    tc.block_id IN (SELECT DISTINCT block_id FROM _sawit_stage)
                    OR tc.palm_tree_id IN (SELECT pt.id FROM spatial.palm_trees pt JOIN _sawit_stage s USING (objectid))
                )
            """), {"p": period}).rowcount
            db.execute(text("""
                INSERT INTO spatial.tree_censuses (palm_tree_id, period, block_id, category_id, diameter, spacing, upload_batch_id)
                SELECT pt.id, :p, s.block_id, s.category_id, s.diameter, s.spacing, :batch
                FROM _sawit_stage s JOIN spatial.palm_trees pt USING (objectid)
            """), {"p": period, "batch": str(batch_id)})
        db.commit()
    except Exception as exc:
        db.rollback()
        finish_batch(db, batch_id, "FAILED", 0, str(exc)[:2000], {"layer": "sawit"})
        raise

    success = len(prepared.rows)
    status = final_status(success, prepared.total)
    stats = {
        "sukses_terunggah": success,
        "tertahan_blok_missing": prepared.match.missing,
        "properti_invalid": prepared.invalid_props,
        "geometri_invalid": prepared.invalid_geom,
        "duplikat_dalam_file": prepared.duplicates,
        "data_lama_diganti": replaced,
        **prepared.match.as_dict(),
        "nilai_referensi_baru": {"tree_categories": prepared.new_categories} if prepared.new_categories else {},
        "sistem_error": 0,
    }
    error = None if status == "SUCCESS" else f"{prepared.total - success} dari {prepared.total} data tidak diunggah."
    finish_batch(db, batch_id, status, success, error, {"detail_statistik": stats})
    return {"batch_id": str(batch_id), "total_data_sawit_diproses": prepared.total, "status_proses": status, "detail_status": stats}


_SELECT = """
    SELECT pt.id, pt.objectid, tc.block_id, bl.code AS kode_blok, dv.code AS kode_afd, es.code AS kode_est,
           tc.diameter, tc.spacing, cat.name AS kategori, tc.period, ST_AsGeoJSON(pt.geom, 6) AS geometry_json
    FROM spatial.tree_censuses tc
    JOIN spatial.palm_trees pt ON pt.id = tc.palm_tree_id
    JOIN master.blocks bl ON bl.id = tc.block_id {joins}
    LEFT JOIN ref.tree_categories cat ON cat.id = tc.category_id
    WHERE {where}
    ORDER BY pt.objectid
"""


def _query(db: Session, flt: BlockFilter, period):
    joins, where_sql, params = flt.sql()
    clauses = [where_sql.removeprefix("WHERE ")] if where_sql else []
    clauses.append("tc.period = :p")
    return db.execute(text(_SELECT.format(joins=joins, where=" AND ".join(clauses))), {**params, "p": period}).mappings()


def list_rows(db: Session, bulan: int, tahun: int, blok: str | None) -> dict:
    period = to_period(bulan, tahun)
    data = [
        {
            "id": r["id"], "blok_id": r["block_id"], "kode_blok": r["kode_blok"], "objectid": r["objectid"],
            "diameter": r["diameter"], "jarak": r["spacing"], "kategori": r["kategori"],
            "geometry": json.loads(r["geometry_json"]) if r["geometry_json"] else None,
        }
        for r in _query(db, BlockFilter(blok=blok), period)
    ]
    return {"status": "success", "total_records": len(data), "periode": period_label(period), "data": data}


def _block_ids(db: Session, flt: BlockFilter) -> list[int]:
    """Blok yang lolos filter wilayah. Kecil (puluhan–ratusan), dipakai menyaring sensus."""
    joins, where_sql, params = flt.sql()
    return list(db.execute(
        text(f"SELECT DISTINCT bl.id FROM master.blocks bl {joins} {where_sql}"),
        params,
    ).scalars().all())


# FeatureCollection dirakit di Postgres. Indeks tree_censuses (block_id, period)
# dipakai lewat join dari daftar blok, bukan dari seluruh tabel sensus.
_GEOJSON_SQL = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(json_build_object(
            'type', 'Feature',
            'properties', json_build_object(
                'id', pt.id,
                'objectid', pt.objectid,
                'blok_id', tc.block_id,
                'kode_blok', bl.code,
                'kode_afd', dv.code,
                'kode_est', es.code,
                'diameter', tc.diameter,
                'jarak', tc.spacing,
                'kategori', cat.name,
                'bulan', :bulan,
                'tahun', :tahun
            ),
            'geometry', ST_AsGeoJSON(pt.geom)::json
        )), '[]'::json)
    )
    FROM unnest(CAST(:ids AS bigint[])) AS scope(block_id)
    JOIN spatial.tree_censuses tc ON tc.block_id = scope.block_id AND tc.period = :p
    JOIN spatial.palm_trees pt ON pt.id = tc.palm_tree_id
    JOIN master.blocks bl ON bl.id = tc.block_id
    JOIN master.divisions dv ON dv.id = bl.division_id
    JOIN master.estates es ON es.id = dv.estate_id
    LEFT JOIN ref.tree_categories cat ON cat.id = tc.category_id
"""


def geojson(db: Session, flt: BlockFilter, bulan: int | None, tahun: int | None):
    period = resolve_period(db, TABLE, bulan, tahun)
    if period is None:
        return feature_collection([])
    block_ids = _block_ids(db, flt)
    if not block_ids:
        return feature_collection([])

    payload = db.execute(text(_GEOJSON_SQL), {
        "p": period, "ids": block_ids, "bulan": period.month, "tahun": period.year,
    }).scalar_one()
    if isinstance(payload, memoryview):
        payload = payload.tobytes().decode()
    elif isinstance(payload, bytes):
        payload = payload.decode()
    elif not isinstance(payload, str):
        payload = json.dumps(payload, default=json_safe, separators=(",", ":"))
    return Response(content=payload, media_type="application/json")


def cleanup(db: Session, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    deleted = db.execute(text(f"DELETE FROM {TABLE} WHERE period = :p"), {"p": period}).rowcount
    db.commit()
    return {"jenis": "sawit", "periode": period_label(period), "data_terhapus": deleted}
