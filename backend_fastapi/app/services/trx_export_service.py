"""
Export data transaksi (trx.*) yang sudah tersimpan ke Excel (.xlsx).

Header kolom sama persis dengan template import, sehingga file hasil export bisa diedit lalu diunggah ulang
lewat halaman Upload Transaksi (pola upsert per blok & bulan).

Workbook: sheet "Data" (sheet pertama, yang dibaca import) + sheet "Info" (filter & waktu export).
Data dibatasi wilayah yang boleh diakses user (hak akses data role) dan filter yang dikirim.
"""
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request
from app.services.block_filter import BLOCK_JOINS, BlockFilter
from app.services.upload.failed_export import safe_cell

WIB = ZoneInfo("Asia/Jakarta")
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_ROWS = 1_048_575  # batas baris Excel dikurangi 1 baris header
FETCH_SIZE = 5_000


@dataclass(frozen=True)
class ExportKind:
    slug: str            # dipakai di nama file
    label: str
    table: str           # nama tabel (juga kunci hak akses transaksi)
    grant_alias: str     # alias hak akses transaksi lama
    headers: tuple[str, ...]
    select_sql: str      # kolom SELECT, urutan sama dengan headers
    extra_joins: str = ""


_AREA_STATEMENT = ExportKind(
    slug="areal-statement",
    label="Areal Statement",
    table="trx.area_statements",
    grant_alias="trx_areal_statement",
    headers=("Year", "Month", "Group", "AreaCode", "CompanyCode", "Estate", "UnitCode", "EstateShortName",
             "DivisionCode", "KodeBlok", "TipeBlok", "StatusTanam", "TahunTanam", "BulanTanam", "LuasTanam",
             "LuasTanah", "TotalPokok", "SPH", "JenisBibit", "JenisTopografi", "TanahDatar", "Berbukit",
             "Gelombang", "Curam", "JenisTanah"),
    select_sql="""
        co_group.code, sar.code, co.code, es.name, es.code, es.short_name, dv.code, bl.code, bt.name, ps.code,
        t.planting_year, t.planting_month, t.planted_area_ha, t.land_area_ha, t.tree_count, t.sph,
        (SELECT string_agg(sv.name, ', ' ORDER BY sv.name)
           FROM trx.area_statement_seed_varieties x JOIN ref.seed_varieties sv ON sv.id = x.seed_variety_id
          WHERE x.area_statement_id = t.id),
        tp.name, t.pct_flat, t.pct_hilly, t.pct_undulating, t.pct_steep, so.name
    """,
    extra_joins="""
        LEFT JOIN master.areas sar ON sar.id = t.area_id
        LEFT JOIN ref.planting_statuses ps ON ps.id = t.planting_status_id
        LEFT JOIN ref.soil_types so ON so.id = t.soil_type_id
        LEFT JOIN ref.topography_types tp ON tp.id = t.topography_type_id
    """,
)

_PRODUCTION = ExportKind(
    slug="produksi-tbs",
    label="Produksi TBS",
    table="trx.block_productions",
    grant_alias="trx_produksi_tbs",
    headers=("Year", "Month", "UnitCode", "DivisionCode", "KodeBlok", "TbsAktual", "TbsBudget", "TbsSensus",
             "JanjangAktual", "JanjangBudget", "JanjangSensus", "BjrAktual", "BjrBudget", "BjrSensus"),
    select_sql="""
        es.code, dv.code, bl.code, t.ffb_actual_kg, t.ffb_budget_kg, t.ffb_census_kg, t.bunches_actual,
        t.bunches_budget, t.bunches_census, t.bjr_actual, t.bjr_budget, t.bjr_census
    """,
)

# "Periode" = tahun dan "Bulan" = angka bulan, sama seperti yang diterima import rotasi.
_ROTATION = ExportKind(
    slug="rotasi-pusingan",
    label="Rotasi & Pusingan",
    table="trx.harvest_rotations",
    grant_alias="trx_rotasi_pusingan",
    headers=("Periode", "Bulan", "Area", "PT", "Estate", "Afdeling", "Blok", "Luas", "Pokok", "Rotasi", "Pusingan",
             "Status Pusingan", "Tanggal"),
    select_sql="""
        COALESCE(est_area.code, est_area.name), co.name, es.name, dv.code, bl.code, t.area_ha, t.tree_count,
        t.rotation_no, t.interval_days, rs.name, to_char(t.period, 'YYYY-MM-DD')
    """,
    extra_joins="LEFT JOIN ref.rotation_statuses rs ON rs.id = t.rotation_status_id",
)

EXPORT_KINDS = {k.slug: k for k in (_AREA_STATEMENT, _PRODUCTION, _ROTATION)}


