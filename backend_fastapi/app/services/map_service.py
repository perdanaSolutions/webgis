"""
GeoJSON untuk peta: batas blok (+ ringkasan transaksi) dan titik TPH.

Semantik periode batas blok = "kondisi per periode": untuk tiap blok diambil
batas TERBARU dengan period <= periode yang diminta (tanpa parameter = terbaru).
Ringkasan trx memakai aturan yang sama per tabel, karena data trx dan batas
blok tidak selalu punya bulan yang sama.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_filter import BlockFilter, statement_as_of_join
from app.services.hierarchy_service import BLOCK_ATTRIBUTE_COLUMNS
from app.services.history_service import gap_category, gap_pct
from app.utils.geojson import feature_collection, make_feature
from app.utils.parsing import json_safe
from app.utils.period import period_label, period_parts, to_period


def resolve_period(db: Session, table_sql: str, bulan: int | None, tahun: int | None) -> date | None:
    """Periode eksak kalau bulan+tahun diisi; selain itu periode terbaru di tabel (dalam tahun itu bila diisi)."""
    if bulan and tahun:
        return to_period(bulan, tahun)
    where = "WHERE extract(year FROM period) = :tahun" if tahun else ""
    return db.execute(text(f"SELECT max(period) FROM {table_sql} {where}"), {"tahun": tahun}).scalar()


def _trx_summaries(db: Session, block_ids: list[int], as_of: date | None) -> dict[int, dict]:
    if not block_ids:
        return {}
    params = {"ids": block_ids, "as_of": as_of}
    period_filter = "AND period <= :as_of" if as_of else ""
    summary: dict[int, dict] = {bid: {} for bid in block_ids}

    for r in db.execute(text(f"""
        SELECT DISTINCT ON (block_id) block_id, period, planted_area_ha, land_area_ha, tree_count, sph
        FROM trx.area_statements WHERE block_id = ANY(:ids) {period_filter}
        ORDER BY block_id, period DESC
    """), params).mappings():
        summary[r["block_id"]]["areal_statement"] = {
            "luas_tanam": json_safe(r["planted_area_ha"]), "luas_tanah": json_safe(r["land_area_ha"]),
            "total_pokok": json_safe(r["tree_count"]), "sph": json_safe(r["sph"]), "periode": period_label(r["period"]),
        }

    for r in db.execute(text(f"""
        SELECT DISTINCT ON (p.block_id) p.block_id, p.period, p.ffb_actual_kg, p.ffb_budget_kg, p.ffb_census_kg,
               p.bunches_actual, p.bjr_actual, st.planted_area_ha
        FROM trx.block_productions p
        LEFT JOIN LATERAL (
            SELECT a.planted_area_ha FROM trx.area_statements a
            WHERE a.block_id = p.block_id AND a.period <= p.period ORDER BY a.period DESC LIMIT 1
        ) st ON true
        WHERE p.block_id = ANY(:ids) {period_filter.replace('period', 'p.period')}
        ORDER BY p.block_id, p.period DESC
    """), params).mappings():
        # Yield (ton/ha) & varians dihitung dari data DB, bukan dari kolom turunan di Excel.
        luas = float(r["planted_area_ha"] or 0)

        def yield_ha(kg):
            return float(kg) / 1000 / luas if luas and kg is not None else None

        y_act, y_bgt, y_sns = yield_ha(r["ffb_actual_kg"]), yield_ha(r["ffb_budget_kg"]), yield_ha(r["ffb_census_kg"])
        gap_bgt, gap_sns = gap_pct(y_act, y_bgt), gap_pct(y_act, y_sns)

        def rnd(v):
            return round(v, 2) if v is not None else None

        summary[r["block_id"]]["produksi_tbs"] = {
            "tbs_aktual": json_safe(r["ffb_actual_kg"]), "tbs_budget": json_safe(r["ffb_budget_kg"]),
            "tbs_sensus": json_safe(r["ffb_census_kg"]),
            "janjang_aktual": r["bunches_actual"], "bjr_aktual": json_safe(r["bjr_actual"]),
            "luas_tanam": json_safe(r["planted_area_ha"]),
            "y_aktual": rnd(y_act), "y_budget": rnd(y_bgt), "y_sensus": rnd(y_sns),
            "gap_budget_pct": rnd(gap_bgt), "gap_sensus_pct": rnd(gap_sns),
            "kategori_budget": gap_category(gap_bgt), "kategori_sensus": gap_category(gap_sns),
            "periode": period_label(r["period"]),
        }

    for r in db.execute(text(f"""
        SELECT DISTINCT ON (h.block_id) h.block_id, h.period, h.rotation_no, h.interval_days, rs.name AS status
        FROM trx.harvest_rotations h LEFT JOIN ref.rotation_statuses rs ON rs.id = h.rotation_status_id
        WHERE h.block_id = ANY(:ids) {period_filter.replace('period', 'h.period')}
        ORDER BY h.block_id, h.period DESC
    """), params).mappings():
        summary[r["block_id"]]["rotasi_terakhir"] = {
            "rotasi_ke": json_safe(r["rotation_no"]), "pusingan_hari": r["interval_days"],
            "status_pusingan": r["status"], "tanggal": json_safe(r["period"]),
        }
    return summary


def blocks_geojson(db: Session, flt: BlockFilter, as_of: date | None):
    joins, where_sql, params = flt.sql()
    params["as_of"] = as_of
    period_filter = "AND bb.period <= :as_of" if as_of else ""
    rows = db.execute(text(f"""
        SELECT {BLOCK_ATTRIBUTE_COLUMNS}, b.period AS boundary_period, b.geom_json
        FROM master.blocks bl {joins}
        JOIN LATERAL (
            SELECT bb.period, ST_AsGeoJSON(bb.geom) AS geom_json
            FROM spatial.block_boundaries bb
            WHERE bb.block_id = bl.id {period_filter}
            ORDER BY bb.period DESC LIMIT 1
        ) b ON true
        {statement_as_of_join("as_of" if as_of else None)}
        {where_sql}
        ORDER BY bl.id
    """), params).mappings().all()

    summaries = _trx_summaries(db, [r["id"] for r in rows], as_of)
    features = []
    for r in rows:
        bulan, tahun = period_parts(r["boundary_period"])
        properties = {
            "blok_id": r["id"], "nama_blok": f"Blok {r['code']}", "kode_blok": r["code"],
            "afd_id": r["division_id"], "kode_afd": r["division_code"],
            "kode_est": r["estate_code"], "nama_estate": r["estate_name"],
            "kode_pt": r["company_code"], "nama_pt": r["company_name"], "kode_area": r["area_code"],
            "tipe_blok": r["block_type"], "tahun_tanam": r["planting_year"], "jenis_bibit": r["seed_varieties"],
            "status_tanam": r["planting_status"], "bulan": bulan, "tahun": tahun,
            **summaries.get(r["id"], {}),
        }
        feature = make_feature(properties, r["geom_json"])
        if feature:
            features.append(feature)
    return feature_collection(features)


def tph_geojson(db: Session, flt: BlockFilter, kategori: str | None, bulan: int | None, tahun: int | None):
    period = resolve_period(db, "spatial.tph_points", bulan, tahun)
    if period is None:
        return feature_collection([])

    joins, where_sql, params = flt.sql()
    clauses = [where_sql.removeprefix("WHERE ")] if where_sql else []
    clauses.append("t.period = :period")
    params["period"] = period
    if kategori and kategori.strip():
        clauses.append("lower(cat.name) = lower(:kategori)")
        params["kategori"] = kategori.strip()

    rows = db.execute(text(f"""
        SELECT t.id, t.period, cat.name AS kategori, bl.id AS block_id, bl.code, dv.id AS division_id, dv.code AS division_code,
               es.code AS estate_code, ST_AsGeoJSON(t.geom) AS geom_json
        FROM spatial.tph_points t
        JOIN master.blocks bl ON bl.id = t.block_id {joins}
        LEFT JOIN ref.tph_categories cat ON cat.id = t.category_id
        WHERE {' AND '.join(clauses)}
        ORDER BY t.id
    """), params).mappings()

    features = []
    for r in rows:
        feature = make_feature({
            "tph_id": r["id"], "blok_id": r["block_id"], "nama_blok": f"Blok {r['code']}", "kode_blok": r["code"],
            "afd_id": r["division_id"], "kode_afd": r["division_code"], "kode_est": r["estate_code"],
            "kategori": r["kategori"], "bulan": r["period"].month, "tahun": r["period"].year,
        }, r["geom_json"])
        if feature:
            features.append(feature)
    return feature_collection(features)
