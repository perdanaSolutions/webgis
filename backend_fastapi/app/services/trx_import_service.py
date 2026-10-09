"""
Impor transaksi (file Excel atau JSON lewat API) ke skema trx v3:
    areal statement -> trx.area_statements (+ trx.area_statement_seed_varieties)
    produksi TBS    -> trx.block_productions
    rotasi pusingan -> trx.harvest_rotations

Ketiganya unik per (block_id, period), jadi impor = UPSERT: file yang sama
boleh diunggah ulang, baris duplikat di dalam file -> baris terakhir yang dipakai.
Validasi dilakukan di Python (sesuai CHECK constraint tabel), lalu data valid
dimuat lewat COPY ke tabel staging dan di-upsert dalam SATU transaksi.

Blok dicari dari (estate, afdeling, kode blok); kalau kolom estate/afdeling
tidak ada di file, dipakai kode blok saja selama kode itu unik di seluruh master.

Impor JSON memakai nama kolom yang sama dengan header Excel dan melewati
validasi + upsert yang sama persis; bedanya hanya sumber barisnya.
"""
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.upload.batch import final_status, finish_batch, start_batch
from app.services.upload.copy import copy_rows
from app.services.upload.resolvers import BlockIndex, RefResolver
from app.utils.excel import pick, read_excel_rows
from app.utils.parsing import clean_str, norm_key, to_float, to_int, to_month

ESTATE_COLUMNS = ("UnitCode", "EstateCode", "KodeEstate", "Kode Estate", "EstID", "EstateShortName", "Estate")
DIVISION_COLUMNS = ("DivisionCode", "Divisi", "Afdeling", "KodeAfdeling", "Kode Afdeling", "Afd")
BLOCK_COLUMNS = ("KodeBlok", "Kode Blok", "Blok", "kode_blok", "BlockCode")
MONTH_COLUMNS = ("Month", "Bulan", "bulan")
YEAR_COLUMNS = ("Year", "Tahun", "tahun", "Periode")


class RowError(ValueError):
    pass


@dataclass
class _CreatedValues:
    """Pencatat nilai master baru (antarmuka sama dengan RefResolver.created)."""

    created: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    groups: dict[tuple[int, date], list[tuple[int, dict]]] = field(default_factory=dict)  # (blok, periode) -> [(baris, nilai)]
    rows: list[dict] = field(default_factory=list)
    total: int = 0
    missing_block: int = 0
    invalid: int = 0
    duplicates_merged: int = 0
    conflicts: int = 0
    unmatched_samples: list[str] = field(default_factory=list)
    invalid_samples: list[str] = field(default_factory=list)
    conflict_samples: list[str] = field(default_factory=list)
    new_refs: dict[str, list[str]] = field(default_factory=dict)


# Pemilih baris untuk (blok, periode) yang muncul >1 kali di file:
# mengembalikan (baris terpilih | None bila konflik, jumlah baris yang dibuang).
Deduper = Callable[[list[tuple[int, dict]]], tuple[dict | None, str]]


def keep_last(rows: list[tuple[int, dict]]) -> tuple[dict | None, str]:
    distinct = {tuple(sorted((k, str(v)) for k, v in r.items())) for _, r in rows}
    return rows[-1][1], "identik" if len(distinct) == 1 else "ditimpa baris terakhir"


def _period(row: dict) -> date:
    tanggal = pick(row, "Tanggal", "tanggal", "Date")
    if isinstance(tanggal, str):  # JSON: tanggal ISO 'YYYY-MM-DD'
        try:
            tanggal = date.fromisoformat(tanggal.strip()[:10])
        except ValueError:
            pass
    month = to_month(pick(row, *MONTH_COLUMNS)) or (to_month(tanggal) if tanggal is not None else None)
    year = to_int(pick(row, *YEAR_COLUMNS)) or (getattr(tanggal, "year", None))
    if not month or not year or not 1900 <= year <= 2100:
        raise RowError("bulan/tahun periode tidak valid")
    return date(year, month, 1)


def _non_negative(value, label: str):
    if value is not None and value < 0:
        raise RowError(f"{label} tidak boleh negatif")
    return value


