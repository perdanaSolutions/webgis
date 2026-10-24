"""
Analisis (uji coba) import Excel transaksi: menjalankan proses import yang SAMA PERSIS di dalam transaksi
lalu membatalkannya, sehingga angka di laporan sama dengan hasil import sungguhan tetapi tidak ada data
yang tersimpan (data, nilai referensi, karantina, dan riwayat upload semuanya di-rollback).

Bentuk laporan mengikuti analisis upload GeoJSON: status_analisis, kesimpulan, peringatan, rincian.
"""
from collections import Counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.trx_import_service import (
    BLOCK_COLUMNS, COMPANY_COLUMNS, DIVISION_COLUMNS, ESTATE_COLUMNS, GROUP_COLUMNS, MONTH_COLUMNS, YEAR_COLUMNS,
    TrxKind, _PROD_SOURCES, _collect, _period_summary, canonicalize_rows,
)
from app.services.upload.report import DETAIL_LIMIT, estate_summary
from app.utils.excel import pick, read_excel_rows
from app.utils.parsing import clean_str

DATE_COLUMNS = ("Tanggal", "tanggal", "Date")

# kolom yang dibaca importer, per jenis (selain kolom blok/estate/periode yang sama untuk semuanya)
KIND_COLUMNS = {
    "trx.area_statements": (
        "AreaCode", "Area", "KodeArea", "StatusTanam", "Status Tanam", "status_tanam", "TahunTanam", "Tahun Tanam",
        "tahun_tanam", "BulanTanam", "Bulan Tanam", "bulan_tanam", "TanahDatar", "Pct Datar", "Berbukit",
        "Pct Berbukit", "Gelombang", "Pct Gelombang", "Curam", "Pct Curam", "JenisBibit", "Jenis Bibit", "jenis_bibit",
        "JenisTanah", "Jenis Tanah", "jenis_tanah", "JenisTopografi", "Jenis Topografi", "jenis_topografi",
        "LuasTanam", "Luas Tanam", "LuasTanah", "Luas Tanah", "TotalPokok", "Total Pokok", "SPH", "Sph",
        "TipeBlok", "Tipe Blok", "Ownership",
    ),
    "trx.block_productions": tuple(name for names in _PROD_SOURCES.values() for name in names),
    "trx.harvest_rotations": (
        "Luas", "luas", "Pokok", "pokok", "Rotasi", "rotasi_ke", "Pusingan", "pusingan_hari",
        "Status Pusingan", "StatusPusingan", "status_pusingan",
    ),
}
# kolom yang boleh ada di file tetapi sengaja tidak disimpan
IGNORED_COLUMNS = {
    "trx.area_statements": (),
    "trx.block_productions": (),
    "trx.harvest_rotations": ("Area", "PT", "BulanID"),
}
# kelompok kolom wajib: label -> nama kolom yang diterima (cukup salah satu)
REQUIRED_GROUPS = {
    "common": {
        "Kode blok (KodeBlok/Blok)": BLOCK_COLUMNS,
        "Afdeling (DivisionCode/Afdeling)": DIVISION_COLUMNS,
        "Estate (UnitCode/Estate/EstateShortName)": ESTATE_COLUMNS,
    },
    "trx.area_statements": {
        "AreaCode": ("AreaCode", "Area", "KodeArea"),
        "StatusTanam": ("StatusTanam", "Status Tanam", "status_tanam"),
    },
}

