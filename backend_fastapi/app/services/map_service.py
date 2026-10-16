"""
GeoJSON untuk peta: batas blok (+ ringkasan transaksi) dan titik TPH.

Semantik periode batas blok = "kondisi per periode": untuk tiap blok diambil
batas TERBARU dengan period <= periode yang diminta (tanpa parameter = terbaru).

`produksi_tbs` memakai rentang transaksi (`TrxWindow`) dari bulan/tahun + `year_to_date`:
- year_to_date + bulan  -> Januari s/d bulan itu
- year_to_date tanpa bulan -> Januari s/d bulan berjalan (tahun lalu: s/d Desember)
- bukan year_to_date + bulan -> bulan itu saja
- bukan year_to_date tanpa bulan -> bulan produksi terakhir yang diupload di tahun itu (blok yang difilter)
Tanpa tahun: acuannya bulan produksi terakhir yang ada. `areal_statement` (dan luas untuk yield)
= statement terbaru di tahun yang sama s/d akhir rentang. `produksi_tbs_comparison` memakai aturan
yang sama untuk bulan/tahun pembanding. Blok tanpa statement maupun produksi di rentang itu tidak
punya key-nya. Yield dan kategori gap memakai rumus yang sama dengan detail blok.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_detail_service import _yield_ton_ha, gap_kategori, gap_value
from app.services.block_filter import BlockFilter, statement_as_of_join
from app.services.hierarchy_service import BLOCK_ATTRIBUTE_COLUMNS
from app.utils.geojson import feature_collection, make_feature
from app.utils.parsing import json_safe, num, whole
from app.utils.period import as_of_period, period_label, period_parts, to_period


def resolve_period(db: Session, table_sql: str, bulan: int | None, tahun: int | None) -> date | None:
    """Periode eksak kalau bulan+tahun diisi; selain itu periode terbaru di tabel (dalam tahun itu bila diisi)."""
    if bulan and tahun:
        return to_period(bulan, tahun)
    where = "WHERE extract(year FROM period) = :tahun" if tahun else ""
    return db.execute(text(f"SELECT max(period) FROM {table_sql} {where}"), {"tahun": tahun}).scalar()


def _money(value) -> float:
    return round(num(value), 2)


def _optional_money(value) -> float:
    return _money(value) if value is not None else 0.0


def _statement_payload(period: date, row) -> dict:
    return {
        "luas_tanam": _optional_money(row["planted_area_ha"] if row else None),
        "luas_tanah": _optional_money(row["land_area_ha"] if row else None),
        "total_pokok": whole(row["tree_count"]) if row and row["tree_count"] is not None else 0,
        "sph": _optional_money(row["sph"] if row else None),
        "periode": period_label(period),
    }


@dataclass(frozen=True)
class TrxWindow:
    """Rentang periode transaksi (bulan pertama s/d bulan terakhir, inklusif)."""

    start: date
    end: date
    year_to_date: bool

    @classmethod
    def of(cls, end: date, year_to_date: bool) -> "TrxWindow":
        return cls(date(end.year, 1, 1) if year_to_date else end, end, year_to_date)


def resolve_trx_window(db: Session, block_ids: list[int], bulan: int | None, tahun: int | None,
                       year_to_date: bool) -> TrxWindow | None:
    if bulan and tahun:
        return TrxWindow.of(to_period(bulan, tahun), year_to_date)
    if tahun and year_to_date:
        today = date.today()
        return TrxWindow.of(to_period(today.month if tahun == today.year else 12, tahun), True)
    year_filter = "AND extract(year FROM period) = :tahun" if tahun else ""
    latest = db.execute(text(f"""
        SELECT max(period) FROM trx.block_productions WHERE block_id = ANY(:ids) {year_filter}
    """), {"ids": block_ids, "tahun": tahun}).scalar()
    return TrxWindow.of(latest, year_to_date) if latest else None


def _produksi_payload(period: date, luas: float, row, window: TrxWindow | None = None) -> dict:
    """Yield dan gap sama dengan detail blok: ton/ha dibulatkan dulu, lalu variansnya."""
    tbs_aktual = _money(row["ffb_actual_kg"]) if row else 0.0
    tbs_budget = _money(row["ffb_budget_kg"]) if row else 0.0
    tbs_sensus = _money(row["ffb_census_kg"]) if row else 0.0
    y_aktual = _yield_ton_ha(tbs_aktual, luas)
    y_budget = _yield_ton_ha(tbs_budget, luas)
    y_sensus = _yield_ton_ha(tbs_sensus, luas)
    gap_budget = gap_value(y_aktual, y_budget)
    gap_sensus = gap_value(y_aktual, y_sensus)
    return {
        "tbs_aktual": tbs_aktual,
        "tbs_budget": tbs_budget,
        "tbs_sensus": tbs_sensus,
        "janjang_aktual": whole(row["bunches_actual"]) if row else 0,
        "bjr_aktual": _money(row["bjr_actual"]) if row else 0.0,
        "luas_tanam": luas,
        "y_aktual": y_aktual,
        "y_budget": y_budget,
        "y_sensus": y_sensus,
        "gap_budget_pct": gap_budget,
        "gap_sensus_pct": gap_sensus,
        "kategori_budget": gap_kategori(gap_budget) or None,
        "kategori_sensus": gap_kategori(gap_sensus) or None,
        "periode": period_label(period),
        **({"periode_awal": period_label(window.start), "periode_akhir": period_label(window.end),
            "year_to_date": window.year_to_date} if window else {}),
    }


def _window_summaries(db: Session, block_ids: list[int], window: TrxWindow) -> dict[int, tuple]:
    """id blok -> (statement | None, produksi | None) untuk satu rentang; blok tanpa keduanya tidak ada."""
    rows = db.execute(text("""
        WITH statements AS (
            SELECT DISTINCT ON (a.block_id)
                   a.block_id, a.period, a.planted_area_ha, a.land_area_ha, a.tree_count, a.sph
            FROM trx.area_statements a
            WHERE a.block_id = ANY(:ids) AND a.period BETWEEN :year_start AND :end
            ORDER BY a.block_id, a.period DESC
        ),
        productions AS (
            SELECT p.block_id,
                   SUM(p.ffb_actual_kg) AS ffb_actual_kg,
                   SUM(p.ffb_budget_kg) AS ffb_budget_kg,
                   SUM(p.ffb_census_kg) AS ffb_census_kg,
                   SUM(p.bunches_actual) AS bunches_actual,
                   AVG(p.bjr_actual) AS bjr_actual
            FROM trx.block_productions p
            WHERE p.block_id = ANY(:ids) AND p.period BETWEEN :start AND :end
            GROUP BY p.block_id
        )
        SELECT COALESCE(s.block_id, pr.block_id) AS block_id, s.period AS statement_period,
               s.planted_area_ha, s.land_area_ha, s.tree_count, s.sph, (s.block_id IS NOT NULL) AS has_statement,
               pr.ffb_actual_kg, pr.ffb_budget_kg, pr.ffb_census_kg, pr.bunches_actual, pr.bjr_actual,
               (pr.block_id IS NOT NULL) AS has_production
        FROM statements s FULL JOIN productions pr ON pr.block_id = s.block_id
    """), {"ids": block_ids, "year_start": date(window.end.year, 1, 1), "start": window.start,
           "end": window.end}).mappings()
    return {r["block_id"]: (r if r["has_statement"] else None, r if r["has_production"] else None) for r in rows}


def _trx_summaries(
    db: Session,
    block_ids: list[int],
    window: TrxWindow | None,
    comparison: TrxWindow | None = None,
) -> dict[int, dict]:
    if not block_ids:
        return {}
    summary: dict[int, dict] = {bid: {} for bid in block_ids}

    if window:
        for block_id, (statement, production) in _window_summaries(db, block_ids, window).items():
            luas = _optional_money(statement["planted_area_ha"]) if statement else 0.0
            statement_period = statement["statement_period"] if statement else window.end
            summary[block_id]["areal_statement"] = _statement_payload(statement_period, statement)
            summary[block_id]["produksi_tbs"] = _produksi_payload(window.end, luas, production, window)
    if comparison:
        for block_id, (statement, production) in _window_summaries(db, block_ids, comparison).items():
            luas = _optional_money(statement["planted_area_ha"]) if statement else 0.0
            summary[block_id]["produksi_tbs_comparison"] = _produksi_payload(
                comparison.end, luas, production, comparison)

    as_of = window.end if window else None
    period_filter = "AND h.period <= :as_of" if as_of else ""
    for r in db.execute(text(f"""
        SELECT DISTINCT ON (h.block_id) h.block_id, h.period, h.rotation_no, h.interval_days, rs.name AS status
        FROM trx.harvest_rotations h LEFT JOIN ref.rotation_statuses rs ON rs.id = h.rotation_status_id
        WHERE h.block_id = ANY(:ids) {period_filter}
        ORDER BY h.block_id, h.period DESC
    """), {"ids": block_ids, "as_of": as_of}).mappings():
        summary[r["block_id"]]["rotasi_terakhir"] = {
            "rotasi_ke": json_safe(r["rotation_no"]), "pusingan_hari": r["interval_days"],
            "status_pusingan": r["status"], "tanggal": json_safe(r["period"]),
        }
    return summary


_LATEST_SOURCES = (
    ("produksi_tbs", "trx.block_productions"),
    ("areal_statement", "trx.area_statements"),
    ("rotasi_pusingan", "trx.harvest_rotations"),
    ("batas_blok", "spatial.block_boundaries"),
)
# Sumber periode default: produksi dulu (dipakai warna peta), lalu areal statement, lalu batas blok.
_DEFAULT_PRIORITY = ("produksi_tbs", "areal_statement", "batas_blok")


def _period_info(period: date | None) -> dict | None:
    return {"bulan": period.month, "tahun": period.year, "periode": period_label(period)} if period else None


def latest_periods(db: Session, flt: BlockFilter) -> dict:
    """Periode terakhir yang sudah diupload untuk blok dalam filter: default filter Periode di FE."""
    blocks_sql, params = flt.block_ids_subquery()
    selects = ", ".join(f"(SELECT max(period) FROM {table} WHERE block_id IN (SELECT id FROM b)) AS {key}"
                        for key, table in _LATEST_SOURCES)
    row = db.execute(text(f"WITH b AS ({blocks_sql}) SELECT {selects}"), params).mappings().one()
    source = next((key for key in _DEFAULT_PRIORITY if row[key]), None)
    default = row[source] if source else None
    return {
        **(_period_info(default) or {"bulan": None, "tahun": None, "periode": None}),
        "sumber": source,
        "per_data": {key: _period_info(row[key]) for key, _ in _LATEST_SOURCES},
    }


def blocks_geojson(
    db: Session,
    flt: BlockFilter,
    bulan: int | None,
    tahun: int | None,
    *,
    year_to_date: bool = False,
    comparison: tuple[int, int] | None = None,
    hide_keys: tuple[str, ...] = (),
):
    """`comparison` = (bulan, tahun) pembanding -> properti `produksi_tbs_comparison`."""
    as_of = as_of_period(bulan, tahun)
    joins, where_sql, params = flt.sql()
    params["as_of"] = as_of
    period_filter = "AND bb.period <= :as_of" if as_of else ""
    rows = db.execute(text(f"""
        SELECT {BLOCK_ATTRIBUTE_COLUMNS}, b.period AS boundary_period, b.geom_json
        FROM master.blocks bl {joins}
        JOIN LATERAL (
            SELECT bb.period, ST_AsGeoJSON(bb.geom, 6) AS geom_json
            FROM spatial.block_boundaries bb
            WHERE bb.block_id = bl.id {period_filter}
            ORDER BY bb.period DESC LIMIT 1
        ) b ON true
        {statement_as_of_join("as_of" if as_of else None)}
        {where_sql}
        ORDER BY bl.id
    """), params).mappings().all()

    block_ids = [r["id"] for r in rows]
    window = resolve_trx_window(db, block_ids, bulan, tahun, year_to_date) if block_ids else None
    comparison_window = TrxWindow.of(to_period(*comparison), year_to_date) if comparison else None
    summaries = _trx_summaries(db, block_ids, window, comparison_window)
    features = []
    for r in rows:
        boundary_bulan, boundary_tahun = period_parts(r["boundary_period"])
        properties = {
            "blok_id": r["id"], "nama_blok": f"Blok {r['code']}", "kode_blok": r["code"],
            "afd_id": r["division_id"], "kode_afd": r["division_code"],
            "kode_est": r["estate_code"], "nama_estate": r["estate_name"],
            "kode_pt": r["company_code"], "nama_pt": r["company_name"], "kode_area": r["area_code"],
            "kode_grup": r["group_code"],
            "tipe_blok": r["block_type"], "tahun_tanam": r["planting_year"], "jenis_bibit": r["seed_varieties"],
            "status_tanam": r["planting_status"],
            # Periode batas (poligon). Periode transaksi ada di masing-masing objek (lihat TrxWindow).
            # `bulan`/`tahun` dipertahankan untuk FE lama.
            "periode_batas": period_label(r["boundary_period"]), "bulan": boundary_bulan, "tahun": boundary_tahun,
            **{k: v for k, v in summaries.get(r["id"], {}).items() if k not in hide_keys},
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
               es.code AS estate_code, ST_AsGeoJSON(t.geom, 6) AS geom_json
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
