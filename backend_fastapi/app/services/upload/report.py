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
from app.utils.geometry_reason import explain_geometry
from app.utils.period import period_label

DETAIL_LIMIT = 100

# kode -> (ringkasan untuk kesimpulan, pesan peringatan lengkap dengan saran)
REJECTIONS = {
    "ATRIBUT_BLOK_KOSONG": (
        "atribut Estate/Afdeling/Blok tidak lengkap",
        "data tidak punya Estate (EstID/Est/Estate), Afdeling, atau Blok, sehingga tidak bisa dikaitkan ke blok. "
        "Lengkapi atributnya di file sumber.",
    ),
    "GEOMETRI_TIDAK_VALID": (
        "geometri tidak valid / kosong / tipenya tidak sesuai",
        "data geometrinya tidak bisa dipakai (kosong, tipe tidak sesuai layer, koordinat rusak, atau bentuknya "
        "tidak valid seperti garis batas saling berpotongan). Lihat 'Alasan Gagal' per data untuk lokasi dan "
        "saran perbaikannya (umumnya QGIS: Fix Geometries).",
    ),
    "NILAI_TIDAK_VALID": (
        "nilai atribut wajib kosong / tidak valid",
        "data punya nilai atribut wajib yang kosong atau tidak valid (lihat alasan per data di rincian).",
    ),
    "BLOK_TIDAK_DITEMUKAN": (
        "blok tidak ditemukan di master",
        "data menunjuk blok yang tidak ada di master, dan posisinya juga tidak berada di batas blok mana pun. "
        "Periksa kode Estate/Afdeling/Blok, atau upload batas bloknya lebih dulu.",
    ),
    "OBJECTID_GANDA": (
        "OBJECTID ganda di file",
        "data memakai OBJECTID yang sama dengan data lain di file; hanya data TERAKHIR yang dipakai. "
        "Pastikan OBJECTID unik.",
    ),
}


@dataclass
class UploadReport:
    total: int = 0
    rejected: list[dict] = field(default_factory=list)
    features: list[dict] = field(default_factory=list, repr=False)  # fitur asli, untuk karantina

    def reject(self, index: int, code: str, reason: str) -> None:
        self.rejected.append({"no_preview": index + 1, "kode": code, "alasan": reason})

    def counts(self) -> Counter:
        return Counter(r["kode"] for r in self.rejected)


ESTATE_KEYS = ("EstID", "Est", "Estate")
_ESTATE_ALT = ("EstID_2", "Estate_2")


def _shown(value) -> str:
    if value is None:
        return "(tidak ada)"
    text_ = str(value).strip()
    return "(kosong)" if not text_ else repr(text_[:60])


def _near_keys(props: dict, wanted: str, accepted: tuple[str, ...]) -> list[str]:
    """Kolom di file yang namanya mirip (beda huruf besar/kecil, spasi, _) dengan kolom wajib."""
    norm = lambda k: str(k).lower().replace("_", "").replace(" ", "")
    targets = {norm(k) for k in (wanted, *accepted)}
    return [k for k in props if norm(k) in targets and k not in (wanted, *accepted)]


