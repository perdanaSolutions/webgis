"""Grafik Produksi TBS (ton) per Grup, Area, dan Estate untuk kartu Produksi TBS di peta.

Rentang mengikuti aturan `produksi_tbs` di GeoJSON (`map_service.resolve_trx_window`):
- year_to_date + bulan -> Januari s/d bulan itu; tanpa year_to_date -> bulan itu saja;
- tanpa bulan -> bulan produksi terakhir (Year to Date: Januari s/d bulan produksi terakhir).
Pembanding "tahun lalu" = rentang bulan yang sama setahun sebelumnya.

Pengelompokan memakai master SAAT INI (grup milik PT, area milik estate), sama dengan filter peta.
Luas tanam & RUT = areal statement terbaru di tahun yang sama s/d akhir rentang, hanya blok yang punya
produksi di rentang itu. RUT (rata-rata umur tanaman, tahun) = Σ(luas x (tahun akhir rentang - tahun tanam)) / Σluas,
hanya blok yang tahun tanamnya terisi.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.block_filter import BlockFilter
from app.services.map_service import TrxWindow, resolve_trx_window
from app.utils.parsing import num
from app.utils.period import period_label

_NO_GROUP = "Tanpa grup"
_NO_AREA = "Tanpa area"


@dataclass
class _Acc:
    kode: str | None
    nama: str
    aktual_kg: float = 0.0
    budget_kg: float = 0.0
    tahun_lalu_kg: float = 0.0
    luas: float = 0.0
    umur_luas: float = 0.0
    luas_umur: float = 0.0
    extra: dict = field(default_factory=dict)

    def add(self, row) -> None:
        self.aktual_kg += num(row["aktual_kg"])
        self.budget_kg += num(row["budget_kg"])
        self.tahun_lalu_kg += num(row["tahun_lalu_kg"])
        if row["ada_produksi"]:
            luas = num(row["luas"])
            self.luas += luas
            if row["umur"] is not None and luas > 0:
                self.umur_luas += luas * num(row["umur"])
                self.luas_umur += luas

    def payload(self) -> dict:
        aktual = self.aktual_kg / 1000
        budget = self.budget_kg / 1000
        lalu = self.tahun_lalu_kg / 1000
        return {
            "kode": self.kode,
            "nama": self.nama,
            **self.extra,
            "aktual_ton": round(aktual, 2),
            "budget_ton": round(budget, 2),
            "aktual_tahun_lalu_ton": round(lalu, 2),
            "aktual_ton_ha": round(aktual / self.luas, 2) if self.luas else None,
            "budget_ton_ha": round(budget / self.luas, 2) if self.luas else None,
            "var_budget_ton": round(aktual - budget, 2),
            "var_budget_pct": _pct(aktual, budget),
            "var_tahun_lalu_ton": round(aktual - lalu, 2),
            "var_tahun_lalu_pct": _pct(aktual, lalu),
            "luas_tanam": round(self.luas, 2),
            "rut": round(self.umur_luas / self.luas_umur, 2) if self.luas_umur else None,
        }


def _pct(actual: float, target: float) -> float | None:
    """(aktual - pembanding) / pembanding %; None bila pembanding kosong/0."""
    if not target:
        return None
    value = round((actual - target) / target * 100, 2)
    return 0.0 if value == 0 else value


def _previous_year(window: TrxWindow) -> tuple[date, date]:
    return window.start.replace(year=window.start.year - 1), window.end.replace(year=window.end.year - 1)


def _empty(window: TrxWindow | None) -> dict:
    return {
        "periode": _periode(window),
        "group_produksi_ton": {"total": None, "by_group": [], "by_area": [], "by_estate": []},
    }


def _periode(window: TrxWindow | None) -> dict | None:
    if window is None:
        return None
    lalu_awal, lalu_akhir = _previous_year(window)
    return {
        "periode_awal": period_label(window.start),
        "periode_akhir": period_label(window.end),
        "year_to_date": window.year_to_date,
        "tahun_lalu_awal": period_label(lalu_awal),
        "tahun_lalu_akhir": period_label(lalu_akhir),
    }


def _sorted(accs: dict) -> list[dict]:
    items = [acc.payload() for acc in accs.values()]
    return sorted(items, key=lambda item: (-item["aktual_ton"], item["nama"]))


def production_groups(db: Session, flt: BlockFilter, bulan: int | None, tahun: int | None,
                      year_to_date: bool) -> dict:
    """{periode, group_produksi_ton: {total, by_group, by_area, by_estate}} untuk blok dalam filter."""
    joins, where_sql, params = flt.sql()
    block_ids = [row[0] for row in db.execute(
        text(f"SELECT bl.id FROM master.blocks bl {joins} {where_sql}"), params,
    ).all()]
    if not block_ids:
        return _empty(None)
    window = resolve_trx_window(db, block_ids, bulan, tahun, year_to_date)
    if window is None:
        return _empty(None)
    lalu_awal, lalu_akhir = _previous_year(window)

    rows = db.execute(text(f"""
        WITH scoped AS (
            SELECT bl.id AS block_id,
                   co_group.code AS grup_kode,
                   est_area.code AS area_kode, est_area.name AS area_nama,
                   es.code AS estate_kode, es.short_name AS estate_singkat, es.name AS estate_nama
            FROM master.blocks bl {joins}
            {where_sql}
        ),
        prod AS (
            SELECT p.block_id,
                   SUM(p.ffb_actual_kg) FILTER (WHERE p.period BETWEEN :start AND :end) AS aktual_kg,
                   SUM(p.ffb_budget_kg) FILTER (WHERE p.period BETWEEN :start AND :end) AS budget_kg,
                   SUM(p.ffb_actual_kg) FILTER (WHERE p.period BETWEEN :prev_start AND :prev_end) AS tahun_lalu_kg,
                   bool_or(p.period BETWEEN :start AND :end) AS ada_produksi
            FROM trx.block_productions p
            WHERE p.block_id IN (SELECT block_id FROM scoped)
              AND (p.period BETWEEN :start AND :end OR p.period BETWEEN :prev_start AND :prev_end)
            GROUP BY p.block_id
        ),
        stmt AS (
            SELECT DISTINCT ON (a.block_id) a.block_id, a.planted_area_ha, a.planting_year
            FROM trx.area_statements a
            WHERE a.block_id IN (SELECT block_id FROM prod) AND a.period BETWEEN :year_start AND :end
            ORDER BY a.block_id, a.period DESC
        )
        SELECT s.grup_kode, s.area_kode, s.area_nama, s.estate_kode, s.estate_singkat, s.estate_nama,
               p.aktual_kg, p.budget_kg, p.tahun_lalu_kg, p.ada_produksi,
               st.planted_area_ha AS luas,
               CASE WHEN st.planting_year > 0 THEN :end_year - st.planting_year END AS umur
        FROM scoped s
        JOIN prod p ON p.block_id = s.block_id
        LEFT JOIN stmt st ON st.block_id = s.block_id
    """), {
        **params,
        "start": window.start, "end": window.end,
        "prev_start": lalu_awal, "prev_end": lalu_akhir,
        "year_start": date(window.end.year, 1, 1), "end_year": window.end.year,
    }).mappings().all()

    total: _Acc | None = None
    groups: dict = {}
    areas: dict = {}
    estates: dict = {}
    for row in rows:
        # Estate/area/grup tanpa produksi di rentang ini (hanya tahun lalu) tetap dihitung agar
        # pembanding tahun lalu utuh, tetapi tidak ditampilkan sebagai bar sendiri (lihat filter di bawah).
        grup = row["grup_kode"]
        area = row["area_kode"]
        estate = row["estate_kode"]
        groups.setdefault(grup, _Acc(grup, grup or _NO_GROUP)).add(row)
        areas.setdefault(area, _Acc(area, row["area_nama"] or area or _NO_AREA)).add(row)
        estates.setdefault(estate, _Acc(
            estate, row["estate_singkat"] or estate, extra={"nama_lengkap": row["estate_nama"]},
        )).add(row)
        if total is None:
            total = _Acc("TOTAL", "")
        total.add(row)

    def shown(accs: dict) -> dict:
        return {key: acc for key, acc in accs.items() if acc.aktual_kg or acc.budget_kg}

    groups, areas, estates = shown(groups), shown(areas), shown(estates)
    if total is not None:
        total.nama = " + ".join(acc.nama for acc in sorted(groups.values(), key=lambda a: -a.aktual_kg)) or "Total"
    return {
        "periode": _periode(window),
        "group_produksi_ton": {
            "total": total.payload() if total is not None and groups else None,
            "by_group": _sorted(groups),
            "by_area": _sorted(areas),
            "by_estate": _sorted(estates),
        },
    }
