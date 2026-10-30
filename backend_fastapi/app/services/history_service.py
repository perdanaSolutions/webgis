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
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.services.block_filter import BlockFilter
from app.utils.gap import gap_kategori
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
    gap_as_of: date | None = None,
    bulan: int | None = None,
    year_to_date: bool = False,
) -> dict:
    """Histori satu tabel trx.

    `bulan` (1-12) menyempit ke bulan itu: produksi/rotasi hanya periode bulan tsb (dengan `tahun` = satu periode,
    tanpa `tahun` = bulan yang sama di tiap tahun), areal statement = snapshot s/d bulan itu. Baris selalu per bulan.

    `gap_as_of` (periode pilihan user) membatasi periode ringkasan GAP produksi; kosong = terbaru.

    `period_year` (query tahun_tanam) menyaring baris tabel itu:
    planting_year bila kolomnya ada, selain itu tahun kolom period.
    `tahun` tetap drill bulanan tahun kalender untuk tabel yang disaring lewat period.
    Untuk areal statement, `tahun` = snapshot per akhir tahun itu dan `period_year` = tahun tanam.
    """
    key, physical = resolve_history_table(table)
    blocks_sql, params = flt.block_ids_subquery()
    params = {**params, "gap_as_of": gap_as_of, "gap_ytd": year_to_date}
    if key == "trx_areal_statement":
        return _area_statement(db, blocks_sql, params, tahun=tahun, tahun_tanam=period_year, bulan=bulan)

    year_column = _trx_year_columns(db).get(physical.split(".")[-1], "period")

    filter_info = {
        "area_id": flt.area, "kode_pt": flt.kode_pt, "kode_est": flt.kode_est, "kode_afd": flt.kode_afd,
        "blok_id": flt.blok, "ownership": flt.ownership,
        "tahun_tanam": str(period_year) if period_year is not None else flt.tahun_tanam,
        "bulan": bulan,
    }
    if year_column == "planting_year":
        if key == "trx_produksi_tbs":
            return _production(db, blocks_sql, params, tahun, filter_info, planting_year=period_year, bulan=bulan)
        if key == "trx_rotasi_pusingan":
            return _rotation(db, blocks_sql, params, tahun, filter_info, planting_year=period_year, bulan=bulan)

    year, monthly = _period_filter(tahun, period_year)
    if key == "trx_produksi_tbs":
        return _production(db, blocks_sql, params, year, filter_info, monthly=monthly, bulan=bulan)
    return _rotation(db, blocks_sql, params, year, filter_info, monthly=monthly, bulan=bulan)


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
    ("OPTIMUM", "Varians >= 0%"),
    ("GAP I", "Varians minus 1 - 20%"),
    ("GAP II", "Varians minus 20 - 40%"),
    ("GAP III", "Varians minus > 40%"),
)


def block_production_history(db: Session, block_id: int, tahun: int | None, gap_as_of: date | None = None) -> dict:
    """Respons `trx_produksi_tbs` (sama dengan GET /history) untuk SATU blok berdasarkan id pasti."""
    return _production(
        db, "SELECT :hist_bid", {"hist_bid": block_id, "gap_as_of": gap_as_of}, tahun, {"blok_id": block_id},
    )


def gap_pct(actual, target) -> float | None:
    """% selisih aktual terhadap target ((aktual - target) / target * 100)."""
    if actual is None or not target:
        return None
    return (actual - target) / target * 100


def gap_category(gap_pct: float | None) -> str | None:
    """Kategori varians produksi = aturan Excel lama (app.utils.gap); None bila tidak ada target."""
    return gap_kategori(gap_pct) or None


