"""
Histori & agregasi transaksi per wilayah (area/PT/estate/afdeling/blok).

Nama tabel dari FE TIDAK pernah dipakai langsung di SQL -- harus cocok dengan
HISTORY_TABLES (whitelist). Nama lama v2 (trx_produksi_tbs, dst.) tetap
diterima supaya FE tidak berubah.

Karena area statement adalah snapshot bulanan, agregasi luas/pokok memakai
snapshot (bukan penjumlahan semua bulan seperti versi lama yang membuat
angka membengkak 12x).
"""
import re
from collections import OrderedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.services.block_filter import BlockFilter
from app.utils.parsing import num, whole

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


_TRX_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _trx_year_columns(db: Session) -> dict[str, str]:
    """nama tabel trx -> kolom filter tahun.

    Ada `planting_year` -> pakai kolom itu. Tidak ada -> tahun dari `period`.
    Hanya tabel data yang bisa dibatasi per blok.
    """
    rows = db.execute(text("""
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema
         AND t.table_name = c.table_name
         AND t.table_type = 'BASE TABLE'
        JOIN information_schema.columns b
          ON b.table_schema = c.table_schema
         AND b.table_name = c.table_name
         AND b.column_name = 'block_id'
        WHERE c.table_schema = 'trx'
          AND c.column_name IN ('planting_year', 'period')
    """)).all()
    found: dict[str, set[str]] = {}
    for name, column in rows:
        if _TRX_IDENT.fullmatch(name):
            found.setdefault(name, set()).add(column)
    chosen: dict[str, str] = {}
    for name, columns in found.items():
        if "planting_year" in columns:
            chosen[name] = "planting_year"
        elif "period" in columns:
            chosen[name] = "period"
    return chosen


def list_planting_years(db: Session, flt: BlockFilter) -> list[int]:
    """Tahun unik untuk filter histori, mengikuti kolom masing-masing tabel trx.

    Tabel yang punya planting_year menyumbang nilai kolom itu (kosong = 0, belum ditanam). Tabel yang tidak
    punya menyumbang tahun kolom period. Dibatasi blok pada filter wilayah.
    """
    columns = _trx_year_columns(db)
    if not columns:
        return []
    blocks_sql, params = flt.block_ids_subquery()
    parts = []
    for name, column in sorted(columns.items()):
        if column == "planting_year":
            parts.append(
                f"SELECT COALESCE(planting_year, 0)::int AS tahun FROM trx.{name} "
                f"WHERE block_id IN (SELECT id FROM blocks)"
            )
        else:
            parts.append(
                f"SELECT extract(year FROM period)::int AS tahun FROM trx.{name} "
                f"WHERE period IS NOT NULL AND block_id IN (SELECT id FROM blocks)"
            )
    rows = db.execute(text(f"""
        WITH blocks AS ({blocks_sql})
        SELECT DISTINCT tahun FROM ({' UNION ALL '.join(parts)}) src
        WHERE tahun IS NOT NULL
        ORDER BY tahun DESC
    """), params).scalars().all()
    return [int(y) for y in rows]


def get_history(
    db: Session,
    table: str,
    tahun: int | None,
    flt: BlockFilter,
    *,
    period_year: int | None = None,
) -> dict:
    """Histori satu tabel trx.

    `period_year` (query tahun_tanam) menyaring baris tabel itu:
    planting_year bila kolomnya ada, selain itu tahun kolom period.
    `tahun` tetap drill bulanan tahun kalender untuk tabel yang disaring lewat period.
    Untuk areal statement, `tahun` = snapshot per akhir tahun itu dan `period_year` = tahun tanam.
    """
    key, physical = resolve_history_table(table)
    blocks_sql, params = flt.block_ids_subquery()
    if key == "trx_areal_statement":
        return _area_statement(db, blocks_sql, params, tahun=tahun, tahun_tanam=period_year)

    year_column = _trx_year_columns(db).get(physical.split(".")[-1], "period")

    filter_info = {
        "area_id": flt.area, "kode_pt": flt.kode_pt, "kode_est": flt.kode_est, "kode_afd": flt.kode_afd,
        "blok_id": flt.blok, "ownership": flt.ownership,
        "tahun_tanam": str(period_year) if period_year is not None else flt.tahun_tanam,
    }
    if year_column == "planting_year":
        if key == "trx_produksi_tbs":
            return _production(db, blocks_sql, params, tahun, filter_info, planting_year=period_year)
        if key == "trx_rotasi_pusingan":
            return _rotation(db, blocks_sql, params, tahun, filter_info, planting_year=period_year)

    year, monthly = _period_filter(tahun, period_year)
    if key == "trx_produksi_tbs":
        return _production(db, blocks_sql, params, year, filter_info, monthly=monthly)
    return _rotation(db, blocks_sql, params, year, filter_info, monthly=monthly)