@dataclass
class ExportPeriod:
    year: int | None = None
    month: int | None = None

    def __post_init__(self):
        if self.month is not None and self.year is None:
            raise bad_request("Parameter tahun wajib diisi bila bulan diisi.", "tahun")

    def where(self) -> tuple[list[str], dict]:
        clauses, params = [], {}
        if self.year is not None:
            clauses.append("t.period >= :p_from AND t.period < :p_to")
            if self.month is None:
                params.update(p_from=date(self.year, 1, 1), p_to=date(self.year + 1, 1, 1))
            else:
                nxt = date(self.year + 1, 1, 1) if self.month == 12 else date(self.year, self.month + 1, 1)
                params.update(p_from=date(self.year, self.month, 1), p_to=nxt)
        return clauses, params

    def label(self) -> str:
        if self.year is None:
            return "semua-periode"
        return f"{self.year}-{self.month:02d}" if self.month else str(self.year)


def _query(kind: ExportKind, flt: BlockFilter, period: ExportPeriod) -> tuple[str, str, dict]:
    """(from_where_sql, order_sql, params) untuk satu jenis export."""
    clauses, params = flt.where()
    period_clauses, period_params = period.where()
    clauses += period_clauses
    params.update(period_params)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    from_sql = f"""
        FROM {kind.table} t
        JOIN master.blocks bl ON bl.id = t.block_id
        {BLOCK_JOINS}
        {kind.extra_joins}
        {where_sql}
    """
    return from_sql, "ORDER BY t.period, es.code, dv.code, bl.code", params


def count_rows(db: Session, kind: ExportKind, flt: BlockFilter, period: ExportPeriod) -> int:
    from_sql, _, params = _query(kind, flt, period)
    return int(db.execute(text(f"SELECT count(*) {from_sql}"), params).scalar_one())


def _cell(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return safe_cell(value)


def build_workbook(db: Session, kind: ExportKind, flt: BlockFilter, period: ExportPeriod,
                   filters: dict[str, Any], total: int) -> bytes:
    from_sql, order_sql, params = _query(kind, flt, period)
    sql = (f"SELECT extract(year FROM t.period)::int, extract(month FROM t.period)::int, {kind.select_sql} "
           f"{from_sql} {order_sql}")

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Data")
    ws.freeze_panes = "A2"
    bold, fill = Font(bold=True), PatternFill("solid", fgColor="F3E9DC")
    header_cells = []
    for name in kind.headers:
        cell = WriteOnlyCell(ws, value=name)
        cell.font, cell.fill = bold, fill
        header_cells.append(cell)
    ws.append(header_cells)

    result = db.execute(text(sql).execution_options(stream_results=True, yield_per=FETCH_SIZE), params)
    for row in result:  # SELECT selalu diawali (tahun, bulan), sama dengan dua header pertama tiap jenis
        ws.append([_cell(v) for v in row])

    info = wb.create_sheet("Info")
    info.append([WriteOnlyCell(info, value="Keterangan"), WriteOnlyCell(info, value="Nilai")])
    info.append(["Jenis data", kind.label])
    info.append(["Sumber tabel", kind.table])
    info.append(["Diekspor pada (WIB)", datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S")])
    info.append(["Jumlah baris", total])
    info.append(["Periode", period.label()])
    for key, value in filters.items():
        if value not in (None, ""):
            info.append([f"Filter {key}", safe_cell(value)])
    info.append([])
    info.append(["Catatan", "Sheet Data memakai header yang sama dengan template import, jadi file ini bisa "
                            "diedit lalu diunggah ulang di halaman Upload Transaksi (upsert per blok & bulan)."])

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def export_filename(kind: ExportKind, period: ExportPeriod, flt: BlockFilter) -> str:
    parts = [kind.slug, period.label()]
    for value in (flt.area, flt.kode_pt, flt.kode_est, flt.kode_afd):
        if value:
            parts.append("".join(ch for ch in value if ch.isalnum() or ch in "-_")[:30])
    parts.append(datetime.now(WIB).strftime("%Y%m%d-%H%M"))
    return "_".join(p for p in parts if p) + ".xlsx"


def export_kind(db: Session, kind: ExportKind, flt: BlockFilter, period: ExportPeriod,
                filters: dict[str, Any]) -> tuple[bytes, str]:
    total = count_rows(db, kind, flt, period)
    if total > MAX_ROWS:
        raise bad_request(
            f"Data terlalu banyak untuk satu file Excel ({total:,} baris, maksimal {MAX_ROWS:,}). "
            "Persempit dengan filter tahun, bulan, atau estate.".replace(",", "."), "tahun")
    return build_workbook(db, kind, flt, period, filters, total), export_filename(kind, period, flt)
