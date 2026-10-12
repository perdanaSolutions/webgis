"""
Detail popup saat blok diklik di peta.

Periode `bulan` + `tahun` dipakai persis (tidak diganti ke transaksi terakhir).
Luas, pokok, dan SPH diambil dari satu baris areal statement periode itu.
TBS, janjang, dan BJR diambil dari produksi periode yang sama.
Yield (ton/ha) = tbs / 1000 / luas_tanam.
Gap = IFERROR((yield_aktual - yield_pembanding) / yield_pembanding%; 0),
yaitu ((aktual - pembanding) / pembanding) * 100, atau 0 bila pembanding 0.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.services.block_filter import BLOCK_JOINS, BLOCK_REF_MATCH, SEED_VARIETIES_OF_STATEMENT, statement_as_of_join
from app.utils.parsing import MONTH_ABBR, num, whole
from app.utils.period import as_of_period, to_period


def resolve_block_id(db: Session, blok_ref: str) -> int:
    rows = db.execute(
        text(f"""
            SELECT bl.id, (bl.id::text = :ref) AS exact
            FROM master.blocks bl WHERE {BLOCK_REF_MATCH.format(p='ref')}
            ORDER BY exact DESC, bl.id LIMIT 3
        """),
        {"ref": blok_ref.strip()},
    ).mappings().all()
    if not rows:
        raise not_found(f"Blok '{blok_ref}' tidak ditemukan di sistem.")
    if len(rows) > 1 and not rows[0]["exact"]:
        raise bad_request(
            f"Kode blok '{blok_ref}' dipakai di lebih dari satu afdeling. Gunakan blok_id numerik.", field="blok_id"
        )
    return rows[0]["id"]


def gap_kategori(value: float) -> str:
    """
    Kategori dari nilai gap (persen), sama dengan rumus Excel:
    < -40 GAP III; -40 s/d -20 GAP II; di atas -20 dan di bawah 0 GAP I;
    di atas 0 OPTIMUM. Nilai 0 (termasuk hasil IFERROR) tidak berkategori.
    """
    if value < -40:
        return "GAP III"
    if -40 <= value <= -20:
        return "GAP II"
    if -20 < value < 0:
        return "GAP I"
    if value > 0:
        return "OPTIMUM"
    return ""


def gap_value(actual: float, target: float) -> float:
    """IFERROR((aktual - target) / target%; 0) = selisih persen, atau 0."""
    if not target:
        return 0.0
    value = round((actual - target) / target * 100, 2)
    return 0.0 if value == 0 else value


def _yield_ton_ha(kg: float, luas: float) -> float:
    if not luas:
        return 0.0
    return round(kg / 1000 / luas, 2)


def _gap_pair(actual_yield: float, target_yield: float) -> dict:
    value = gap_value(actual_yield, target_yield)
    return {"value": value, "kategori": gap_kategori(value)}


def _resolve_detail_period(db: Session, block_id: int, bulan: int | None, tahun: int | None) -> tuple[date | None, bool]:
    """
    Bulan dan tahun diisi: periode itu persis, meski belum ada transaksi.
    Selain itu: bulan terakhir yang ada (dibatasi akhir tahun bila hanya tahun).
    """
    if bulan is not None and tahun is not None:
        return to_period(bulan, tahun), True

    as_of = as_of_period(bulan, tahun)
    period = db.execute(text("""
        SELECT MAX(period) FROM (
            SELECT period FROM trx.area_statements WHERE block_id = :bid
            UNION ALL SELECT period FROM trx.block_productions WHERE block_id = :bid
        ) src
        WHERE CAST(:as_of AS date) IS NULL OR period <= :as_of
    """), {"bid": block_id, "as_of": as_of}).scalar()
    return period, False


def _triplet(actual, budget, census, *, whole_number: bool = False) -> dict:
    cast = whole if whole_number else lambda value: round(num(value), 2)
    return {"aktual": cast(actual), "budget": cast(budget), "sensus": cast(census)}


def get_block_detail(
    db: Session,
    blok_ref: str,
    tahun_tanam: int | None = None,
    ownership: str | None = None,
    bulan: int | None = None,
    tahun: int | None = None,
) -> dict:
    block_id = resolve_block_id(db, blok_ref)
    period, from_params = _resolve_detail_period(db, block_id, bulan, tahun)
    planting_filter = "COALESCE(a.planting_year, 0) = :tt" if tahun_tanam is not None else ""
    master_params: dict = {"bid": block_id}
    if tahun_tanam is not None:
        master_params["tt"] = tahun_tanam
    if period is not None:
        master_params["as_of"] = period

    master = db.execute(text(f"""
        SELECT bl.id, bl.code, bt.name AS block_type,
               dv.code AS division_code, es.code AS estate_code, es.name AS estate_name,
               co.code AS company_code, COALESCE(NULLIF(co.name, ''), co.code) AS company_name,
               sar.code AS area_code, sar.name AS area_name,
               st.planting_year, st.planting_month, st.planted_area_ha, st.land_area_ha,
               st.tree_count, st.sph,
               ps.code AS planting_status, so.name AS soil_type, tp.name AS topography,
               {SEED_VARIETIES_OF_STATEMENT} AS seed_varieties
        FROM master.blocks bl {BLOCK_JOINS}
        {statement_as_of_join("as_of" if period is not None else None, planting_filter, exact=period is not None)}
        WHERE bl.id = :bid
    """), master_params).mappings().one()

    prod = db.execute(text("""
        SELECT COALESCE(SUM(ffb_actual_kg), 0) AS tbs_aktual,
               COALESCE(SUM(ffb_budget_kg), 0) AS tbs_budget,
               COALESCE(SUM(ffb_census_kg), 0) AS tbs_sensus,
               COALESCE(SUM(bunches_actual), 0) AS jjg_aktual,
               COALESCE(SUM(bunches_budget), 0) AS jjg_budget,
               COALESCE(SUM(bunches_census), 0) AS jjg_sensus,
               COALESCE(AVG(bjr_actual), 0) AS bjr_aktual,
               COALESCE(AVG(bjr_budget), 0) AS bjr_budget,
               COALESCE(AVG(bjr_census), 0) AS bjr_sensus
        FROM trx.block_productions
        WHERE block_id = :bid AND period = :as_of
    """), {"bid": block_id, "as_of": period}).mappings().one() if period is not None else {}

    luas = round(num(master["planted_area_ha"]), 2) if master["planted_area_ha"] is not None else 0.0
    tbs = _triplet(prod.get("tbs_aktual"), prod.get("tbs_budget"), prod.get("tbs_sensus"))
    jjg = _triplet(prod.get("jjg_aktual"), prod.get("jjg_budget"), prod.get("jjg_sensus"), whole_number=True)
    bjr = _triplet(prod.get("bjr_aktual"), prod.get("bjr_budget"), prod.get("bjr_sensus"))
    yield_row = {
        "aktual": _yield_ton_ha(tbs["aktual"], luas),
        "budget": _yield_ton_ha(tbs["budget"], luas),
        "sensus": _yield_ton_ha(tbs["sensus"], luas),
    }
    shown_year = tahun if from_params else (period.year if period is not None else tahun)
    shown_month = bulan if from_params else (period.month if period is not None else bulan)

    return {
        "status": "success",
        "message": f"Detail data blok {master['code']} berhasil dimuat.",
        "mode": "PERIODE_BULAN_TAHUN",
        "periode": {
            "bulan": shown_month,
            "tahun": shown_year,
            "label_periode": f"Tahun {shown_year}" if shown_year else "Belum ada data",
        },
        "informasi_blok": {
            "blok_id": master["id"],
            "nama_blok": f"Blok {master['code']}",
            "kode_blok": master["code"],
            "tipe_blok": master["block_type"] or ownership,
            "tahun_tanam": master["planting_year"],
            "bulan_tanam": MONTH_ABBR.get(master["planting_month"]),
            "jenis_bibit": master["seed_varieties"],
            "status_tanam": master["planting_status"],
            "jenis_topografi": master["topography"],
            "jenis_tanah": master["soil_type"],
            "luas_tanam": luas,
            "luas_tanah": round(num(master["land_area_ha"]), 2) if master["land_area_ha"] is not None else 0.0,
            "pokok": whole(master["tree_count"]) if master["tree_count"] is not None else 0,
            "sph": round(num(master["sph"]), 2) if master["sph"] is not None else 0.0,
            "tbs": tbs,
            "jjg": jjg,
            "bjr": bjr,
            "yield": yield_row,
            "gap_act_bgt": _gap_pair(yield_row["aktual"], yield_row["budget"]),
            "gap_act_sns": _gap_pair(yield_row["aktual"], yield_row["sensus"]),
            "hierarki": {
                "kode_area": master["area_code"], "nama_area": master["area_name"],
                "kode_pt": master["company_code"], "nama_pt": master["company_name"],
                "kode_est": master["estate_code"], "nama_estate": master["estate_name"],
                "kode_afd": master["division_code"], "nama_afd": master["division_code"],
            },
        },
    }
