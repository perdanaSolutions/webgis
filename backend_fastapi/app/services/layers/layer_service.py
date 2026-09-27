"""
Upload (analisis & eksekusi), daftar, GeoJSON, dan cleanup untuk layer bawaan
yang dideskripsikan `LayerSpec` (slope, landuse, jalan, jembatan, tph).

Aturan upload per periode:
- Blok induk dicari dari properti EstID/Estate + Afdeling + Blok di master; kalau
  labelnya tidak cocok, blok dicari dari posisi geometri terhadap batas blok
  (estate yang sama) dan koreksinya dilaporkan di `koreksi_label_blok`.
- Data lama periode itu untuk blok-blok di file (dan objectid yang sama)
  dihapus lalu diganti isi file -- upload ulang file yang sama idempoten,
  dan upload estate lain di periode yang sama tidak saling menghapus.
- Semua langkah tulis berjalan dalam SATU transaksi: gagal = tidak ada yang berubah.
"""
import json
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_filter import BlockFilter
from app.services.layers.specs import Column, LayerSpec
from app.services.map_service import resolve_period
from app.services.upload.batch import final_status, finish_batch, start_batch
from app.services.upload.copy import copy_rows
from app.services.upload.resolvers import BlockIndex, BlockMatchReport, RefResolver, geojson_block_keys, match_blocks
from app.utils.geojson import feature_collection, geometry_to_ewkb, make_feature, parse_features
from app.utils.parsing import clean_str, json_safe, to_float, to_int
from app.utils.period import period_label, to_period
from app.utils.sql import quote_table


@dataclass
class PreparedUpload:
    total: int = 0
    rows: list[dict] = field(default_factory=list)
    invalid_props: int = 0
    invalid_geom: int = 0
    duplicates: int = 0
    match: BlockMatchReport = field(default_factory=BlockMatchReport)
    new_refs: dict[str, list[str]] = field(default_factory=dict)

    @property
    def missing_block(self) -> int:
        return self.match.missing

    @property
    def block_ids(self) -> list[int]:
        return sorted({r["block_id"] for r in self.rows})

    @property
    def objectids(self) -> list[int]:
        return sorted({r["objectid"] for r in self.rows if r.get("objectid") is not None})

    def stats(self, success: int, replaced: int = 0) -> dict:
        return {
            "sukses_terunggah": success,
            "tertahan_blok_missing": self.missing_block,
            "properti_invalid": self.invalid_props,
            "geometri_invalid": self.invalid_geom,
            "duplikat_dalam_file": self.duplicates,
            "data_lama_diganti": replaced,
            **self.match.as_dict(),
            "nilai_referensi_baru": self.new_refs,
            "sistem_error": 0,
        }


def _cast(column: Column, value, refs: dict[str, RefResolver]):
    if column.kind == "int":
        return to_int(value)
    if column.kind == "float":
        return to_float(value)
    if column.kind.startswith("ref:"):
        return refs[column.kind[4:]].resolve(value)
    text_value = clean_str(value)
    return text_value[:100] if text_value else None


