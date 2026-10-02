"""
Laporan analisis upload GeoJSON yang bisa dipahami pengunggah: status, kesimpulan,
peringatan (apa masalahnya + saran), dan rincian (fitur mana yang ditolak & kenapa).

Nomor fitur (`no_preview`) dimulai dari 1 = nomor baris di tabel preview FE.
"""
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.upload.resolvers import BlockMatchReport
from app.utils.period import period_label

DETAIL_LIMIT = 100

# kode -> (ringkasan untuk kesimpulan, pesan peringatan lengkap dengan saran)
REJECTIONS = {
    "ATRIBUT_BLOK_KOSONG": (
        "atribut Estate/Afdeling/Blok tidak lengkap",
        "fitur tidak punya Estate (EstID/Est/Estate), Afdeling, atau Blok, sehingga tidak bisa dikaitkan ke blok. "
        "Lengkapi atributnya di file sumber.",
    ),
    "GEOMETRI_TIDAK_VALID": (
        "geometri kosong / tipenya tidak sesuai",
        "fitur geometrinya kosong atau tipenya tidak sesuai layer ini. Periksa tipe geometri di file sumber.",
    ),
    "NILAI_TIDAK_VALID": (
        "nilai atribut wajib kosong / tidak valid",
        "fitur punya nilai atribut wajib yang kosong atau tidak valid (lihat alasan per fitur di rincian).",
    ),
    "BLOK_TIDAK_DITEMUKAN": (
        "blok tidak ditemukan di master",
        "fitur menunjuk blok yang tidak ada di master, dan posisinya juga tidak berada di batas blok mana pun. "
        "Periksa kode Estate/Afdeling/Blok, atau upload batas bloknya lebih dulu.",
    ),
    "OBJECTID_GANDA": (
        "OBJECTID ganda di file",
        "fitur memakai OBJECTID yang sama dengan fitur lain di file; hanya fitur TERAKHIR yang dipakai. "
        "Pastikan OBJECTID unik.",
    ),
}


@dataclass
class UploadReport:
    total: int = 0
    rejected: list[dict] = field(default_factory=list)

    def reject(self, index: int, code: str, reason: str) -> None:
        self.rejected.append({"no_preview": index + 1, "kode": code, "alasan": reason})

    def counts(self) -> Counter:
        return Counter(r["kode"] for r in self.rejected)


def missing_block_attributes(props: dict) -> str:
    """Alasan untuk fitur yang gagal `geojson_block_keys`."""
    missing = []
    if not any(props.get(k) for k in ("EstID", "Est", "Estate")):
        missing.append("Estate (EstID/Est/Estate)")
    if not props.get("Afdeling"):
        missing.append("Afdeling")
    if not props.get("Blok"):
        missing.append("Blok")
    return "Kosong: " + ", ".join(missing)


def geometry_problem(geometry: dict | None, expected: str) -> str:
    gtype = (geometry or {}).get("type")
    if not gtype:
        return "Geometri kosong."
    return f"Tipe geometri {gtype} tidak bisa dipakai untuk layer {expected}, atau koordinatnya tidak valid."


def estate_summary(db: Session, block_ids: Iterable[int]) -> list[dict]:
    """Jumlah blok & fitur siap per estate (dari block_id baris yang siap diunggah)."""
    counts = Counter(block_ids)
    if not counts:
        return []
    rows = db.execute(text("""
        SELECT bl.id, es.code, es.name
        FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
        JOIN master.estates es ON es.id = dv.estate_id
        WHERE bl.id = ANY(:ids)
    """), {"ids": list(counts)}).all()
    per_estate: dict[str, dict] = {}
    for block_id, code, name in rows:
        row = per_estate.setdefault(code, {"estate": code, "nama_estate": name, "jumlah_blok": 0, "fitur_siap": 0})
        row["jumlah_blok"] += 1
        row["fitur_siap"] += counts[block_id]
    return sorted(per_estate.values(), key=lambda r: r["estate"])


def build(
    db: Session,
    report: UploadReport,
    *,
    layer: str,
    period: date,
    ready: int,
    block_ids: list[int] | None,
    replaced: int,
    match: BlockMatchReport | None = None,
    replace_scope: str = "pada blok-blok yang ada di file ini",
    notices: list[dict] | None = None,
) -> dict:
    """
    Susun bagian laporan analisis. `block_ids` = block_id tiap baris siap (None untuk layer tanpa relasi blok).
    `notices` = peringatan tambahan khusus layer: {kode, jumlah, pesan, level} (level PERINGATAN/INFO).
    """
    label = period_label(period)
    counts = report.counts()
    warnings = [
        {"kode": code, "level": "PERINGATAN", "jumlah": n, "pesan": f"{n} {REJECTIONS[code][1]}"}
        for code, n in counts.items()
    ]
    warnings += [{"level": "PERINGATAN", **n} for n in notices or [] if n.get("level", "PERINGATAN") == "PERINGATAN"]
    if match and match.spatial_matches:
        warnings.append({
            "kode": "KOREKSI_LABEL_BLOK", "level": "INFO", "jumlah": match.spatial_matches,
            "pesan": f"{match.spatial_matches} fitur labelnya tidak cocok dengan master, sehingga bloknya ditentukan "
                     "dari posisi geometri. Lihat 'koreksi_label_blok' dan perbaiki labelnya di file sumber.",
        })
    if replaced:
        warnings.append({
            "kode": "MENGGANTI_DATA_LAMA", "level": "INFO", "jumlah": replaced,
            "pesan": f"{replaced} data lama periode {label} {replace_scope} akan DIHAPUS dan diganti isi file ini.",
        })
    warnings += [{**n, "level": "INFO"} for n in notices or [] if n.get("level") == "INFO"]

    blocks = len(set(block_ids)) if block_ids is not None else None
    if ready == 0:
        status = "TIDAK_ADA_DATA_VALID"
        conclusion = f"Tidak ada fitur yang bisa diunggah dari {report.total} fitur ke layer {layer}."
    else:
        status = "SIAP_DENGAN_CATATAN" if any(w["level"] == "PERINGATAN" for w in warnings) else "SIAP"
        target = f" ke {blocks} blok" if blocks is not None else ""
        conclusion = f"Dari {report.total} fitur, {ready} siap diunggah{target} untuk layer {layer} periode {label}."
    if report.rejected:
        reasons = ", ".join(f"{n} {REJECTIONS[code][0]}" for code, n in counts.most_common())
        conclusion += f" {len(report.rejected)} fitur ditolak ({reasons})."
    if replaced and ready:
        conclusion += f" {replaced} data lama periode ini {replace_scope} akan diganti."

    return {
        "status_analisis": status,
        "kesimpulan": conclusion,
        "peringatan": warnings,
        "rincian": {
            "per_estate": estate_summary(db, block_ids or []),
            "fitur_ditolak": sorted(report.rejected, key=lambda r: r["no_preview"])[:DETAIL_LIMIT],
            "catatan": f"Daftar fitur_ditolak dibatasi {DETAIL_LIMIT} baris; jumlah lengkapnya ada di 'peringatan'. "
                       "no_preview dimulai dari 1 (nomor baris di tabel preview FE).",
        },
    }