def _collect(db: Session, rows: list[dict], build: Callable[[dict], dict], dedupe: Deduper,
             first_row: int = 2) -> ImportResult:
    index = BlockIndex.load(db)
    result = ImportResult(total=len(rows))
    for number, row in enumerate(rows, start=first_row):  # Excel: baris 1 = header; JSON: item ke-1 = baris 1
        block_code = pick(row, *BLOCK_COLUMNS)
        if clean_str(block_code) is None:
            result.invalid += 1
            continue
        estate_refs = tuple(pick(row, c) for c in ESTATE_COLUMNS)
        division = pick(row, *DIVISION_COLUMNS)
        block_id = index.resolve(estate_refs, division, block_code, allow_code_only=True)
        if block_id is None:
            result.missing_block += 1
            if len(result.unmatched_samples) < 5:
                estate = next((e for e in estate_refs if e), "-")
                result.unmatched_samples.append(f"baris {number}: {estate}/{division or '-'}/{block_code}")
            continue
        try:
            period = _period(row)
            values = build(row)
        except RowError as exc:
            result.invalid += 1
            if len(result.invalid_samples) < 5:
                result.invalid_samples.append(f"baris {number}: {exc}")
            continue
        result.groups.setdefault((block_id, period), []).append((number, values))

    for (block_id, period), items in result.groups.items():
        if len(items) == 1:
            chosen = items[0][1]
        else:
            chosen, reason = dedupe(items)
            if chosen is None:
                result.conflicts += len(items)
                if len(result.conflict_samples) < 5:
                    result.conflict_samples.append(
                        f"baris {', '.join(str(n) for n, _ in items)} ({period.month}-{period.year}): {reason}")
                continue
            result.duplicates_merged += len(items) - 1
        result.rows.append({"block_id": block_id, "period": period, **chosen})
    return result


def _period_summary(periods: list[date]) -> dict:
    if not periods:
        return {"jumlah": 0}
    return {"dari": f"{periods[0].month}-{periods[0].year}", "sampai": f"{periods[-1].month}-{periods[-1].year}",
            "jumlah": len(periods)}


@dataclass(frozen=True)
class TrxKind:
    target: str
    label: str
    build_factory: Callable[[Session], tuple[Callable[[dict], dict], dict]]
    load: Callable[[Session, list[dict], UUID], dict]
    dedupe: Deduper = keep_last


def _run(db: Session, kind: TrxKind, *, rows: list[dict], source_type: str, source_name: str | None,
         user_id: UUID | None, first_row: int) -> dict:
    target, label = kind.target, kind.label
    batch_id = start_batch(db, source_type=source_type, target_table=target, source_name=source_name,
                           user_id=user_id, period=None, metadata={"jenis": label})
    try:
        build, refs = kind.build_factory(db)
        result = _collect(db, rows, build, kind.dedupe, first_row)
        result.new_refs = {name: r.created for name, r in refs.items() if r.created}
        written = kind.load(db, result.rows, batch_id) if result.rows else {"baru": 0, "diperbarui": 0}
        db.commit()
    except Exception as exc:
        db.rollback()
        finish_batch(db, batch_id, "FAILED", 0, str(exc)[:2000], {"jenis": label})
        raise

    success = len(result.rows)
    status = final_status(success + result.duplicates_merged, result.total)
    periods = sorted({r["period"] for r in result.rows})
    details = {
        "batch_id": str(batch_id),
        "total_baris_excel": result.total,
        "success_count": success,
        "data_baru": written["baru"],
        "data_diperbarui": written["diperbarui"],
        "data_tidak_berubah": success - written["baru"] - written["diperbarui"],
        "duplicate_in_file": result.duplicates_merged,
        "konflik_duplikat_tidak_dimuat": result.conflicts,
        "missing_blok_count": result.missing_block,
        "invalid_prop_count": result.invalid,
        "failed_error_count": 0,
        "periode_terisi": _period_summary(periods),
        "sample_unmatched_excel": result.unmatched_samples,
        "sample_invalid_rows": result.invalid_samples,
        "sample_konflik": result.conflict_samples,
        "nilai_referensi_baru": result.new_refs,
        "last_error_msg": None,
    }
    if len(periods) == 1:
        db.execute(text("UPDATE audit.upload_batches SET period = :p WHERE id = :id"), {"p": periods[0], "id": str(batch_id)})
    finish_batch(db, batch_id, status, written["baru"] + written["diperbarui"],
                 None if status == "SUCCESS" else "Sebagian baris tidak diimpor.", {"detail_statistik": details})
    return {"status": "success", "message": f"Proses impor {label} selesai.", "details": details}