def prepare_features(db: Session, spec: LayerSpec, content: bytes, create_refs: bool) -> PreparedUpload:
    features = parse_features(content)
    refs = {c.kind[4:]: RefResolver(db, c.kind[4:], create_missing=create_refs)
            for c in spec.columns if c.kind.startswith("ref:")}
    result = PreparedUpload(total=len(features))

    # 1) validasi properti & geometri
    candidates: list[tuple[tuple, dict]] = []
    for feature in features:
        props = feature.get("properties") or {}
        keys = geojson_block_keys(props)
        if keys is None:
            result.invalid_props += 1
            continue
        geom = geometry_to_ewkb(feature.get("geometry"), spec.geometry_type)
        if geom is None:
            result.invalid_geom += 1
            continue
        row = {"geom": geom}
        valid = True
        for column in spec.columns:
            raw = next((props.get(p) for p in column.props if props.get(p) is not None), None)
            value = _cast(column, raw, refs)
            if column.non_negative and value is not None and value < 0:
                valid = False
            row[column.column] = value
        if not valid:
            result.invalid_props += 1
            continue
        candidates.append((keys, row))

    # 2) tentukan blok (label -> master, cadangan: posisi geometri)
    block_ids, result.match = match_blocks(db, BlockIndex.load(db), [(k, r["geom"]) for k, r in candidates])

    # 3) buang yang tanpa blok, dedup objectid (baris terakhir menang)
    by_objectid: dict[int, dict] = {}
    for (_, row), block_id in zip(candidates, block_ids):
        if block_id is None:
            continue
        row["block_id"] = block_id
        objectid = row.get("objectid")
        if spec.unique_objectid and objectid is not None:
            result.duplicates += objectid in by_objectid
            by_objectid[objectid] = row
        else:
            result.rows.append(row)

    result.rows.extend(by_objectid.values())
    result.new_refs = {name: r.created for name, r in refs.items() if r.created}
    return result


def _existing_filter(spec: LayerSpec, prepared: PreparedUpload) -> tuple[str, dict]:
    clauses = ["block_id = ANY(:blocks)"]
    params = {"blocks": prepared.block_ids}
    if spec.unique_objectid:
        clauses.append("objectid = ANY(:oids)")
        params["oids"] = prepared.objectids
    return "(" + " OR ".join(clauses) + ")", params