def _period_filter(tahun: int | None, period_year: int | None) -> tuple[int | None, bool]:
    """(tahun period yang disaring, apakah dipecah per bulan).

    `tahun` saja tetap drill bulanan. `period_year` saja menyaring tahun
    kolom period dan agregasinya tetap tahunan.
    """
    if period_year is not None and tahun is None:
        return period_year, False
    if tahun is not None and (period_year is None or period_year == tahun):
        return tahun, True
    if period_year is not None:
        return period_year, False
    return None, False


GAP_CATEGORIES = (
    ("OPTIMUM", "Varians > 0%"),
    ("GAP I", "Varians minus 1 - 20%"),
    ("GAP II", "Varians minus 20 - 40%"),
    ("GAP III", "Varians minus > 40%"),
)


def block_production_history(db: Session, block_id: int, tahun: int | None) -> dict:
    """Respons `trx_produksi_tbs` (sama dengan GET /history) untuk SATU blok berdasarkan id pasti."""
    return _production(db, "SELECT :hist_bid", {"hist_bid": block_id}, tahun, {"blok_id": block_id})


def gap_pct(actual, target) -> float | None:
    """% selisih aktual terhadap target ((aktual - target) / target * 100)."""
    if actual is None or not target:
        return None
    return (actual - target) / target * 100


def gap_category(gap_pct: float | None) -> str | None:
    """Kategori varians produksi (sama dengan aplikasi lama); None bila tidak ada target."""
    if gap_pct is None:
        return None
    if gap_pct >= 0:
        return "OPTIMUM"
    if gap_pct >= -20:
        return "GAP I"
    if gap_pct >= -40:
        return "GAP II"
    return "GAP III"


def _production_gap_summary(db: Session, blocks_sql: str, params: dict, year_filter: str, target: str) -> dict | None:
    """Rekap kategori GAP per blok (luas, jumlah blok, % blok) pada periode produksi terbaru."""
    latest = db.execute(text(f"""
        SELECT max(p.period) FROM trx.block_productions p WHERE p.block_id IN ({blocks_sql}) {year_filter}
    """), params).scalar()
    if latest is None:
        return None
    target_col = {"budget": "ffb_budget_kg", "sensus": "ffb_census_kg"}[target]
    blocks = db.execute(text(f"""
        SELECT SUM(p.ffb_actual_kg) AS act, SUM(p.{target_col}) AS tgt, SUM(a.planted_area_ha) AS luas
        FROM trx.block_productions p
        LEFT JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
        WHERE p.block_id IN ({blocks_sql}) AND p.period = :latest
        GROUP BY p.block_id
    """), {**params, "latest": latest}).mappings().all()

    buckets = {name: {"luas": 0.0, "jumlah_blok": 0} for name, _ in GAP_CATEGORIES}
    for b in blocks:
        category = gap_category(gap_pct(num(b["act"]), num(b["tgt"])))
        if category:
            buckets[category]["luas"] += num(b["luas"])
            buckets[category]["jumlah_blok"] += 1
    total_blok = sum(v["jumlah_blok"] for v in buckets.values())
    return {
        "periode": {"tahun": latest.year, "bulan": latest.month},
        "pembanding": target,
        "kategori": [
            {
                "kategori": name, "keterangan": note, "luas": round(buckets[name]["luas"], 2),
                "jumlah_blok": buckets[name]["jumlah_blok"],
                "persen_blok": round(buckets[name]["jumlah_blok"] / total_blok * 100, 1) if total_blok else 0.0,
            }
            for name, note in GAP_CATEGORIES
        ],
        "grand_total": {
            "luas": round(sum(v["luas"] for v in buckets.values()), 2), "jumlah_blok": total_blok,
            "persen_blok": 100.0 if total_blok else 0.0,
        },
    }


