"""
Histori & agregasi transaksi per wilayah (area/PT/estate/afdeling/blok).

Nama tabel dari FE TIDAK pernah dipakai langsung di SQL -- harus cocok dengan
HISTORY_TABLES (whitelist). Nama lama v2 (trx_produksi_tbs, dst.) tetap
diterima supaya FE tidak berubah.

Karena area statement adalah snapshot bulanan, agregasi luas/pokok memakai
snapshot (bukan penjumlahan semua bulan seperti versi lama yang membuat
angka membengkak 12x).
"""
from collections import OrderedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.services.block_filter import SEED_VARIETIES_OF_STATEMENT, BlockFilter
from app.utils.parsing import MONTH_ABBR, num, whole

HISTORY_TABLES = OrderedDict([
    ("trx_produksi_tbs", {"label": "Produksi TBS", "table": "trx.block_productions"}),
    ("trx_areal_statement", {"label": "Pernyataan Areal (Areal Statement)", "table": "trx.area_statements"}),
    ("trx_rotasi_pusingan", {"label": "Rotasi Pusingan", "table": "trx.harvest_rotations"}),
])
_ALIASES = {cfg["table"]: key for key, cfg in HISTORY_TABLES.items()}


def list_history_tables() -> list[dict]:
    return [{"table": key, "label": cfg["label"], "physical_table": cfg["table"]} for key, cfg in HISTORY_TABLES.items()]


def _ha(value) -> str:
    """1234.5 -> '1.234,50 ha' (format angka Indonesia)."""
    formatted = f"{num(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{formatted} ha"


def resolve_history_table(table: str) -> tuple[str, str]:
    """(kunci lama, nama fisik schema.tabel)."""
    key = _ALIASES.get(table, table)
    if key not in HISTORY_TABLES:
        raise bad_request(f"Tabel '{table}' tidak valid. Pilihan: {list(HISTORY_TABLES)}", field="table")
    return key, HISTORY_TABLES[key]["table"]


def get_history(db: Session, table: str, tahun: int | None, flt: BlockFilter) -> dict:
    key, _physical = resolve_history_table(table)

    blocks_sql, params = flt.block_ids_subquery()
    filter_info = {
        "area_id": flt.area, "kode_pt": flt.kode_pt, "kode_est": flt.kode_est, "kode_afd": flt.kode_afd,
        "blok_id": flt.blok, "ownership": flt.ownership, "tahun_tanam": flt.tahun_tanam,
    }
    if key == "trx_produksi_tbs":
        return _production(db, blocks_sql, params, tahun, filter_info)
    if key == "trx_rotasi_pusingan":
        return _rotation(db, blocks_sql, params, tahun, filter_info)
    return _area_statement(db, blocks_sql, params, tahun, filter_info)


