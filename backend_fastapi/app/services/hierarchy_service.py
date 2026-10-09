"""
Daftar master wilayah untuk dropdown/filter FE: area, PT, estate, afdeling, blok.

Master di v3 tidak berperiode lagi (tidak ada bulan/tahun di tabel master).
Parameter bulan/tahun tetap diterima: di /blok dipakai sebagai "kondisi per
periode" untuk atribut dari area statement; di level lain diabaikan dan
field bulan/tahun di response bernilai null.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.services.block_filter import LATEST_AREA_JOIN, SEED_VARIETIES_OF_STATEMENT, BlockFilter, statement_as_of_join
from app.utils.pagination import paginate_sql
from app.utils.period import period_parts


def _search_clause(columns: list[str], search: str | None, clauses: list[str], params: dict) -> None:
    if search and search.strip():
        clauses.append("(" + " OR ".join(f"{c} ILIKE :search" for c in columns) + ")")
        params["search"] = f"%{search.strip()}%"


def _where(clauses: list[str]) -> str:
    return ("WHERE " + " AND ".join(clauses)) if clauses else ""


def list_areas(db: Session, search: str | None, page: int, limit: int,
               extra_clause: tuple[str, dict] | None = None) -> dict:
    clauses, params = [], {}
    if extra_clause:
        clauses.append(extra_clause[0])
        params.update(extra_clause[1])
    _search_clause(["ar.name", "ar.code"], search, clauses, params)
    sql = f"SELECT ar.id, ar.code, ar.name FROM master.areas ar {_where(clauses)}"
    return paginate_sql(db, sql, params, "q.name", page, limit, lambda r: {
        "id": r["id"], "area_id": r["code"], "kode_area": r["code"], "nama": r["name"], "nama_area": r["name"],
        "bulan": None, "tahun": None,
    })


def list_companies(db: Session, search: str | None, kode_pt: str | None, area: str | None, page: int, limit: int,
                   extra_clause: tuple[str, dict] | None = None) -> dict:
    flt = BlockFilter(area=area)
    area_clauses, params = flt.where()
    area_where = ("AND " + " AND ".join(area_clauses)) if area_clauses else ""

    clauses = [] if not area else ["pa.area_code IS NOT NULL"]
    if extra_clause:
        clauses.append(extra_clause[0])
        params.update(extra_clause[1])
    if kode_pt and kode_pt.strip():
        clauses.append("(co.code = :kode_pt OR co.id::text = :kode_pt)")
        params["kode_pt"] = kode_pt.strip()
    _search_clause(["co.name", "co.code"], search, clauses, params)

    # Area "utama" PT = area yang paling banyak dipakai blok-bloknya (atau area yang difilter).
    sql = f"""
        SELECT co.id, co.code, COALESCE(NULLIF(co.name, ''), co.code) AS name, pa.area_code, pa.area_name
        FROM master.companies co
        LEFT JOIN LATERAL (
            SELECT ar.code AS area_code, ar.name AS area_name, COUNT(*) AS n
            FROM master.blocks bl
            JOIN master.divisions dv ON dv.id = bl.division_id
            JOIN master.estates es ON es.id = dv.estate_id
            {LATEST_AREA_JOIN}
            WHERE es.company_id = co.id AND ar.id IS NOT NULL {area_where}
            GROUP BY ar.code, ar.name ORDER BY n DESC LIMIT 1
        ) pa ON true
        {_where(clauses)}
    """
    return paginate_sql(db, sql, params, "q.name", page, limit, lambda r: {
        "id": r["id"], "kode_pt": r["code"], "nama_pt": r["name"],
        "area_id": r["area_code"], "kode_area": r["area_code"], "nama_area": r["area_name"],
        "bulan": None, "tahun": None,
    })


def list_estates(db: Session, search: str | None, kode_pt: str | None, kode_est: str | None, area: str | None,
                 page: int, limit: int, extra_clause: tuple[str, dict] | None = None) -> dict:
    flt = BlockFilter(kode_pt=kode_pt, kode_est=kode_est)
    clauses, params = flt.where()
    if area and area.strip():
        area_clauses, area_params = BlockFilter(area=area).where()
        clauses.append(f"""EXISTS (
            SELECT 1 FROM master.blocks bl
            JOIN master.divisions dv2 ON dv2.id = bl.division_id
            {LATEST_AREA_JOIN}
            WHERE dv2.estate_id = es.id AND {' AND '.join(area_clauses)})""")
        params.update(area_params)
    if extra_clause:
        clauses.append(extra_clause[0])
        params.update(extra_clause[1])
    _search_clause(["es.name", "es.code", "es.short_name"], search, clauses, params)

    sql = f"""
        SELECT es.id, es.code, es.name, es.short_name, co.id AS company_id, co.code AS company_code
        FROM master.estates es JOIN master.companies co ON co.id = es.company_id
        {_where(clauses)}
    """
    return paginate_sql(db, sql, params, "q.name", page, limit, lambda r: {
        "id": r["id"], "pt_id": r["company_id"], "kode_pt": r["company_code"],
        "kode_est": r["code"], "nama_estate": r["name"], "short_name": r["short_name"],
        "bulan": None, "tahun": None,
    })


def list_divisions(db: Session, search: str | None, kode_pt: str | None, kode_est: str | None, kode_afd: str | None,
                   page: int, limit: int, extra_clause: tuple[str, dict] | None = None) -> dict:
    clauses, params = BlockFilter(kode_pt=kode_pt, kode_est=kode_est, kode_afd=kode_afd).where()
    if extra_clause:
        clauses.append(extra_clause[0])
        params.update(extra_clause[1])
    _search_clause(["dv.code"], search, clauses, params)
    sql = f"""
        SELECT dv.id, dv.code, es.id AS estate_id, es.code AS estate_code, co.code AS company_code
        FROM master.divisions dv
        JOIN master.estates es ON es.id = dv.estate_id
        JOIN master.companies co ON co.id = es.company_id
        {_where(clauses)}
    """
    return paginate_sql(db, sql, params, "q.code, q.estate_code", page, limit, lambda r: {
        "id": r["id"], "est_id": r["estate_id"], "kode_est": r["estate_code"], "kode_pt": r["company_code"],
        "kode_afd": r["code"], "nama_afdeling": r["code"], "bulan": None, "tahun": None,
    })


BLOCK_ATTRIBUTE_COLUMNS = f"""
    bl.id, bl.code, bt.name AS block_type,
    dv.id AS division_id, dv.code AS division_code,
    es.id AS estate_id, es.code AS estate_code, es.name AS estate_name,
    co.id AS company_id, co.code AS company_code, COALESCE(NULLIF(co.name, ''), co.code) AS company_name,
    st.period AS statement_period, st.planting_year, st.planting_month,
    ps.code AS planting_status, so.name AS soil_type, tp.name AS topography,
    sar.code AS area_code, sar.name AS area_name,
    {SEED_VARIETIES_OF_STATEMENT} AS seed_varieties
