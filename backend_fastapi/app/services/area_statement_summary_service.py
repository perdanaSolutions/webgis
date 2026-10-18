"""
Ringkasan Areal Statement untuk card "Areal Statement" (format laporan peta areal statement):
- tanaman per status tanam (TM/TBM/LC) dan per tahun tanam;
- populasi tanaman per kelas kerapatan pokok (SPH);
- luas tanah blok dan selisihnya terhadap luas tanam (areal tidak tertanam di dalam blok).

Memakai SATU snapshot: periode areal statement terakhir s/d batas bulan/tahun (blok yang tidak dilaporkan
di periode itu tidak ikut), sama dengan GET /history?table=trx_areal_statement.
Areal non-tanam dari layer landuse menyusul; `non_tanam` dikirim null sampai datanya tersedia.
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_filter import BlockFilter
from app.utils.parsing import num
from app.utils.period import period_label

STATUS_ORDER = ("TM", "TBM", "LC")
STATUS_LABEL = {"TM": "Tanaman Menghasilkan", "TBM": "Tanaman Belum Menghasilkan", "LC": "Pembukaan Lahan (LC)"}

# Kelas kerapatan pokok (pokok/ha) seperti laporan areal statement: > 136, 130 - 135, < 130.
POPULATION_CLASSES = (
    ("ATAS_136", "Di atas 136 pokok/ha", 136, None),
    ("ANTARA_130_135", "130 - 135 pokok/ha", 130, 136),
    ("BAWAH_130", "Di bawah 130 pokok/ha", None, 130),
)


def _population_class(sph: float | None) -> str | None:
    if sph is None:
        return None
    for code, _, low, high in POPULATION_CLASSES:
        if (low is None or sph >= low) and (high is None or sph < high):
            return code
    return None


def _ha(value) -> float:
    return round(num(value), 2)


def _pct(part: float, total: float) -> float:
    return round(part / total * 100, 2) if total else 0.0


def area_statement_summary(db: Session, flt: BlockFilter, as_of: date | None) -> dict:
    blocks_sql, params = flt.block_ids_subquery()
    period_sql = "AND a.period <= :as_of" if as_of else ""
    rows = db.execute(text(f"""
        WITH scoped AS (
            SELECT a.* FROM trx.area_statements a
            WHERE a.block_id IN ({blocks_sql}) {period_sql}
        ),
        snap AS (SELECT * FROM scoped WHERE period = (SELECT max(period) FROM scoped))
        SELECT s.period, s.block_id, upper(ps.code) AS status, COALESCE(s.planting_year, 0)::int AS tahun_tanam,
               s.planted_area_ha, s.land_area_ha, s.tree_count,
               COALESCE(s.sph, s.tree_count / NULLIF(s.planted_area_ha, 0)) AS sph
        FROM snap s LEFT JOIN ref.planting_statuses ps ON ps.id = s.planting_status_id
    """), {**params, "as_of": as_of}).mappings().all()

    period = rows[0]["period"] if rows else None
    planted = sum(num(r["planted_area_ha"]) for r in rows)
    land = sum(num(r["land_area_ha"]) for r in rows)
    trees = sum(int(r["tree_count"] or 0) for r in rows)

    by_status: dict[str, dict] = {}
    by_year: dict[int, float] = {}
    by_class: dict[str | None, dict] = {}
    for r in rows:
        luas = num(r["planted_area_ha"])
        status = r["status"] or "TANPA_STATUS"
        item = by_status.setdefault(status, {"jumlah_blok": 0, "luas_tanam": 0.0, "luas_tanah": 0.0, "pokok": 0})
        item["jumlah_blok"] += 1
        item["luas_tanam"] += luas
        item["luas_tanah"] += num(r["land_area_ha"])
        item["pokok"] += int(r["tree_count"] or 0)
        by_year[r["tahun_tanam"]] = by_year.get(r["tahun_tanam"], 0.0) + luas
        sph = float(r["sph"]) if r["sph"] is not None and luas > 0 else None
        cls = by_class.setdefault(_population_class(sph), {"jumlah_blok": 0, "luas_tanam": 0.0})
        cls["jumlah_blok"] += 1
        cls["luas_tanam"] += luas

    statuses = sorted(by_status, key=lambda s: (STATUS_ORDER.index(s) if s in STATUS_ORDER else len(STATUS_ORDER), s))
    no_class = by_class.get(None, {"jumlah_blok": 0, "luas_tanam": 0.0})
    return {
        "periode": period_label(period) if period else None,
        "bulan": period.month if period else None,
        "tahun": period.year if period else None,
        "tanam": {
            "total_luas_tanam": _ha(planted),
            "total_luas_tanah": _ha(land),
            "total_pokok": trees,
            "sph_rata_rata": round(trees / planted, 2) if planted else 0.0,
            "jumlah_blok": len(rows),
            "per_status": [
                {"status": s, "label": STATUS_LABEL.get(s, s), "jumlah_blok": by_status[s]["jumlah_blok"],
                 "luas_tanam": _ha(by_status[s]["luas_tanam"]), "luas_tanah": _ha(by_status[s]["luas_tanah"]),
                 "pokok": by_status[s]["pokok"], "persen": _pct(by_status[s]["luas_tanam"], planted)}
                for s in statuses
            ],
            "per_tahun_tanam": [
                {"tahun_tanam": y, "luas_tanam": _ha(v), "persen": _pct(v, planted)} for y, v in sorted(by_year.items())
            ],
        },
        "populasi": {
            "kelas": [
                {"kode": code, "label": label, "batas_bawah": low, "batas_atas": high,
                 "jumlah_blok": by_class.get(code, {}).get("jumlah_blok", 0),
                 "luas_tanam": _ha(by_class.get(code, {}).get("luas_tanam", 0.0)),
                 "persen": _pct(by_class.get(code, {}).get("luas_tanam", 0.0), planted)}
                for code, label, low, high in POPULATION_CLASSES
            ],
            "tanpa_sph": {"jumlah_blok": no_class["jumlah_blok"], "luas_tanam": _ha(no_class["luas_tanam"])},
        },
        "tidak_tertanam_dalam_blok": {
            "luas": _ha(max(land - planted, 0.0)),
            "keterangan": "Luas tanah blok dikurangi luas tanam (jalan, parit, dan areal tidak tertanam di dalam blok).",
        },
        "non_tanam": None,
    }