def _production(db: Session, blocks_sql: str, params: dict, tahun: int | None, filter_info: dict) -> dict:
    monthly = tahun is not None
    params = {**params, "tahun": tahun}
    year_filter = "AND extract(year FROM p.period) = :tahun" if monthly else ""
    as_of_filter = "AND a.period <= make_date(:tahun, 12, 1)" if monthly else ""

    slope = db.execute(text(f"""
        WITH st AS (
            SELECT DISTINCT ON (a.block_id) a.*
            FROM trx.area_statements a
            WHERE a.block_id IN ({blocks_sql}) {as_of_filter}
            ORDER BY a.block_id, a.period DESC
        )
        SELECT SUM(planted_area_ha * COALESCE(pct_flat, 0) / 100)       AS s0,
               SUM(planted_area_ha * COALESCE(pct_undulating, 0) / 100) AS s1,
               SUM(planted_area_ha * COALESCE(pct_hilly, 0) / 100)      AS s2,
               SUM(planted_area_ha * COALESCE(pct_steep, 0) / 100)      AS s3
        FROM st
    """), params).mappings().one()

    time_cols = "extract(year FROM period)::int AS tahun, " + (
        "extract(month FROM period)::int AS bulan" if monthly else "NULL::int AS bulan")
    group_by = "1, 2"
    rows = db.execute(text(f"""
        WITH m AS (
            SELECT p.period,
                   SUM(p.ffb_actual_kg) AS ffb, SUM(p.bunches_actual) AS bunches,
                   SUM(a.planted_area_ha) AS area, SUM(a.tree_count) AS trees
            FROM trx.block_productions p
            LEFT JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
            WHERE p.block_id IN ({blocks_sql}) {year_filter}
            GROUP BY p.period
        )
        SELECT {time_cols},
               AVG(area) AS luas,
               SUM(ffb) / 1000.0 AS ton,
               SUM(ffb) / NULLIF(SUM(bunches), 0) AS bjr,
               SUM(bunches) / NULLIF(AVG(trees), 0) AS jjg_ppk,
               SUM(ffb) / NULLIF(AVG(trees), 0) AS kg_ppk
        FROM m GROUP BY {group_by} ORDER BY {group_by}
    """), params).mappings().all()

    return {
        "table": "trx_produksi_tbs",
        "label": "Produksi TBS (Histori & Slope)",
        "mode_akumulasi": "BULANAN" if monthly else "TAHUNAN",
        "filter_applied": {**filter_info, "tahun": tahun},
        "slope_kemiringan_lereng": {
            "0-3%": _ha(slope["s0"]), "3-8%": _ha(slope["s1"]), "8-15%": _ha(slope["s2"]),
            "15-25%": _ha(slope["s3"]), ">25%": _ha(0),
        },
        # Nilai numerik (ha) untuk grafik; key sama dengan versi teks di atas.
        "slope_kemiringan_lereng_ha": {
            "0-3%": round(num(slope["s0"]), 2), "3-8%": round(num(slope["s1"]), 2),
            "8-15%": round(num(slope["s2"]), 2), "15-25%": round(num(slope["s3"]), 2), ">25%": 0.0,
        },
        "total_periode": len(rows),
        "data_histori": [
            {
                "periode": r["bulan"] if monthly else r["tahun"],
                "tahun": r["tahun"], "bulan": r["bulan"],
                "luas": round(num(r["luas"]), 2),
                "ton": round(num(r["ton"]), 2),
                "ton_ha": round(num(r["ton"]) / num(r["luas"]), 2) if num(r["luas"]) else 0.0,
                "bjr": round(num(r["bjr"]), 2),
                "jjg_ppk": round(num(r["jjg_ppk"]), 2) if r["jjg_ppk"] is not None else None,
                "kg_ppk": round(num(r["kg_ppk"])) if r["kg_ppk"] is not None else None,
            }
            for r in rows
        ],
    }


def _rotation(db: Session, blocks_sql: str, params: dict, tahun: int | None, filter_info: dict) -> dict:
    monthly = tahun is not None
    time_cols = "extract(year FROM h.period)::int AS tahun, " + (
        "extract(month FROM h.period)::int AS bulan" if monthly else "NULL::int AS bulan")
    rows = db.execute(text(f"""
        SELECT {time_cols},
               COUNT(*) AS total_rotasi,
               MAX(h.rotation_no) AS rotasi_terakhir,
               ROUND(AVG(h.interval_days), 2) AS avg_pusingan_hari,
               SUM(h.area_ha) AS total_luas_rotasi,
               SUM(h.tree_count) AS total_pokok_rotasi
        FROM trx.harvest_rotations h
        WHERE h.block_id IN ({blocks_sql}) {"AND extract(year FROM h.period) = :tahun" if monthly else ""}
        GROUP BY 1, 2 ORDER BY 1, 2
    """), {**params, "tahun": tahun}).mappings().all()

    return {
        "table": "trx_rotasi_pusingan",
        "label": "Rotasi Pusingan",
        "mode_akumulasi": "BULANAN" if monthly else "TAHUNAN",
        "filter_applied": {**filter_info, "tahun": tahun},
        "total_periode": len(rows),
        "data": [
            {
                "tahun": r["tahun"], "bulan": r["bulan"], "total_rotasi": r["total_rotasi"],
                "rotasi_terakhir": num(r["rotasi_terakhir"]) if r["rotasi_terakhir"] is not None else None,
                "avg_pusingan_hari": num(r["avg_pusingan_hari"]),
                "total_luas_rotasi": num(r["total_luas_rotasi"]),
                "total_pokok_rotasi": whole(r["total_pokok_rotasi"]),
            }
            for r in rows
        ],
    }