def missing_block_attributes(props: dict, estate_keys: tuple[str, ...] = ESTATE_KEYS,
                             alt_keys: bool = True) -> str:
    """
    Alasan rinci untuk fitur tanpa Estate/Afdeling/Blok lengkap: kolom apa yang kosong, nilai yang
    terbaca dari file, nama kolom yang diterima, dan kolom bernama mirip (salah tulis) bila ada.
    """
    estate_all = estate_keys + (_ESTATE_ALT if alt_keys else ())
    division_all = ("Afdeling", "Afdeling_2") if alt_keys else ("Afdeling",)
    fields = [("Estate", estate_all), ("Afdeling", division_all), ("Blok", ("Blok",))]
    missing, read, hints = [], [], []
    for label, keys in fields:
        values = {k: props.get(k) for k in keys if k in props}
        filled = {k: v for k, v in values.items() if v is not None and str(v).strip()}
        if filled:
            k, v = next(iter(filled.items()))
            read.append(f"{k}={_shown(v)}")
            continue
        missing.append(f"{label} ({'/'.join(keys)})")
        read.append(f"{keys[0]}={_shown(values.get(keys[0]))}" if values else f"{label}=(kolom tidak ada)")
        similar = [k for k in _near_keys(props, label, keys)
                   if props.get(k) is not None and str(props.get(k)).strip()]
        if similar:
            hints.append(f"kolom '{similar[0]}' berisi {_shown(props[similar[0]])} tetapi nama kolomnya harus "
                         f"persis '{keys[0]}'")
    reason = (f"Atribut wajib kosong: {', '.join(missing)}. Nilai terbaca di file: {'; '.join(read)}. "
              "Tanpa Estate, Afdeling, dan Blok, data tidak bisa dikaitkan ke blok master.")
    if hints:
        reason += " Kemungkinan salah nama kolom: " + "; ".join(hints) + "."
    return reason + " Lengkapi kolomnya di tabel atribut (QGIS: Open Attribute Table / Field Calculator)."


def value_text(value) -> str:
    """Nilai atribut untuk pesan: (tidak ada) / (kosong) / 'nilai'."""
    return _shown(value)


def duplicate_reason(objectid, later_index: int) -> str:
    """OBJECTID_GANDA: `later_index` = indeks (0-based, lokal part) data yang DIPAKAI (muncul lebih akhir).
    Nomor `data #N` digeser ke nomor global oleh part_response."""
    return (f"OBJECTID {objectid} dipakai lebih dari satu data di file; yang disimpan hanya data terakhir "
            f"(data #{later_index + 1}), data ini dilewati. Pastikan OBJECTID unik per data "
            "(QGIS Field Calculator: @row_number).")


def geometry_problem(geometry: dict | None, expected: str, layer: str | None = None) -> str:
    """Alasan rinci GEOMETRI_TIDAK_VALID (lihat app.utils.geometry_reason)."""
    return explain_geometry(geometry, expected, layer)


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
        row = per_estate.setdefault(code, {"estate": code, "nama_estate": name, "jumlah_blok": 0, "data_siap": 0})
        row["jumlah_blok"] += 1
        row["data_siap"] += counts[block_id]
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
            "pesan": f"{match.spatial_matches} data labelnya tidak cocok dengan master, sehingga bloknya ditentukan "
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
        conclusion = f"Tidak ada data yang bisa diunggah dari {report.total} data ke layer {layer}."
    else:
        status = "SIAP_DENGAN_CATATAN" if any(w["level"] == "PERINGATAN" for w in warnings) else "SIAP"
        target = f" ke {blocks} blok" if blocks is not None else ""
        conclusion = f"Dari {report.total} data, {ready} siap diunggah{target} untuk layer {layer} periode {label}."
    if report.rejected:
        reasons = ", ".join(f"{n} {REJECTIONS[code][0]}" for code, n in counts.most_common())
        conclusion += f" {len(report.rejected)} data ditolak ({reasons})."
    if replaced and ready:
        conclusion += f" {replaced} data lama periode ini {replace_scope} akan diganti."

    return {
        "status_analisis": status,
        "kesimpulan": conclusion,
        "peringatan": warnings,
        "rincian": {
            "per_estate": estate_summary(db, block_ids or []),
            "data_ditolak": sorted(report.rejected, key=lambda r: r["no_preview"])[:DETAIL_LIMIT],
        },
        # Daftar lengkap (tanpa batas) untuk table_preview per part; tidak ikut ke respons.
        "penolakan": [
            {**r, "sumber": report.features[r["no_preview"] - 1]}
            if 0 < r["no_preview"] <= len(report.features) else r
            for r in sorted(report.rejected, key=lambda r: r["no_preview"])
        ],
    }
