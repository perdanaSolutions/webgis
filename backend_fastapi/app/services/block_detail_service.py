"""
Detail popup saat blok diklik di peta: master + hierarki, snapshot area
statement, akumulasi produksi TBS setahun, dan daftar rotasi panen.

Perbedaan dari backend lama (sengaja):
- Area statement adalah SNAPSHOT bulanan per blok, jadi yang ditampilkan
  adalah baris terbaru (<= periode diminta), bukan penjumlahan semua bulan
  (versi lama menjumlah 12 baris bulanan sehingga luas terlihat 12x lipat).
- Produksi diakumulasi untuk SATU tahun (tahun diminta, atau tahun data
  produksi terbaru), bukan seluruh riwayat blok.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.services.block_filter import BLOCK_JOINS, BLOCK_REF_MATCH, SEED_VARIETIES_OF_STATEMENT, statement_as_of_join
from app.utils.parsing import MONTH_ABBR, json_safe, num, whole
from app.utils.period import as_of_period, period_label, to_period
from app.services.history_service import block_production_history, gap_category, gap_pct


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


def _statement_block(r: dict) -> dict | None:
    if r["st_id"] is None:
        return None
    totals = {
        "count_records": 1,
        "luas_tanam": num(r["planted_area_ha"]), "luas_tanah": num(r["land_area_ha"]),
        "total_pokok": whole(r["tree_count"]), "sph": num(r["sph"]),
        "pct_tanah_datar": num(r["pct_flat"]), "pct_berbukit": num(r["pct_hilly"]),
        "pct_gelombang": num(r["pct_undulating"]), "pct_curam": num(r["pct_steep"]),
    }
    return {
        "tahun": r["st_period"].year,
        "periode": period_label(r["st_period"]),
        "groups": [{
            "group_keys": {
                "status_tanam": r["planting_status"],
                "bulan_tanam": MONTH_ABBR.get(r["planting_month"]),
                "tahun_tanam": r["planting_year"],
                "jenis_bibit": r["seed_varieties"],
                "jenis_topografi": r["topography"],
                "jenis_tanah": r["soil_type"],
            },
            "totals": totals,
        }],
        "grand_total": totals,
    }


def _resolve_requested_period(db: Session, block_id: int, bulan: int | None, tahun: int | None) -> tuple[date | None, bool]:
    """
    Popup mengirim bulan+tahun. Kalau periode itu punya transaksi, pakai persis
    periode itu (SPESIFIK). Kalau tidak, jatuh ke transaksi paling akhir (LATEST)
    supaya angka yang tampil bukan nol di tahun kosong.
    Tanpa bulan+tahun, perilaku lama: statement terbaru tanpa batas atas.
    """
    if bulan is None or tahun is None:
        return as_of_period(bulan, tahun), False

    requested = to_period(bulan, tahun)
    row = db.execute(text("""
        SELECT BOOL_OR(period = :p) AS exact, MAX(period) AS latest
        FROM (
            SELECT period FROM trx.area_statements WHERE block_id = :bid
            UNION ALL SELECT period FROM trx.block_productions WHERE block_id = :bid
            UNION ALL SELECT period FROM trx.harvest_rotations WHERE block_id = :bid
        ) src
    """), {"bid": block_id, "p": requested}).mappings().one()
    if row["exact"]:
        return requested, True
    return row["latest"], False


def get_block_detail(
    db: Session,
    blok_ref: str,
    tahun_tanam: int | None = None,
    ownership: str | None = None,
    bulan: int | None = None,
    tahun: int | None = None,
) -> dict:
    block_id = resolve_block_id(db, blok_ref)
    period_requested = bulan is not None and tahun is not None
    as_of, period_exact = _resolve_requested_period(db, block_id, bulan, tahun)
    params = {"bid": block_id, "as_of": as_of, "tt": tahun_tanam}

    master = db.execute(text(f"""
        SELECT bl.id, bl.code, bt.name AS block_type,
               dv.code AS division_code, es.code AS estate_code, es.name AS estate_name,
               co.code AS company_code, COALESCE(NULLIF(co.name, ''), co.code) AS company_name,
               sar.code AS area_code, sar.name AS area_name,
               st.id AS st_id, st.period AS st_period, st.planting_year, st.planting_month,
               st.planted_area_ha, st.land_area_ha, st.tree_count, st.sph,
               st.pct_flat, st.pct_hilly, st.pct_undulating, st.pct_steep,
               ps.code AS planting_status, so.name AS soil_type, tp.name AS topography,
               {SEED_VARIETIES_OF_STATEMENT} AS seed_varieties
        FROM master.blocks bl {BLOCK_JOINS}
        {statement_as_of_join("as_of" if as_of else None, "a.planting_year = :tt" if tahun_tanam else "")}
        WHERE bl.id = :bid
    """), params).mappings().one()

    # Produksi & rotasi mengikuti periode yang dipakai. Kalau filter bulan+tahun
    # kosong, tetap tahun produksi terbaru (perilaku lama).
    if period_requested and as_of is not None:
        year, year_end = as_of.year, as_of
    else:
        year = tahun or db.execute(
            text(f"SELECT extract(year FROM max(period))::int FROM trx.block_productions WHERE block_id = :bid "
                 f"{'AND period <= :as_of' if as_of else ''}"),
            params,
        ).scalar()
        year_end = as_of if (as_of and year and as_of.year == year) else (date(year, 12, 1) if year else None)
    year_start = date(year, 1, 1) if year else None
    range_params = {"bid": block_id, "start": year_start, "end": year_end}

    prod = db.execute(text("""
        SELECT SUM(ffb_actual_kg) AS tbs_aktual, SUM(ffb_budget_kg) AS tbs_budget, SUM(ffb_census_kg) AS tbs_sensus,
               SUM(bunches_actual) AS jjg_aktual, SUM(bunches_budget) AS jjg_budget, SUM(bunches_census) AS jjg_sensus,
               CASE WHEN SUM(bunches_actual) > 0 THEN SUM(ffb_actual_kg) / SUM(bunches_actual) ELSE AVG(bjr_actual) END AS bjr_aktual,
               AVG(bjr_budget) AS bjr_budget, AVG(bjr_census) AS bjr_sensus
        FROM trx.block_productions
        WHERE block_id = :bid AND period BETWEEN :start AND :end
    """), range_params).mappings().one() if year else {}

    rotations = db.execute(text("""
        SELECT h.id, h.period, h.rotation_no, h.interval_days, rs.name AS status, h.area_ha, h.tree_count
        FROM trx.harvest_rotations h LEFT JOIN ref.rotation_statuses rs ON rs.id = h.rotation_status_id
        WHERE h.block_id = :bid AND h.period BETWEEN :start AND :end
        ORDER BY h.period
    """), range_params).mappings().all() if year else []

    tbs_act, tbs_bgt = num(prod.get("tbs_aktual")), num(prod.get("tbs_budget"))
    jjg_act = whole(prod.get("jjg_aktual"))
    trees = whole(master["tree_count"])
    if tbs_bgt > 0:
        achievement = round(tbs_act / tbs_bgt * 100, 2)
        category = "HIGH YIELD" if achievement >= 100 else "MEDIUM YIELD" if achievement >= 85 else "LOW YIELD"
    else:
        achievement, category = 0.0, "NO TARGET"

    # Yield & varians: rumus dan kunci sama dengan GET /history (dihitung dari data DB).
    luas = num(master["planted_area_ha"])

    def yield_ha(kg):
        return num(kg) / 1000 / luas if luas and kg is not None else None

    y_act, y_bgt, y_sns = yield_ha(prod.get("tbs_aktual")), yield_ha(prod.get("tbs_budget")), yield_ha(prod.get("tbs_sensus"))
    gap_bgt, gap_sns = gap_pct(y_act, y_bgt), gap_pct(y_act, y_sns)

    def rnd(v):
        return round(v, 2) if v is not None else None

    varians = {
        "luas": round(luas, 2), "ton": round(tbs_act / 1000, 2),
        "ton_ha": round(y_act, 2) if y_act is not None else 0.0,
        "ton_ha_budget": rnd(y_bgt), "ton_ha_sensus": rnd(y_sns),
        "gap_budget_pct": rnd(gap_bgt), "gap_sensus_pct": rnd(gap_sns),
        "kategori_budget": gap_category(gap_bgt), "kategori_sensus": gap_category(gap_sns),
    }

    return {
        "status": "success",
        "message": f"Detail data blok {master['code']} berhasil dimuat.",
        "mode": "SPESIFIK_TAHUN_TANAM" if period_exact else "LATEST_TAHUN_TANAM",
        "periode": {
            "bulan": (as_of.month if as_of is not None else None) if period_requested else bulan,
            "tahun": (as_of.year if as_of is not None else None) if period_requested else year,
            "label_periode": f"Tahun {year}" + (f" s/d bulan {year_end.month}" if year_end and year_end.month < 12 else "")
            if year else "Belum ada data produksi",
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
            "hierarki": {
                "kode_area": master["area_code"], "nama_area": master["area_name"],
                "kode_pt": master["company_code"], "nama_pt": master["company_name"],
                "kode_est": master["estate_code"], "nama_estate": master["estate_name"],
                "kode_afd": master["division_code"], "nama_afd": master["division_code"],
            },
        },
        "areal_statement": _statement_block(master),
        "produksi_tbs": {
            **varians,
            "tbs": {
                "aktual": tbs_act, "budget": tbs_bgt, "sensus": num(prod.get("tbs_sensus")),
                "gap": round(tbs_act - tbs_bgt, 2), "pct_achievement": achievement, "kategori_yield": category,
            },
            "janjang": {"aktual": jjg_act, "budget": whole(prod.get("jjg_budget")), "sensus": whole(prod.get("jjg_sensus"))},
            "bjr": {
                "aktual": round(num(prod.get("bjr_aktual")), 2),
                "budget": round(num(prod.get("bjr_budget")), 2),
                "sensus": round(num(prod.get("bjr_sensus")), 2),
            },
            "kpi_per_pokok": {
                "kg_pkk": round(tbs_act / trees, 2) if trees else 0.0,
                "jjg_pkk": round(jjg_act / trees, 2) if trees else 0.0,
            },
            # Struktur yang sama dengan GET /history?table=trx_produksi_tbs (slope, data_histori, ringkasan gap).
            **block_production_history(db, block_id, year),
        },
        "rotasi_pusingan": {
            "total_kegiatan": len(rotations),
            "daftar_rotasi": [
                {
                    "id_rotasi_pusingan": r["id"], "tanggal": json_safe(r["period"]),
                    "rotasi_ke": json_safe(r["rotation_no"]), "pusingan_hari": r["interval_days"],
                    "status_pusingan": r["status"], "luas": num(r["area_ha"]), "pokok": whole(r["tree_count"]),
                }
                for r in rotations
            ],
        },
    }
