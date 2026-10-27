"""
Bentuk respons analisis per part (dipakai worker antrian dan endpoint /upload-analyze sinkron):

    {
      "kategori": "landuse", "bulan": 1, "tahun": 2026, "part": 2, "total_part": 13,
      "data": {
        "table_preview": [{"no_preview": 1001, "status_analisa": "AMAN", "kode_gagal": null, "alasan_gagal": null}, ...],
        "analisa_aman":  {...rincian yang aman/siap disimpan, dikelompokkan...},
        "analisa_gagal": {...rincian yang gagal/kendala data, dikelompokkan...},
        "ringkasan":     {...status_analisis, kesimpulan, angka-angka hasil lama...}
      }
    }

`no_preview` = nomor feature di FILE ASLI (offset part + nomor di part, mulai 1), sama dengan nomor
baris tabel preview FE, sehingga FE bisa langsung menempelkan kolom status_analisa/kode_gagal/alasan_gagal.
"""
import re
from typing import Any

from app.services.upload.report import REJECTIONS

AMAN = "AMAN"
GAGAL = "GAGAL"

# Kunci rincian lama yang berisi data gagal / tidak akan disimpan. Kunci rincian lain = aman (akan disimpan,
# mungkin dengan catatan: blok baru di master, menimpa batas lama, blok terpecah digabung, dst).
GAGAL_RINCIAN = {"data_ditolak", "data_tidak_valid", "data_geometri_invalid", "blok_kembar_di_master"}
# Kode peringatan yang menjelaskan data gagal. Peringatan lain = catatan pada data aman.
GAGAL_PERINGATAN = set(REJECTIONS) | {
    "ATRIBUT_TIDAK_LENGKAP", "GEOMETRI_TIDAK_VALID", "BLOK_KEMBAR_DI_MASTER", "NILAI_ATRIBUT_INVALID",
}
EXTRA_LABELS = {
    "ATRIBUT_BLOK_KOSONG": "atribut Estate/Afdeling/Blok tidak lengkap",
    "BLOK_KEMBAR_DI_MASTER": "kode blok kembar di beberapa afdeling master",
    "GAGAL_DISIMPAN": "gagal disimpan",
}


def _label(code: str) -> str:
    return REJECTIONS[code][0] if code in REJECTIONS else EXTRA_LABELS.get(code, code)


_DATA_NO = re.compile(r"data #(\d+)")


def shift_reason(reason: Any, offset: int) -> Any:
    """Nomor `data #N` di teks alasan (nomor lokal part) -> nomor global = no_preview tabel FE."""
    if not offset or not isinstance(reason, str):
        return reason
    return _DATA_NO.sub(lambda m: f"data #{int(m.group(1)) + offset}", reason)


def shift_no_preview(value: Any, offset: int) -> Any:
    """Geser semua `no_preview` (int atau list int) di rincian lama ke nomor global."""
    if not offset:
        return value
    if isinstance(value, list):
        return [shift_no_preview(v, offset) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "no_preview" and isinstance(v, int):
                out[k] = v + offset
            elif k == "no_preview" and isinstance(v, list):
                out[k] = [n + offset if isinstance(n, int) else n for n in v]
            elif k == "alasan":
                out[k] = shift_reason(v, offset)
            else:
                out[k] = shift_no_preview(v, offset)
        return out
    return value


def table_preview(total: int, rejected: list[dict], offset: int = 0) -> list[dict]:
    """Satu baris per feature di part. `rejected` memakai no_preview lokal (1..total)."""
    by_no: dict[int, list[dict]] = {}
    for r in rejected:
        by_no.setdefault(int(r["no_preview"]), []).append(r)
    rows = []
    for no in range(1, total + 1):
        found = by_no.get(no) or []
        r = found[0] if found else None  # alasan pertama = kolom kode_gagal/alasan_gagal
        row = {
            "no_preview": offset + no,
            "status_analisa": GAGAL if r else AMAN,
            "kode_gagal": r["kode"] if r else None,
            "alasan_gagal": shift_reason(r["alasan"], offset) if r else None,
        }
        if len(found) > 1:  # data dengan >1 alasan gagal: alasan lain (untuk unduhan Excel data gagal)
            row["gagal_lain"] = [{"kode": x["kode"], "alasan": shift_reason(x["alasan"], offset)} for x in found[1:]]
        rows.append(row)
    return rows


def group_failures(rejected: list[dict], offset: int = 0) -> list[dict]:
    groups: dict[str, dict] = {}
    for r in rejected:
        g = groups.setdefault(r["kode"], {"kode": r["kode"], "keterangan": _label(r["kode"]), "jumlah": 0, "data": []})
        g["jumlah"] += 1
        g["data"].append({"no_preview": offset + int(r["no_preview"]), "alasan": shift_reason(r["alasan"], offset)})
    return sorted(groups.values(), key=lambda g: (-g["jumlah"], g["kode"]))


def build(result: dict, *, kategori: str, bulan: int, tahun: int, part: int = 1, total_part: int = 1,
          offset: int = 0) -> dict:
    """Bungkus hasil analisis lama satu part menjadi bentuk respons per part."""
    result = dict(result)
    rejected = result.pop("_penolakan", []) or []
    total = int(result.pop("_total_fitur", 0) or 0)
    rincian = shift_no_preview(result.pop("rincian", {}) or {}, offset)
    peringatan = result.pop("peringatan", []) or []

    aman_rincian = {k: v for k, v in rincian.items() if k not in GAGAL_RINCIAN}
    gagal_rincian = {k: v for k, v in rincian.items() if k in GAGAL_RINCIAN}
    preview = table_preview(total, rejected, offset)
    jumlah_gagal = sum(r["status_analisa"] == GAGAL for r in preview)

    return {
        "kategori": kategori,
        "bulan": bulan,
        "tahun": tahun,
        "part": part,
        "total_part": total_part,
        "data": {
            "table_preview": preview,
            "analisa_aman": {
                "jumlah_data": total - jumlah_gagal,
                "rincian": aman_rincian,
                "catatan": [w for w in peringatan if w.get("kode") not in GAGAL_PERINGATAN],
            },
            "analisa_gagal": {
                "jumlah_data": jumlah_gagal,
                "per_kode": group_failures(rejected, offset),
                "rincian": gagal_rincian,
                "peringatan": [w for w in peringatan if w.get("kode") in GAGAL_PERINGATAN],
            },
            # Ringkasan hasil lama (status_analisis, kesimpulan, angka) untuk kartu ringkasan FE.
            "ringkasan": {**result, "no_preview_awal": offset + 1 if total else None,
                          "no_preview_akhir": offset + total if total else None},
        },
    }