"""


def block_item(r: dict) -> dict:
    bulan, tahun = period_parts(r.get("statement_period"))
    return {
        "id": r["id"], "blok_id": r["id"], "kode_blok": r["code"], "nama_blok": f"Blok {r['code']}",
        "afd_id": r["division_id"], "kode_afd": r["division_code"],
        "est_id": r["estate_id"], "kode_est": r["estate_code"],
        "pt_id": r["company_id"], "kode_pt": r["company_code"],
        "kode_area": r["area_code"],
        "tipe_blok": r["block_type"], "status_tanam": r["planting_status"],
        "tahun_tanam": r["planting_year"], "bulan_tanam": r["planting_month"],
        "jenis_bibit": r["seed_varieties"], "jenis_tanah": r["soil_type"], "jenis_topografi": r["topography"],
        "bulan": bulan, "tahun": tahun,
    }


def list_blocks(
    db: Session, search: str | None, flt: BlockFilter, as_of: date | None, page: int, limit: int,
    tahun_tanam: int | None = None,
) -> dict:
    joins, where_sql, params = flt.sql()
    clauses = [where_sql.removeprefix("WHERE ")] if where_sql else []
    _search_clause(["bl.code"], search, clauses, params)
    if tahun_tanam is not None:
        # Cocokkan dengan statement yang ditampilkan (as_of), sama dengan kolom tahun_tanam di hasil.
        # 0 = belum ditanam (planting_year kosong); blok tanpa statement tidak ikut.
        clauses.append("st.id IS NOT NULL AND COALESCE(st.planting_year, 0) = :f_tahun_tanam")
        params["f_tahun_tanam"] = tahun_tanam
    if as_of:
        params["as_of"] = as_of
    sql = f"""
        SELECT {BLOCK_ATTRIBUTE_COLUMNS}
        FROM master.blocks bl {joins}
        {statement_as_of_join("as_of" if as_of else None)}
        {_where(clauses)}
    """
    return paginate_sql(db, sql, params, "q.code, q.id", page, limit, block_item)