def _upsert_changed(db: Session, table: str, stage: str, columns: tuple[str, ...], batch_id: UUID) -> dict:
    """
    UPSERT per (block_id, period) yang HANYA menyentuh baris yang nilainya berubah,
    sehingga impor ulang file yang sama tidak menulis ulang (dan tidak membanjiri log audit).
    """
    cols = ", ".join(columns)
    counts = db.execute(text(f"""
        WITH up AS (
            INSERT INTO {table} (block_id, period, {cols}, upload_batch_id)
            SELECT block_id, period, {cols}, :batch FROM {stage}
            ON CONFLICT (block_id, period) DO UPDATE SET
                {', '.join(f'{c} = EXCLUDED.{c}' for c in columns)}, upload_batch_id = EXCLUDED.upload_batch_id
            WHERE ({', '.join(f'{table}.{c}' for c in columns)}) IS DISTINCT FROM ({', '.join(f'EXCLUDED.{c}' for c in columns)})
            RETURNING (xmax = 0) AS inserted
        )
        SELECT count(*) FILTER (WHERE inserted) AS baru, count(*) FILTER (WHERE NOT inserted) AS diperbarui FROM up
    """), {"batch": str(batch_id)}).mappings().one()
    return dict(counts)


# =====================================================================
# AREAL STATEMENT
# =====================================================================

_AREA_STAGE = ("block_id", "period", "area_id", "planting_status_id", "planting_year", "planting_month", "soil_type_id",
               "topography_type_id", "planted_area_ha", "land_area_ha", "tree_count", "sph", "pct_flat", "pct_hilly",
               "pct_undulating", "pct_steep", "seed_ids", "block_type_id")
_SEED_SPLIT = re.compile(r"\s*(?:,|/|;|\+|&|\bdan\b)\s*", re.IGNORECASE)


def _pct(row: dict, *names: str) -> int | None:
    value = to_int(pick(row, *names))
    if value is not None and not 0 <= value <= 100:
        raise RowError(f"persentase {names[0]} harus 0-100")
    return value


def _area_statement_builder(db: Session):
    refs = {name: RefResolver(db, name) for name in
            ("planting_statuses", "soil_types", "topography_types", "seed_varieties", "block_types")}
    areas = {norm_key(k): i for i, code, name in db.execute(text("SELECT id, code, name FROM master.areas")).all()
             for k in (code, name)}
    new_areas = _CreatedValues()
    refs["areas"] = new_areas

    def area_id(value) -> int:
        key = norm_key(value)
        if not key:
            raise RowError("AreaCode kosong")
        if key not in areas:
            name = clean_str(value)
            areas[key] = db.execute(text("INSERT INTO master.areas (code, name) VALUES (:c, :n) RETURNING id"),
                                    {"c": name[:50], "n": name[:150]}).scalar_one()
            new_areas.created.append(name)
        return areas[key]

    def build(row: dict) -> dict:
        status_id = refs["planting_statuses"].resolve(pick(row, "StatusTanam", "Status Tanam", "status_tanam"))
        if status_id is None:
            raise RowError("StatusTanam kosong")
        planting_year = to_int(pick(row, "TahunTanam", "Tahun Tanam", "tahun_tanam")) or None  # 0 = belum ditanam (LC)
        planting_month = to_month(pick(row, "BulanTanam", "Bulan Tanam", "bulan_tanam"))
        if planting_year is not None and not 1900 <= planting_year <= 2100:
            raise RowError("TahunTanam di luar 1900-2100")
        if planting_month and planting_year is None:
            planting_month = None
        pcts = [_pct(row, "TanahDatar", "Pct Datar"), _pct(row, "Berbukit", "Pct Berbukit"),
                _pct(row, "Gelombang", "Pct Gelombang"), _pct(row, "Curam", "Pct Curam")]
        if sum(p or 0 for p in pcts) > 100:
            raise RowError("total persentase topografi > 100")
        seeds = clean_str(pick(row, "JenisBibit", "Jenis Bibit", "jenis_bibit"))
        seed_ids = sorted({refs["seed_varieties"].resolve(s) for s in _SEED_SPLIT.split(seeds) if s.strip()}) if seeds else []
        return {
            "area_id": area_id(pick(row, "AreaCode", "Area", "KodeArea")),
            "planting_status_id": status_id,
            "planting_year": planting_year,
            "planting_month": planting_month,
            "soil_type_id": refs["soil_types"].resolve(pick(row, "JenisTanah", "Jenis Tanah", "jenis_tanah")),
            "topography_type_id": refs["topography_types"].resolve(pick(row, "JenisTopografi", "Jenis Topografi", "jenis_topografi")),
            "planted_area_ha": _non_negative(to_float(pick(row, "LuasTanam", "Luas Tanam")), "LuasTanam"),
            "land_area_ha": _non_negative(to_float(pick(row, "LuasTanah", "Luas Tanah")), "LuasTanah"),
            "tree_count": _non_negative(to_float(pick(row, "TotalPokok", "Total Pokok")), "TotalPokok"),
            "sph": _non_negative(to_float(pick(row, "SPH", "Sph")), "SPH"),
            "pct_flat": pcts[0], "pct_hilly": pcts[1], "pct_undulating": pcts[2], "pct_steep": pcts[3],
            "seed_ids": [s for s in seed_ids if s is not None],
            "block_type_id": refs["block_types"].resolve(pick(row, "TipeBlok", "Tipe Blok", "Ownership")),
        }

    return build, refs