def _production(
    db: Session,
    blocks_sql: str,
    params: dict,
    tahun: int | None,
    filter_info: dict,
    *,
    monthly: bool | None = None,
    planting_year: int | None = None,
) -> dict:
    if monthly is None:
        monthly = tahun is not None
    params = {**params, "tahun": tahun, "planting_year": planting_year}
    year_filter = "AND extract(year FROM p.period) = :tahun" if tahun is not None else ""
    if planting_year is not None:
        year_filter += " AND COALESCE(p.planting_year, 0) = :planting_year"
    as_of_filter = "AND a.period <= make_date(:tahun, 12, 1)" if tahun is not None else ""

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
                   SUM(p.ffb_actual_kg) AS ffb, SUM(p.ffb_budget_kg) AS ffb_bgt, SUM(p.ffb_census_kg) AS ffb_sns,
                   SUM(p.bunches_actual) AS bunches, SUM(a.planted_area_ha) AS area, SUM(a.tree_count) AS trees
            FROM trx.block_productions p
            LEFT JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
            WHERE p.block_id IN ({blocks_sql}) {year_filter}
            GROUP BY p.period
        )
        SELECT {time_cols},
               AVG(area) AS luas,
               SUM(ffb) / 1000.0 AS ton,
               SUM(ffb_bgt) / 1000.0 AS ton_bgt,
               SUM(ffb_sns) / 1000.0 AS ton_sns,
               SUM(ffb) / NULLIF(SUM(bunches), 0) AS bjr,
               SUM(bunches) / NULLIF(AVG(trees), 0) AS jjg_ppk,
               SUM(ffb) / NULLIF(AVG(trees), 0) AS kg_ppk
        FROM m GROUP BY {group_by} ORDER BY {group_by}
    """), params).mappings().all()

    def history_row(r) -> dict:
        luas = num(r["luas"])
        yield_of = lambda ton: num(ton) / luas if luas and ton is not None else None  # noqa: E731
        y_act, y_bgt, y_sns = yield_of(r["ton"]), yield_of(r["ton_bgt"]), yield_of(r["ton_sns"])
        gap_bgt, gap_sns = gap_pct(y_act, y_bgt), gap_pct(y_act, y_sns)
        rnd = lambda v: round(v, 2) if v is not None else None  # noqa: E731
        return {
            "periode": r["bulan"] if monthly else r["tahun"],
            "tahun": r["tahun"], "bulan": r["bulan"],
            "luas": round(luas, 2),
            "ton": round(num(r["ton"]), 2),
            "ton_ha": round(y_act, 2) if y_act is not None else 0.0,
            "ton_ha_budget": rnd(y_bgt), "ton_ha_sensus": rnd(y_sns),
            "gap_budget_pct": rnd(gap_bgt), "gap_sensus_pct": rnd(gap_sns),
            "kategori_budget": gap_category(gap_bgt), "kategori_sensus": gap_category(gap_sns),
            "bjr": round(num(r["bjr"]), 2),
            "jjg_ppk": round(num(r["jjg_ppk"]), 2) if r["jjg_ppk"] is not None else None,
            "kg_ppk": round(num(r["kg_ppk"])) if r["kg_ppk"] is not None else None,
        }

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
        "data_histori": [history_row(r) for r in rows],
        "ringkasan_gap_budget": _production_gap_summary(db, blocks_sql, params, year_filter, "budget"),
        "ringkasan_gap_sensus": _production_gap_summary(db, blocks_sql, params, year_filter, "sensus"),
    }


def _rotation(
    db: Session,
    blocks_sql: str,
    params: dict,
    tahun: int | None,
    filter_info: dict,
    *,
    monthly: bool | None = None,
    planting_year: int | None = None,
) -> dict:
    if monthly is None:
        monthly = tahun is not None
    time_cols = "extract(year FROM h.period)::int AS tahun, " + (
        "extract(month FROM h.period)::int AS bulan" if monthly else "NULL::int AS bulan")
    planting_sql = "AND COALESCE(h.planting_year, 0) = :planting_year" if planting_year is not None else ""
    period_sql = "AND extract(year FROM h.period) = :tahun" if tahun is not None else ""
    rows = db.execute(text(f"""
        SELECT {time_cols},
               COUNT(*) AS total_rotasi,
               MAX(h.rotation_no) AS rotasi_terakhir,
               ROUND(AVG(h.interval_days), 2) AS avg_pusingan_hari,
               SUM(h.area_ha) AS total_luas_rotasi,
               SUM(h.tree_count) AS total_pokok_rotasi
        FROM trx.harvest_rotations h
        WHERE h.block_id IN ({blocks_sql}) {period_sql} {planting_sql}
        GROUP BY 1, 2 ORDER BY 1, 2
    """), {**params, "tahun": tahun, "planting_year": planting_year}).mappings().all()

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


def _area_statement(
    db: Session,
    blocks_sql: str,
    params: dict,
    *,
    tahun: int | None = None,
    tahun_tanam: int | None = None,
) -> dict:
    """Luas tanam dikelompokkan per tahun tanam dan per divisi.

    Memakai snapshot periode terakhir yang tersedia (dibatasi akhir `tahun` bila diisi),
    sehingga luas blok tidak terjumlah berulang untuk setiap periode bulanan dan blok
    yang tidak lagi dilaporkan di periode itu tidak ikut terhitung.
    Tahun tanam kosong (belum ditanam) dilaporkan sebagai 0.
    """
    period_sql = "AND a.period < make_date(:tahun + 1, 1, 1)" if tahun is not None else ""
    planting_sql = "WHERE COALESCE(st.planting_year, 0) = :tahun_tanam" if tahun_tanam is not None else ""
    rows = db.execute(text(f"""
        WITH scoped AS (
            SELECT a.period, a.block_id, a.area_id, a.planting_year, a.planted_area_ha
            FROM trx.area_statements a
            WHERE a.block_id IN ({blocks_sql}) {period_sql}
        ),
        snap AS (SELECT * FROM scoped WHERE period = (SELECT max(period) FROM scoped))
        SELECT COALESCE(st.planting_year, 0)::int AS tahun_tanam, dv.code AS division_code, ar.code AS area_code,
               SUM(st.planted_area_ha) AS luas_tanam
        FROM snap st
        JOIN master.blocks bl ON bl.id = st.block_id
        JOIN master.divisions dv ON dv.id = bl.division_id
        LEFT JOIN master.areas ar ON ar.id = st.area_id
        {planting_sql}
        GROUP BY 1, 2, 3
    """), {**params, "tahun": tahun, "tahun_tanam": tahun_tanam}).mappings().all()

    area_codes = {r["area_code"] for r in rows}
    area_code = next(iter(area_codes)) if len(area_codes) == 1 else None

    def group(key: str) -> dict:
        sums: dict = {}
        for r in rows:
            sums[r[key]] = sums.get(r[key], 0.0) + num(r["luas_tanam"])
        return {
            "area_code": area_code,
            "details": [{key: k, "luas_tanam": round(v, 2)} for k, v in sorted(sums.items())],
            "total_luas_tanam": round(sum(sums.values()), 2),
        }

    return {
        "status": "success",
        "message": "Data berhasil diekstrak",
        "data": {
            "group_tahun_tanam": group("tahun_tanam"),
            "group_divisi": group("division_code"),
        },
    }