REJECTIONS = {
    "KODE_BLOK_KOSONG": (
        "kode blok kosong",
        "baris tidak punya kode blok. Isi kolom KodeBlok/Blok di Excel.",
    ),
    "BLOK_TIDAK_DITEMUKAN": (
        "blok tidak ditemukan di master",
        "baris menunjuk estate/afdeling/blok yang tidak cocok persis dengan master. Lihat 'blok_tidak_ditemukan' di "
        "rincian untuk penyebab tiap blok, lalu tambahkan ke master atau perbaiki kodenya di Excel.",
    ),
    "NILAI_TIDAK_VALID": (
        "nilai kosong / tidak valid",
        "baris punya nilai wajib yang kosong atau tidak valid (lihat alasan per baris di rincian 'data_ditolak').",
    ),
    "DUPLIKAT_BERTENTANGAN": (
        "duplikat bertentangan",
        "blok dan bulan yang sama muncul lebih dari sekali dengan isi yang bertentangan, sehingga semua barisnya "
        "ditolak. Sisakan satu baris yang benar di Excel.",
    ),
}


def _row_label(row: dict) -> str:
    estate = next((str(v) for c in ESTATE_COLUMNS if (v := pick(row, c))), "-")
    return f"{estate}/{clean_str(pick(row, *DIVISION_COLUMNS)) or '-'}/{clean_str(pick(row, *BLOCK_COLUMNS)) or '-'}"


def _column_report(kind: TrxKind, headers: list[str]) -> tuple[list[str], list[str], list[str]]:
    """(kolom dibaca, kolom diabaikan/tidak dikenali, kelompok wajib yang tidak ada)."""
    ignored = set(IGNORED_COLUMNS.get(kind.target, ()))
    read = (set(BLOCK_COLUMNS) | set(DIVISION_COLUMNS) | set(ESTATE_COLUMNS) | set(MONTH_COLUMNS) | set(YEAR_COLUMNS)
            | set(DATE_COLUMNS) | set(COMPANY_COLUMNS) | set(GROUP_COLUMNS) | set(KIND_COLUMNS.get(kind.target, ())))
    used = [h for h in headers if h in read]
    skipped = [h for h in headers if h not in read]
    missing = [label for label, names in {**REQUIRED_GROUPS["common"], **REQUIRED_GROUPS.get(kind.target, {})}.items()
               if not any(h in names for h in headers)]
    has_period = (any(h in YEAR_COLUMNS for h in headers) and any(h in MONTH_COLUMNS for h in headers)) \
        or any(h in DATE_COLUMNS for h in headers)
    if not has_period:
        missing.append("Periode (Year + Month, atau Tanggal)")
    return used, [h for h in skipped if h not in ignored], missing


def analyze_excel(db: Session, kind: TrxKind, filename: str | None, content: bytes) -> dict:
    rows = canonicalize_rows(read_excel_rows(filename, content))
    headers = list(rows[0].keys()) if rows else []
    try:
        build, refs = kind.build_factory(db)
        result = _collect(db, rows, build, kind.dedupe, 2, kind.strict_block, check_area_column=kind.check_area_column)
        new_refs = {name: r.created for name, r in refs.items() if r.created}
        written = {"baru": 0, "diperbarui": 0}
        if result.rows:
            batch_id = db.execute(text(
                "INSERT INTO audit.upload_batches (source_type, target_table, source_name) "
                "VALUES ('EXCEL_ANALYZE', :t, :n) RETURNING id"),
                {"t": kind.target, "n": (filename or "")[:255] or None}).scalar_one()
            written = kind.load(db, result.rows, batch_id)
        report = _report(db, kind, filename, headers, result, new_refs, written, len(rows))
        first_row = 2
        report["_total_fitur"] = len(rows)
        report["_penolakan"] = [
            {"no_preview": r.no - first_row + 1, "kode": r.code, "alasan": r.reason}
            for r in result.rejected
        ]
        return report
    finally:
        db.rollback()  # tidak ada yang disimpan


