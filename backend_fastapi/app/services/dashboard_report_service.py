"""Laporan dashboard: empat kueri terpisah, masing-masing sesuai tema kartunya.

Hak akses:
- superadmin melihat seluruh blok dan seluruh tema;
- role lain hanya blok pada scope data role, dan tema yang transaksi-nya tidak diberikan dikosongkan.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_filter import BlockFilter
from app.services.user_access import apply_data_scope, is_superadmin, transaction_granted
from app.utils.parsing import num

_RECENT = 6
_STATUS_ORDER = ("TM", "TBM", "LC")
_STATUS_LABEL = {
    "TM": "Tanaman Menghasilkan",
    "TBM": "Tanaman Belum Menghasilkan",
    "LC": "Pembukaan Lahan",
}


def _closed(tema: str) -> dict:
    return {"tema": tema, "akses": False}


def _periods(rows) -> list[dict]:
    ordered = sorted(rows, key=lambda row: (int(row["tahun"]), int(row["bulan"] or 0)))
    return ordered[-_RECENT:]


def _production(db: Session, blocks_sql: str, params: dict) -> dict:
    rows = db.execute(text(f"""
        SELECT extract(year FROM p.period)::int AS tahun,
               extract(month FROM p.period)::int AS bulan,
               SUM(p.ffb_actual_kg) / 1000.0 AS ton
        FROM trx.block_productions p
        WHERE p.block_id IN ({blocks_sql}) AND p.period IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2 DESC
        LIMIT {_RECENT}
    """), params).mappings().all()
    periode = _periods(rows)
    series = [
        {"tahun": int(row["tahun"]), "bulan": int(row["bulan"]), "ton": round(num(row["ton"]), 2)}
        for row in periode
    ]
    return {
        "tema": "produksi_tbs",
        "akses": True,
        "total_ton": series[-1]["ton"] if series else None,
        "periode": series,
    }


def _yield(db: Session, blocks_sql: str, params: dict) -> dict:
    rows = db.execute(text(f"""
        SELECT extract(year FROM p.period)::int AS tahun,
               extract(month FROM p.period)::int AS bulan,
               SUM(p.ffb_actual_kg) / 1000.0 / NULLIF(SUM(a.planted_area_ha), 0) AS ton_ha
        FROM trx.block_productions p
        LEFT JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
        WHERE p.block_id IN ({blocks_sql}) AND p.period IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2 DESC
        LIMIT {_RECENT}
    """), params).mappings().all()
    periode = _periods(rows)
    series = [
        {
            "tahun": int(row["tahun"]),
            "bulan": int(row["bulan"]),
            "ton_ha": round(num(row["ton_ha"]), 2) if row["ton_ha"] is not None else None,
        }
        for row in periode
    ]
    latest = next((row["ton_ha"] for row in reversed(series) if row["ton_ha"] is not None), None)
    return {"tema": "yield", "akses": True, "ton_ha": latest, "periode": series}


def _planting_status(db: Session, blocks_sql: str, params: dict) -> dict:
    rows = db.execute(text(f"""
        WITH scoped AS (
            SELECT a.period, a.block_id, a.planting_status_id, a.planted_area_ha
            FROM trx.area_statements a
            WHERE a.block_id IN ({blocks_sql})
        ),
        snap AS (
            SELECT * FROM scoped WHERE period = (SELECT max(period) FROM scoped)
        )
        SELECT upper(ps.code) AS status, COUNT(*)::int AS jumlah_blok,
               SUM(s.planted_area_ha) AS luas, max(s.period) AS period
        FROM snap s
        LEFT JOIN ref.planting_statuses ps ON ps.id = s.planting_status_id
        GROUP BY 1
    """), params).mappings().all()
    planted = sum(num(row["luas"]) for row in rows)
    period = next((row["period"] for row in rows if row["period"] is not None), None)

    def sort_key(row):
        status = row["status"] or "TANPA_STATUS"
        order = _STATUS_ORDER.index(status) if status in _STATUS_ORDER else len(_STATUS_ORDER)
        return (order, status)

    per_status = []
    for row in sorted(rows, key=sort_key):
        status = row["status"] or "TANPA_STATUS"
        luas = num(row["luas"])
        per_status.append({
            "status": status,
            "label": _STATUS_LABEL.get(status, status),
            "jumlah_blok": int(row["jumlah_blok"] or 0),
            "luas_tanam": round(luas, 2),
            "persen": round(luas / planted * 100, 2) if planted else 0.0,
        })
    utama = max(per_status, key=lambda item: item["luas_tanam"]) if per_status else None
    return {
        "tema": "status_tanam",
        "akses": True,
        "bulan": period.month if period else None,
        "tahun": period.year if period else None,
        "total_luas_tanam": round(planted, 2),
        "utama": utama,
        "per_status": per_status,
    }


def _rotation(db: Session, blocks_sql: str, params: dict) -> dict:
    rows = db.execute(text(f"""
        SELECT extract(year FROM h.period)::int AS tahun,
               extract(month FROM h.period)::int AS bulan,
               ROUND(AVG(h.interval_days), 2) AS avg_pusingan_hari
        FROM trx.harvest_rotations h
        WHERE h.block_id IN ({blocks_sql}) AND h.period IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2 DESC
        LIMIT {_RECENT}
    """), params).mappings().all()
    periode = _periods(rows)
    series = [
        {
            "tahun": int(row["tahun"]),
            "bulan": int(row["bulan"]),
            "avg_pusingan_hari": round(num(row["avg_pusingan_hari"]), 2),
        }
        for row in periode
    ]
    latest = series[-1]["avg_pusingan_hari"] if series else None
    return {"tema": "rotasi", "akses": True, "avg_pusingan_hari": latest, "periode": series}


def dashboard_report(db: Session, user) -> dict:
    """Satu respons untuk keempat kartu. Tema tanpa hak transaksi tidak dihitung."""
    flt = apply_data_scope(db, user, BlockFilter())
    blocks_sql, params = flt.block_ids_subquery()
    can_production = transaction_granted(db, user, "trx.block_productions", "trx_produksi_tbs")
    can_area = transaction_granted(db, user, "trx.area_statements", "trx_areal_statement")
    can_rotation = transaction_granted(db, user, "trx.harvest_rotations", "trx_rotasi_pusingan")
    return {
        "cakupan": "semua" if is_superadmin(user) else "terbatas",
        "produksi_tbs": _production(db, blocks_sql, params) if can_production else _closed("produksi_tbs"),
        "yield": _yield(db, blocks_sql, params) if can_production else _closed("yield"),
        "status_tanam": _planting_status(db, blocks_sql, params) if can_area else _closed("status_tanam"),
        "rotasi": _rotation(db, blocks_sql, params) if can_rotation else _closed("rotasi"),
    }