def _area_statement(db: Session, blocks_sql: str, params: dict, tahun_tanam: int | None, filter_info: dict) -> dict:
    # Snapshot akhir tahun per blok: baris dengan period terbesar di tiap tahun.
    snapshot_cte = f"""
        snap AS (
            SELECT DISTINCT ON (a.block_id, extract(year FROM a.period)) a.*
            FROM trx.area_statements a
            WHERE a.block_id IN ({blocks_sql})
            ORDER BY a.block_id, extract(year FROM a.period), a.period DESC
        )
    """
    if tahun_tanam:
        start_tt = end_tt = tahun_tanam
        mode = "SPESIFIK TAHUN TANAM"
    else:
        end_tt = db.execute(text(f"WITH {snapshot_cte} SELECT max(planting_year) FROM snap"), params).scalar()
        end_tt = end_tt or 0
        start_tt = end_tt - 4
        mode = "AKUMULASI TAHUN TANAM (5 Tahun Tanam Terakhir)"

    rows = db.execute(text(f"""
        WITH {snapshot_cte},
        f AS (
            SELECT st.*, ps.code AS status_tanam, so.name AS jenis_tanah, tp.name AS jenis_topografi,
                   {SEED_VARIETIES_OF_STATEMENT} AS jenis_bibit
            FROM snap st
            LEFT JOIN ref.planting_statuses ps ON ps.id = st.planting_status_id
            LEFT JOIN ref.soil_types so ON so.id = st.soil_type_id
            LEFT JOIN ref.topography_types tp ON tp.id = st.topography_type_id
            WHERE st.planting_year BETWEEN :start_tt AND :end_tt
        )
        SELECT extract(year FROM period)::int AS tahun, status_tanam, planting_month, planting_year,
               jenis_bibit, jenis_topografi, jenis_tanah,
               COUNT(*) AS count_records,
               SUM(planted_area_ha) AS luas_tanam, SUM(land_area_ha) AS luas_tanah, SUM(tree_count) AS total_pokok,
               SUM(tree_count) / NULLIF(SUM(planted_area_ha), 0) AS sph,
               AVG(COALESCE(pct_flat, 0)) AS pct_tanah_datar, AVG(COALESCE(pct_hilly, 0)) AS pct_berbukit,
               AVG(COALESCE(pct_undulating, 0)) AS pct_gelombang, AVG(COALESCE(pct_steep, 0)) AS pct_curam
        FROM f
        GROUP BY 1, 2, 3, 4, 5, 6, 7
        ORDER BY 1 DESC, 4 DESC, 2
    """), {**params, "start_tt": start_tt, "end_tt": end_tt}).mappings().all()

    def totals(items: list[dict]) -> dict:
        luas = sum(num(r["luas_tanam"]) for r in items)
        trees = sum(whole(r["total_pokok"]) for r in items)
        count = sum(r["count_records"] for r in items)

        def weighted(col: str) -> float:  # rata-rata persen berbobot jumlah blok
            return round(sum(num(r[col]) * r["count_records"] for r in items) / count, 2) if count else 0.0

        return {
            "count_records": count,
            "luas_tanam": round(luas, 2),
            "luas_tanah": round(sum(num(r["luas_tanah"]) for r in items), 2),
            "total_pokok": trees,
            "sph": round(trees / luas, 2) if luas else 0.0,
            "pct_tanah_datar": weighted("pct_tanah_datar"), "pct_berbukit": weighted("pct_berbukit"),
            "pct_gelombang": weighted("pct_gelombang"), "pct_curam": weighted("pct_curam"),
        }

    by_year: OrderedDict[int, list[dict]] = OrderedDict()
    for r in rows:
        by_year.setdefault(r["tahun"], []).append(dict(r))

    latest_year = next(iter(by_year), None)
    return {
        "status": "success",
        "message": "Data Areal Statement berhasil dimuat",
        "meta": {
            "table": "trx_areal_statement",
            "label": "Areal Statement",
            "mode_akumulasi": mode,
            "grouped_by_level_1": "tahun",
            "filter_applied": {**filter_info, "tahun_tanam": tahun_tanam or f"{start_tt} - {end_tt}"},
            "group_by_attributes": ["status_tanam", "bulan_tanam", "tahun_tanam", "jenis_bibit", "jenis_topografi", "jenis_tanah"],
            "total_records": len(rows),
            "tahun_grand_total": latest_year,
        },
        "grand_total": {k: v for k, v in totals(by_year.get(latest_year, [])).items() if k != "count_records"},
        "data": [
            {
                "tahun": year,
                "groups": [
                    {
                        "group_keys": {
                            "status_tanam": r["status_tanam"], "bulan_tanam": MONTH_ABBR.get(r["planting_month"]),
                            "tahun_tanam": r["planting_year"], "jenis_bibit": r["jenis_bibit"],
                            "jenis_topografi": r["jenis_topografi"], "jenis_tanah": r["jenis_tanah"],
                        },
                        "totals": totals([r]),
                    }
                    for r in items
                ],
            }
            for year, items in by_year.items()
        ],
    }