def _load_area_statements(db: Session, rows: list[dict], batch_id: UUID) -> dict:
    db.execute(text("""
        CREATE TEMP TABLE _as_stage (
            block_id bigint, period date, area_id bigint, planting_status_id smallint, planting_year smallint,
            planting_month smallint, soil_type_id smallint, topography_type_id smallint, planted_area_ha numeric,
            land_area_ha numeric, tree_count numeric, sph numeric, pct_flat smallint, pct_hilly smallint,
            pct_undulating smallint, pct_steep smallint, seed_ids smallint[], block_type_id smallint
        ) ON COMMIT DROP
    """))
    copy_rows(db, "_as_stage", _AREA_STAGE, ([r[c] for c in _AREA_STAGE] for r in rows))
    cols = tuple(c for c in _AREA_STAGE if c not in ("block_id", "period", "seed_ids", "block_type_id"))
    counts = _upsert_changed(db, "trx.area_statements", "_as_stage", cols, batch_id)

    # Varietas bibit: hapus yang tidak ada lagi di file, tambah yang baru (tanpa menyentuh yang sama).
    db.execute(text("""
        DELETE FROM trx.area_statement_seed_varieties sv
        USING trx.area_statements a JOIN _as_stage s ON s.block_id = a.block_id AND s.period = a.period
        WHERE sv.area_statement_id = a.id AND NOT (sv.seed_variety_id = ANY(s.seed_ids))
    """))
    db.execute(text("""
        INSERT INTO trx.area_statement_seed_varieties (area_statement_id, seed_variety_id)
        SELECT DISTINCT a.id, unnest(s.seed_ids)
        FROM _as_stage s JOIN trx.area_statements a ON a.block_id = s.block_id AND a.period = s.period
        ON CONFLICT DO NOTHING
    """))
    # Tipe blok (Inti/Plasma) adalah atribut master blok.
    db.execute(text("""
        UPDATE master.blocks bl SET block_type_id = s.block_type_id
        FROM (SELECT DISTINCT ON (block_id) block_id, block_type_id FROM _as_stage
              WHERE block_type_id IS NOT NULL ORDER BY block_id, period DESC) s
        WHERE bl.id = s.block_id AND bl.block_type_id IS DISTINCT FROM s.block_type_id
    """))
    return counts


AREA_STATEMENT = TrxKind("trx.area_statements", "areal statement", _area_statement_builder, _load_area_statements)


# =====================================================================
# PRODUKSI TBS
# =====================================================================

_PROD_COLUMNS = ("ffb_actual_kg", "ffb_budget_kg", "ffb_census_kg", "bunches_actual", "bunches_budget", "bunches_census",
                 "bjr_actual", "bjr_budget", "bjr_census")
_PROD_SOURCES = {
    "ffb_actual_kg": ("TbsAktual", "tbs_aktual"), "ffb_budget_kg": ("TbsBudget", "tbs_budget"),
    "ffb_census_kg": ("TbsSensus", "tbs_sensus"), "bunches_actual": ("JanjangAktual", "janjang_aktual"),
    "bunches_budget": ("JanjangBudget", "janjang_budget"), "bunches_census": ("JanjangSensus", "janjang_sensus"),
    "bjr_actual": ("BjrAktual", "bjr_aktual"), "bjr_budget": ("BjrBudget", "bjr_budget"),
    "bjr_census": ("BjrSensus", "bjr_sensus"),
}


def _is_complete_production(values: dict) -> bool:
    """Baris produksi 'lengkap' = ada TBS aktual atau data janjang; sisanya hanya baris sensus/budget."""
    return bool(values.get("ffb_actual_kg")) or values.get("bunches_actual") is not None