def _report(db, kind, filename, headers, result, new_refs, written, total) -> dict:
    ready = len(result.rows)
    unchanged = ready - written["baru"] - written["diperbarui"]
    periods = sorted({r["period"] for r in result.rows})
    used_columns, skipped_columns, missing_columns = _column_report(kind, headers)
    counts = Counter(r.code for r in result.rejected)
    rejected_total = len(result.rejected)

    warnings = []
    if missing_columns:
        warnings.append({
            "kode": "KOLOM_WAJIB_TIDAK_ADA", "level": "PERINGATAN", "jumlah": len(missing_columns),
            "pesan": "Kolom wajib tidak ditemukan di header Excel: " + "; ".join(missing_columns) +
                     ". Periksa penulisan nama kolom di baris pertama.",
        })
    for code, n in counts.most_common():
        warnings.append({"kode": code, "level": "PERINGATAN", "jumlah": n, "pesan": f"{n} {REJECTIONS[code][1]}"})
    if new_refs:
        listed = "; ".join(f"{name}: {', '.join(values[:10])}" for name, values in new_refs.items())
        warnings.append({
            "kode": "NILAI_REFERENSI_BARU", "level": "PERINGATAN", "jumlah": sum(len(v) for v in new_refs.values()),
            "pesan": f"Nilai berikut belum terdaftar dan akan DIBUAT otomatis saat import: {listed}. "
                     "Pastikan bukan salah ketik.",
        })
    if result.company_warnings:
        warnings.append({
            "kode": "COMPANY_CODE_BERBEDA", "level": "PERINGATAN", "jumlah": result.company_warnings,
            "pesan": f"{result.company_warnings} baris punya CompanyCode yang berbeda dari PT blok di master. "
                     "Baris tetap diimpor; periksa 'peringatan_company_code' di rincian.",
        })
    if result.division_warnings:
        warnings.append({
            "kode": "AFDELING_BERBEDA", "level": "PERINGATAN", "jumlah": result.division_warnings,
            "pesan": f"{result.division_warnings} baris menunjuk blok yang ada di master tetapi di afdeling lain. "
                     "Baris tetap diimpor ke blok itu (kunci UnitCode + Blok); afdeling di master tidak diubah "
                     "(afdeling resmi mengikuti GeoJSON blok). Periksa 'peringatan_afdeling' di rincian.",
        })
    if result.area_warnings:
        warnings.append({
            "kode": "AREA_BERBEDA", "level": "PERINGATAN", "jumlah": result.area_warnings,
            "pesan": f"{result.area_warnings} baris punya AreaCode yang berbeda dari area estate saat ini di master. "
                     "Baris tetap diimpor dengan area di file sebagai riwayat bulan itu; area estate di master "
                     "TIDAK diubah (area resmi mengikuti GeoJSON blok). Periksa 'peringatan_area' di rincian.",
        })
    if result.group_warnings:
        warnings.append({
            "kode": "GRUP_BERBEDA", "level": "PERINGATAN", "jumlah": result.group_warnings,
            "pesan": f"{result.group_warnings} baris punya Group yang berbeda dari grup PT di master. "
                     "Baris tetap diimpor dan grup di master TIDAK diubah (grup resmi mengikuti GeoJSON blok); "
                     "periksa 'peringatan_grup' di rincian.",
        })
    if result.duplicates_merged:
        warnings.append({
            "kode": "DUPLIKAT_DALAM_FILE", "level": "INFO", "jumlah": result.duplicates_merged,
            "pesan": f"{result.duplicates_merged} baris ganda (blok dan bulan sama) digabung; yang dipakai satu baris "
                     "sesuai aturan jenis data ini.",
        })
    if written["diperbarui"]:
        warnings.append({
            "kode": "MEMPERBARUI_DATA_LAMA", "level": "INFO", "jumlah": written["diperbarui"],
            "pesan": f"{written['diperbarui']} baris akan MEMPERBARUI data yang sudah ada karena nilainya berbeda.",
        })
    if skipped_columns:
        warnings.append({
            "kode": "KOLOM_TIDAK_DIBACA", "level": "INFO", "jumlah": len(skipped_columns),
            "pesan": "Kolom berikut ada di Excel tetapi tidak dibaca importer: " + ", ".join(skipped_columns) + ".",
        })
    warnings.append({
        "kode": "TIDAK_MENGHAPUS", "level": "INFO", "jumlah": 0,
        "pesan": "Import Excel hanya menambah dan memperbarui data; blok yang tidak ada di file tidak dihapus.",
    })

    if total == 0:
        status, conclusion = "TIDAK_ADA_DATA_VALID", "File tidak berisi baris data."
    elif ready == 0:
        status = "TIDAK_ADA_DATA_VALID"
        conclusion = f"Tidak ada baris yang bisa diimpor dari {total} baris untuk {kind.label}."
    else:
        status = "SIAP_DENGAN_CATATAN" if any(w["level"] == "PERINGATAN" for w in warnings) else "SIAP"
        period_text = _period_text(periods)
        conclusion = (f"Dari {total} baris, {ready} siap diimpor untuk {kind.label} ({period_text}): "
                      f"{written['baru']} data baru, {written['diperbarui']} memperbarui data yang sudah ada, "
                      f"{unchanged} sama persis dengan data yang ada.")
    if rejected_total and total:
        reasons = ", ".join(f"{n} {REJECTIONS[code][0]}" for code, n in counts.most_common())
        conclusion += f" {rejected_total} baris ditolak ({reasons}) dan masuk karantina jika diimpor."

    missing_blocks = sorted(
        ({"blok": label, **info} for label, info in result.missing_blocks.items()),
        key=lambda b: (-b["jumlah_baris"], b["blok"]))
    causes = Counter(info["penyebab"] for info in result.missing_blocks.values())
    return {
        "tipe_upload": f"EXCEL_{kind.target.split('.')[-1].upper()}",
        "nama_file": filename,
        "status_analisis": status,
        "kesimpulan": conclusion,
        "total_baris": total,
        "baris_siap": ready,
        "data_baru": written["baru"],
        "data_diperbarui": written["diperbarui"],
        "data_tidak_berubah": unchanged,
        "baris_ganda_digabung": result.duplicates_merged,
        "baris_ditolak": {
            "total": rejected_total,
            **{code.lower(): n for code, n in counts.items()},
        },
        "periode_terisi": _period_summary(periods),
        "peringatan": warnings,
        "rincian": {
            "kolom_dibaca": used_columns,
            "kolom_tidak_dibaca": skipped_columns,
            "per_periode": [{"periode": f"{p.month}-{p.year}", "jumlah_data": n}
                            for p, n in sorted(Counter(r["period"] for r in result.rows).items())],
            "per_estate": estate_summary(db, [r["block_id"] for r in result.rows]),
            "blok_tidak_ditemukan": missing_blocks[:DETAIL_LIMIT],
            "ringkasan_penyebab_blok_tidak_ditemukan": [
                {"penyebab": cause, "jumlah_blok": n} for cause, n in causes.most_common()],
            "data_ditolak": [
                {"no_baris": r.no, "kode": r.code, "alasan": r.reason, "blok": _row_label(r.data)}
                for r in sorted(result.rejected, key=lambda r: r.no)[:DETAIL_LIMIT]
            ],
            "nilai_referensi_baru": new_refs,
            "peringatan_company_code": {"jumlah": result.company_warnings, "contoh": result.company_warning_samples},
            "peringatan_grup": {"jumlah": result.group_warnings, "contoh": result.group_warning_samples},
            "peringatan_area": {"jumlah": result.area_warnings, "contoh": result.area_warning_samples},
            "peringatan_afdeling": {"jumlah": result.division_warnings, "contoh": result.division_warning_samples},
        },
    }


def _period_text(periods) -> str:
    if not periods:
        return "tanpa periode"
    if len(periods) == 1:
        return f"periode {periods[0].month}-{periods[0].year}"
    return f"periode {periods[0].month}-{periods[0].year} sampai {periods[-1].month}-{periods[-1].year}"