def analyze(db: Session, spec: LayerSpec, content: bytes, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    prepared = prepare_features(db, spec, content, create_refs=False)
    condition, params = _existing_filter(spec, prepared)
    will_replace = db.execute(
        text(f"SELECT count(*) FROM {quote_table(spec.table)} WHERE period = :p AND {condition}"),
        {**params, "p": period},
    ).scalar_one() if prepared.rows else 0
    code = spec.code
    return {
        "tipe_upload": spec.tipe_upload,
        "periode": period_label(period),
        f"total_fitur_{code}": prepared.total,
        f"{code}_siap_diunggah": len(prepared.rows),
        f"{code}_tertahan_karena_blok_belum_ada": prepared.missing_block,
        "data_properti_invalid": prepared.invalid_props,
        "data_geometri_invalid": prepared.invalid_geom,
        "duplikat_objectid_dalam_file": prepared.duplicates,
        "data_periode_ini_akan_diganti": will_replace,
        **prepared.match.as_dict(),
        "contoh_blok_tidak_ditemukan": prepared.match.unmatched_samples,
    }


def execute(db: Session, spec: LayerSpec, content: bytes, filename: str | None, bulan: int, tahun: int,
            user_id: UUID | None) -> dict:
    period = to_period(bulan, tahun)
    batch_id = start_batch(db, source_type="GEOJSON_UPLOAD", target_table=spec.table, source_name=filename,
                           user_id=user_id, period=period, metadata={"layer": spec.code})
    try:
        prepared = prepare_features(db, spec, content, create_refs=True)
        replaced = 0
        if prepared.rows:
            condition, params = _existing_filter(spec, prepared)
            replaced = db.execute(
                text(f"DELETE FROM {quote_table(spec.table)} WHERE period = :p AND {condition}"), {**params, "p": period}
            ).rowcount
            columns = ["block_id", "period", *(c.column for c in spec.columns), "geom", "upload_batch_id"]
            copy_rows(db, quote_table(spec.table), columns, (
                [r["block_id"], period, *(r[c.column] for c in spec.columns), r["geom"], batch_id] for r in prepared.rows
            ))
        db.commit()
    except Exception as exc:
        db.rollback()
        finish_batch(db, batch_id, "FAILED", 0, str(exc)[:2000], {"layer": spec.code})
        raise

    success = len(prepared.rows)
    status = final_status(success, prepared.total)
    stats = prepared.stats(success, replaced)
    error = None if status == "SUCCESS" else (
        f"{prepared.total - success} dari {prepared.total} fitur tidak diunggah." if prepared.total else "File tidak berisi fitur.")
    finish_batch(db, batch_id, status, success, error, {"detail_statistik": stats})
    return {
        "batch_id": str(batch_id),
        f"total_fitur_{spec.code}_diproses": prepared.total,
        "status_proses": status,
        "detail_status": stats,
    }


def _select_columns(spec: LayerSpec) -> str:
    parts = []
    for c in spec.columns:
        if c.kind.startswith("ref:"):
            parts.append(f"(SELECT name FROM ref.{c.kind[4:]} r WHERE r.id = t.{c.column}) AS {c.output}")
        else:
            parts.append(f"t.{c.column} AS {c.output}")
    parts += [f"{expr} AS {name}" for name, expr in spec.derived]
    return ", ".join(parts)


def list_rows(db: Session, spec: LayerSpec, bulan: int, tahun: int, blok: str | None) -> dict:
    period = to_period(bulan, tahun)
    joins, where_sql, params = BlockFilter(blok=blok).sql()
    clauses = [where_sql.removeprefix("WHERE ")] if where_sql else []
    clauses.append("t.period = :p")
    rows = db.execute(text(f"""
        SELECT t.id, t.block_id, bl.code AS kode_blok, {_select_columns(spec)}, ST_AsGeoJSON(t.geom) AS geometry_json
        FROM {quote_table(spec.table)} t JOIN master.blocks bl ON bl.id = t.block_id {joins}
        WHERE {' AND '.join(clauses)}
        ORDER BY t.id
    """), {**params, "p": period}).mappings().all()

    data = [
        {
            "id": r["id"], "blok_id": r["block_id"], "kode_blok": r["kode_blok"],
            **{c.output: json_safe(r[c.output]) for c in spec.columns},
            **{name: json_safe(r[name]) for name, _ in spec.derived},
            "geometry": json.loads(r["geometry_json"]) if r["geometry_json"] else None,
        }
        for r in rows
    ]
    return {"status": "success", "total_records": len(data), "periode": period_label(period), "data": data}


def geojson(db: Session, spec: LayerSpec, flt: BlockFilter, bulan: int | None, tahun: int | None):
    period = resolve_period(db, quote_table(spec.table), bulan, tahun)
    if period is None:
        return feature_collection([])
    joins, where_sql, params = flt.sql()
    clauses = [where_sql.removeprefix("WHERE ")] if where_sql else []
    clauses.append("t.period = :p")
    rows = db.execute(text(f"""
        SELECT t.id, t.block_id, bl.code AS kode_blok, dv.code AS kode_afd, es.code AS kode_est,
               {_select_columns(spec)}, ST_AsGeoJSON(t.geom) AS geometry_json
        FROM {quote_table(spec.table)} t JOIN master.blocks bl ON bl.id = t.block_id {joins}
        WHERE {' AND '.join(clauses)}
        ORDER BY t.id
    """), {**params, "p": period}).mappings()

    features = []
    for r in rows:
        properties = {
            "id": r["id"], "blok_id": r["block_id"], "kode_blok": r["kode_blok"], "kode_afd": r["kode_afd"],
            "kode_est": r["kode_est"], **{c.output: r[c.output] for c in spec.columns},
            **{name: r[name] for name, _ in spec.derived},
            "bulan": period.month, "tahun": period.year,
        }
        if feature := make_feature(properties, r["geometry_json"]):
            features.append(feature)
    return feature_collection(features)


def cleanup(db: Session, spec: LayerSpec, bulan: int, tahun: int) -> dict:
    period = to_period(bulan, tahun)
    deleted = db.execute(text(f"DELETE FROM {quote_table(spec.table)} WHERE period = :p"), {"p": period}).rowcount
    db.commit()
    return {"jenis": spec.code, "periode": period_label(period), "data_terhapus": deleted}