def production_dedupe(rows: list[tuple[int, dict]]) -> tuple[dict | None, str]:
    """
    Aturan sama dengan migrasi gis_db_v3 (lihat quarantine.rows):
    - tepat satu baris lengkap -> dipakai, baris sensus-saja diabaikan;
    - semua baris identik -> dipakai satu;
    - selain itu (>1 baris lengkap berbeda, atau baris sensus saling bertentangan) -> tidak dimuat.
    """
    distinct = {tuple(sorted((k, str(v)) for k, v in r.items())) for _, r in rows}
    if len(distinct) == 1:
        return rows[-1][1], "identik"
    complete = {tuple(sorted((k, str(v)) for k, v in r.items())): r for _, r in rows if _is_complete_production(r)}
    if len(complete) == 1:
        return next(iter(complete.values())), "baris sensus-saja diabaikan"
    return None, "baris ganda saling bertentangan"


def _production_builder(db: Session):
    def build(row: dict) -> dict:
        values = {}
        for column, sources in _PROD_SOURCES.items():
            value = pick(row, *sources)
            value = to_int(value) if column == "bunches_actual" else to_float(value)
            values[column] = _non_negative(value, sources[0])
        return values

    return build, {}


def _upsert_simple(db: Session, rows: list[dict], batch_id: UUID, table: str, stage_ddl: str,
                   columns: tuple[str, ...]) -> dict:
    db.execute(text(f"CREATE TEMP TABLE _stage (block_id bigint, period date, {stage_ddl}) ON COMMIT DROP"))
    copy_rows(db, "_stage", ("block_id", "period", *columns),
              ([r["block_id"], r["period"], *(r[c] for c in columns)] for r in rows))
    return _upsert_changed(db, table, "_stage", columns, batch_id)


_PROD_DDL = ", ".join(f"{c} {'integer' if c == 'bunches_actual' else 'numeric'}" for c in _PROD_COLUMNS)
PRODUCTION = TrxKind(
    "trx.block_productions", "data produksi TBS", _production_builder,
    lambda s, rows, batch: _upsert_simple(s, rows, batch, "trx.block_productions", _PROD_DDL, _PROD_COLUMNS),
    production_dedupe,
)


# =====================================================================
# ROTASI PUSINGAN
# =====================================================================

_ROT_COLUMNS = ("area_ha", "tree_count", "rotation_no", "interval_days", "rotation_status_id")


def _rotation_builder(db: Session):
    statuses = RefResolver(db, "rotation_statuses")

    def build(row: dict) -> dict:
        return {
            "area_ha": _non_negative(to_float(pick(row, "Luas", "luas")), "Luas"),
            "tree_count": _non_negative(to_int(pick(row, "Pokok", "pokok")), "Pokok"),
            "rotation_no": _non_negative(to_float(pick(row, "Rotasi", "rotasi_ke")), "Rotasi"),
            "interval_days": _non_negative(to_int(pick(row, "Pusingan", "pusingan_hari")), "Pusingan"),
            "rotation_status_id": statuses.resolve(pick(row, "Status Pusingan", "StatusPusingan", "status_pusingan")),
        }

    return build, {"rotation_statuses": statuses}


_ROT_DDL = "area_ha numeric, tree_count integer, rotation_no numeric, interval_days integer, rotation_status_id smallint"
ROTATION = TrxKind(
    "trx.harvest_rotations", "data rotasi & pusingan", _rotation_builder,
    lambda s, rows, batch: _upsert_simple(s, rows, batch, "trx.harvest_rotations", _ROT_DDL, _ROT_COLUMNS),
)


# =====================================================================
# PINTU MASUK: EXCEL & JSON
# =====================================================================

def import_excel(db: Session, kind: TrxKind, filename: str | None, content: bytes, user_id: UUID | None) -> dict:
    rows = read_excel_rows(filename, content)
    return _run(db, kind, rows=rows, source_type="EXCEL_UPLOAD", source_name=filename, user_id=user_id, first_row=2)


def import_json(db: Session, kind: TrxKind, rows: list[dict], source_name: str | None, user_id: UUID | None) -> dict:
    """Baris JSON memakai nama kolom yang sama dengan header Excel (spasi di tepi nama kolom diabaikan)."""
    rows = [{str(k).strip(): v for k, v in row.items()} for row in rows]
    return _run(db, kind, rows=rows, source_type="JSON_API", source_name=source_name or "JSON API",
                user_id=user_id, first_row=1)


def import_area_statements(db: Session, filename: str | None, content: bytes, user_id: UUID | None) -> dict:
    return import_excel(db, AREA_STATEMENT, filename, content, user_id)


def import_productions(db: Session, filename: str | None, content: bytes, user_id: UUID | None) -> dict:
    return import_excel(db, PRODUCTION, filename, content, user_id)


def import_rotations(db: Session, filename: str | None, content: bytes, user_id: UUID | None) -> dict:
    return import_excel(db, ROTATION, filename, content, user_id)