def _production_gap_summary(db: Session, blocks_sql: str, params: dict, year_filter: str, target: str) -> dict | None:
    """Rekap kategori GAP per blok (luas, jumlah blok, % blok).

    Periode yang dipakai: produksi terbaru, dibatasi `gap_as_of` (periode yang dipilih user) bila ada.

    `gap_ytd` (Year to Date): kategori per blok dari agregat Januari s/d periode itu pada tahun yang sama:
    gap% = (Σ aktual kg - Σ target kg) / Σ target kg * 100 (rumus sama dengan bulanan), luas = luas tanam
    blok pada bulan terakhir rentang (bulan terakhir yang punya areal statement <= periode akhir).
    """
    ytd = bool(params.get("gap_ytd"))
    as_of_filter = "AND p.period <= :gap_as_of" if params.get("gap_as_of") else ""
    latest = db.execute(text(f"""
        SELECT max(p.period) FROM trx.block_productions p
        WHERE p.block_id IN ({blocks_sql}) {year_filter} {as_of_filter}
    """), params).scalar()
    if latest is None:
        return None
    target_col = {"budget": "ffb_budget_kg", "sensus": "ffb_census_kg"}[target]
    start = date(latest.year, 1, 1) if ytd else latest
    if ytd:
        blocks = db.execute(text(f"""
            WITH p AS (
                SELECT p.block_id, SUM(p.ffb_actual_kg) AS act, SUM(p.{target_col}) AS tgt
                FROM trx.block_productions p
                WHERE p.block_id IN ({blocks_sql}) AND p.period BETWEEN :start AND :latest
                GROUP BY p.block_id
            )
            SELECT p.act, p.tgt,
                   (SELECT a.planted_area_ha FROM trx.area_statements a
                    WHERE a.block_id = p.block_id AND a.period BETWEEN :start AND :latest
                    ORDER BY a.period DESC LIMIT 1) AS luas
            FROM p
        """), {**params, "latest": latest, "start": start}).mappings().all()
    else:
        blocks = None
    blocks = blocks if blocks is not None else db.execute(text(f"""
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
        "periode_mulai": {"tahun": start.year, "bulan": start.month},
        "year_to_date": ytd,
        "pembanding": target,
        "kategori": [
            {
                "kategori": name, "keterangan": note, "luas": round(buckets[name]["luas"], 4),
                "jumlah_blok": buckets[name]["jumlah_blok"],
                "persen_blok": round(buckets[name]["jumlah_blok"] / total_blok * 100, 4) if total_blok else 0.0,
            }
            for name, note in GAP_CATEGORIES
        ],
        "grand_total": {
            "luas": round(sum(v["luas"] for v in buckets.values()), 4), "jumlah_blok": total_blok,
            "persen_blok": 100.0 if total_blok else 0.0,
        },
    }


def yearly_recap_rows(months: list[dict]) -> list[dict]:
    """Rekap per tahun dari baris BULANAN mentah (belum dibulatkan), tahun naik.

    Rumus (selaras ringkasan tahunan frontend utils/productionSummary.ts):
    - luas            : luas bulan TERAKHIR tahun itu yang punya luas (luas tanam berulang tiap bulan, tidak dijumlah).
    - ton             : SUM ton bulanan.
    - ton_ha          : ton / luas.
    - ton_ha_budget   : SUM ton budget / luas (= jumlah ton/ha budget bulanan bila luas tetap; satu penyebut
                        dengan ton_ha supaya gap tidak terdistorsi perubahan luas).  ton_ha_sensus: idem.
    - gap_*_pct       : (ton_ha - ton_ha_target) / ton_ha_target * 100 (rumus bulanan, gap_pct).
    - kategori_*      : gap_category(gap tahunan), ambang sama dengan bulanan.
    - bjr             : SUM kg / SUM janjang (definisi BJR bulanan = kg / janjang).
    - jjg_ppk, kg_ppk : SUM nilai bulanan (janjang/pokok, kg/pokok per bulan).
    - jumlah_periode  : jumlah bulan yang punya data produksi.
    """
    years: dict[int, dict] = {}
    for m in sorted(months, key=lambda r: (r["tahun"], r["bulan"])):
        y = years.setdefault(m["tahun"], {"n": 0, "luas": None, "ffb": 0.0, "bgt": 0.0, "sns": 0.0, "has_bgt": False,
                                          "has_sns": False, "bunches": 0.0, "jjg_ppk": None, "kg_ppk": None})
        y["n"] += 1
        if m["area"] is not None and num(m["area"]) > 0:
            y["luas"] = num(m["area"])
        y["ffb"] += num(m["ffb"])
        if m["ffb_bgt"] is not None:
            y["bgt"] += num(m["ffb_bgt"]); y["has_bgt"] = True
        if m["ffb_sns"] is not None:
            y["sns"] += num(m["ffb_sns"]); y["has_sns"] = True
        y["bunches"] += num(m["bunches"])
        trees = num(m["trees"])
        if trees:
            y["jjg_ppk"] = (y["jjg_ppk"] or 0.0) + num(m["bunches"]) / trees
            y["kg_ppk"] = (y["kg_ppk"] or 0.0) + num(m["ffb"]) / trees

    rnd = lambda v: round(v, 4) if v is not None else None  # noqa: E731
    out = []
    for tahun, y in sorted(years.items()):
        luas = y["luas"] or 0.0
        per_ha = lambda kg: kg / 1000.0 / luas if luas else None  # noqa: E731
        y_act = per_ha(y["ffb"])
        y_bgt = per_ha(y["bgt"]) if y["has_bgt"] else None
        y_sns = per_ha(y["sns"]) if y["has_sns"] else None
        gap_bgt, gap_sns = gap_pct(y_act, y_bgt), gap_pct(y_act, y_sns)
        out.append({
            "tahun": tahun,
            "jumlah_periode": y["n"],
            "luas": round(luas, 4),
            "ton": round(y["ffb"] / 1000.0, 4),
            "ton_ha": round(y_act, 4) if y_act is not None else 0.0,
            "ton_ha_budget": rnd(y_bgt), "ton_ha_sensus": rnd(y_sns),
            "gap_budget_pct": rnd(gap_bgt), "gap_sensus_pct": rnd(gap_sns),
            "kategori_budget": gap_category(gap_bgt), "kategori_sensus": gap_category(gap_sns),
            "bjr": round(y["ffb"] / y["bunches"], 4) if y["bunches"] else 0.0,
            "jjg_ppk": rnd(y["jjg_ppk"]),
            "kg_ppk": round(y["kg_ppk"], 4) if y["kg_ppk"] is not None else None,
        })
    return out


def yearly_recap(db: Session, blocks_sql: str, params: dict, *, planting_year: int | None = None) -> list[dict]:
    """`rekap_tahunan`: SEMUA tahun produksi untuk filter wilayah + hak akses (blocks_sql), mengabaikan
    filter `tahun`/`bulan`. Filter tahun tanam tetap dipakai bila tabel punya kolom planting_year."""
    pf = "AND COALESCE(p.planting_year, 0) = :rk_py" if planting_year is not None else ""
    months = db.execute(text(f"""
        SELECT extract(year FROM p.period)::int AS tahun, extract(month FROM p.period)::int AS bulan,
               SUM(p.ffb_actual_kg) AS ffb, SUM(p.ffb_budget_kg) AS ffb_bgt, SUM(p.ffb_census_kg) AS ffb_sns,
               SUM(p.bunches_actual) AS bunches, SUM(a.planted_area_ha) AS area, SUM(a.tree_count) AS trees
        FROM trx.block_productions p
        LEFT JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
        WHERE p.block_id IN ({blocks_sql}) {pf}
        GROUP BY p.period
    """), {**params, "rk_py": planting_year}).mappings().all()
    return yearly_recap_rows([dict(m) for m in months])


def _production(
    db: Session,
    blocks_sql: str,
    params: dict,
    tahun: int | None,
    filter_info: dict,
    *,
    monthly: bool | None = None,
    planting_year: int | None = None,
    bulan: int | None = None,
) -> dict:
    if monthly is None:
        monthly = tahun is not None
    monthly = monthly or bulan is not None
    params = {**params, "tahun": tahun, "planting_year": planting_year, "bulan": bulan}
    year_filter = "AND extract(year FROM p.period) = :tahun" if tahun is not None else ""
    if bulan is not None:
        year_filter += " AND extract(month FROM p.period) = :bulan"
    if planting_year is not None:
        year_filter += " AND COALESCE(p.planting_year, 0) = :planting_year"
    as_of_filter = "AND a.period <= make_date(:tahun, COALESCE(:bulan, 12), 1)" if tahun is not None else ""

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
        rnd = lambda v: round(v, 4) if v is not None else None  # noqa: E731
        return {
            "periode": r["bulan"] if monthly else r["tahun"],
            "tahun": r["tahun"], "bulan": r["bulan"],
            "luas": round(luas, 4),
            "ton": round(num(r["ton"]), 4),
            "ton_ha": round(y_act, 4) if y_act is not None else 0.0,
            "ton_ha_budget": rnd(y_bgt), "ton_ha_sensus": rnd(y_sns),
            "gap_budget_pct": rnd(gap_bgt), "gap_sensus_pct": rnd(gap_sns),
            "kategori_budget": gap_category(gap_bgt), "kategori_sensus": gap_category(gap_sns),
            "bjr": round(num(r["bjr"]), 4),
            "jjg_ppk": round(num(r["jjg_ppk"]), 4) if r["jjg_ppk"] is not None else None,
            "kg_ppk": round(num(r["kg_ppk"]), 4) if r["kg_ppk"] is not None else None,
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
            "0-3%": round(num(slope["s0"]), 4), "3-8%": round(num(slope["s1"]), 4),
            "8-15%": round(num(slope["s2"]), 4), "15-25%": round(num(slope["s3"]), 4), ">25%": 0.0,
        },
        "rekap_tahunan": yearly_recap(db, blocks_sql, params, planting_year=planting_year),
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
    bulan: int | None = None,
) -> dict:
    if monthly is None:
        monthly = tahun is not None
    monthly = monthly or bulan is not None
    time_cols = "extract(year FROM h.period)::int AS tahun, " + (
        "extract(month FROM h.period)::int AS bulan" if monthly else "NULL::int AS bulan")
    planting_sql = "AND COALESCE(h.planting_year, 0) = :planting_year" if planting_year is not None else ""
    period_sql = "AND extract(year FROM h.period) = :tahun" if tahun is not None else ""
    if bulan is not None:
        period_sql += " AND extract(month FROM h.period) = :bulan"
    rows = db.execute(text(f"""
        SELECT {time_cols},
               COUNT(*) AS total_rotasi,
               MAX(h.rotation_no) AS rotasi_terakhir,
               ROUND(AVG(h.interval_days), 2) AS avg_pusingan_hari,
               SUM(h.area_ha) AS total_luas_rotasi,
               SUM(h.area_ha * h.rotation_no) AS luas_panen,
               SUM(h.tree_count) AS total_pokok_rotasi
        FROM trx.harvest_rotations h
        WHERE h.block_id IN ({blocks_sql}) {period_sql} {planting_sql}
        GROUP BY 1, 2 ORDER BY 1, 2
    """), {**params, "tahun": tahun, "planting_year": planting_year, "bulan": bulan}).mappings().all()

    return {
        "table": "trx_rotasi_pusingan",
        "label": "Rotasi Pusingan",
        "mode_akumulasi": "BULANAN" if monthly else "TAHUNAN",
        "filter_applied": {**filter_info, "tahun": tahun},
        "total_periode": len(rows),
        "ringkasan": rotation_summary(rows),
        "data": [
            {
                "tahun": r["tahun"], "bulan": r["bulan"], "total_rotasi": r["total_rotasi"],
                "rotasi_terakhir": num(r["rotasi_terakhir"]) if r["rotasi_terakhir"] is not None else None,
                "avg_pusingan_hari": num(r["avg_pusingan_hari"]),
                "total_luas_rotasi": num(r["total_luas_rotasi"]),
                "luas_panen": num(r["luas_panen"]),
                "total_pokok_rotasi": whole(r["total_pokok_rotasi"]),
            }
            for r in rows
        ],
    }


def rotation_summary(rows) -> dict | None:
    """Total rotasi periode = Σ luas panen ÷ luas tanam (bukan SUM rotasi bulanan).

    Per baris trx.harvest_rotations: area_ha = luas tanam blok (sama dengan planted_area_ha area statement),
    rotation_no = berapa kali blok dipanen di bulan itu, jadi luas panen = area_ha × rotation_no.
    Luas tanam = Σ area_ha bulan terakhir pada rentang (aturan luas = bulan terakhir, sama dengan rekap produksi).
    """
    rows = [r for r in rows if r["total_luas_rotasi"] is not None]
    if not rows:
        return None
    luas_panen = sum(float(r["luas_panen"] or 0) for r in rows)
    luas_tanam = float(rows[-1]["total_luas_rotasi"] or 0)
    return {
        "luas_panen": round(luas_panen, 4),
        "luas_tanam": round(luas_tanam, 4),
        "rotasi": round(luas_panen / luas_tanam, 4) if luas_tanam > 0 else None,
        "periode_luas_tanam": {"tahun": rows[-1]["tahun"], "bulan": rows[-1]["bulan"]},
    }


def _area_statement(
    db: Session,
    blocks_sql: str,
    params: dict,
    *,
    tahun: int | None = None,
    tahun_tanam: int | None = None,
    bulan: int | None = None,
) -> dict:
    """Luas tanam dikelompokkan per tahun tanam dan per divisi.

    Memakai snapshot periode terakhir yang tersedia (dibatasi akhir `tahun` bila diisi),
    sehingga luas blok tidak terjumlah berulang untuk setiap periode bulanan dan blok
    yang tidak lagi dilaporkan di periode itu tidak ikut terhitung.
    Tahun tanam kosong (belum ditanam) dilaporkan sebagai 0.
    """
    period_sql = "AND a.period < make_date(:tahun + 1, 1, 1)" if tahun is not None else ""
    if bulan is not None:
        # snapshot s/d bulan itu (dengan tahun), atau bulan yang sama pada semua tahun (tanpa tahun)
        period_sql = (
            "AND a.period < (make_date(:tahun, :bulan, 1) + interval '1 month')" if tahun is not None
            else "AND extract(month FROM a.period) = :bulan"
        )
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
    """), {**params, "tahun": tahun, "tahun_tanam": tahun_tanam, "bulan": bulan}).mappings().all()

    area_codes = {r["area_code"] for r in rows}
    area_code = next(iter(area_codes)) if len(area_codes) == 1 else None

    def group(key: str) -> dict:
        sums: dict = {}
        for r in rows:
            sums[r[key]] = sums.get(r[key], 0.0) + num(r["luas_tanam"])
        return {
            "area_code": area_code,
            "details": [{key: k, "luas_tanam": round(v, 4)} for k, v in sorted(sums.items())],
            "total_luas_tanam": round(sum(sums.values()), 4),
        }

    return {
        "status": "success",
        "message": "Data berhasil diekstrak",
        "data": {
            "group_tahun_tanam": group("tahun_tanam"),
            "group_divisi": group("division_code"),
        },
    }
