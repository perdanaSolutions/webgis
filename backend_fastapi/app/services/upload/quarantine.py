"""
Karantina upload (quarantine.rows): baris/fitur yang tidak lolos validasi disimpan utuh
beserta alasannya, dikaitkan ke batch upload, supaya bisa ditelusuri dan diperbaiki di sumbernya.

Ditulis dalam transaksi yang sama dengan data yang lolos (commit bersama).
"""
import json
import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.upload import context
from app.utils.parsing import json_safe


@dataclass
class Rejected:
    no: int  # nomor baris Excel / item JSON / fitur GeoJSON (mulai 1)
    code: str  # kode alasan, mis. BLOK_TIDAK_DITEMUKAN
    reason: str
    data: Any  # baris asli (dict) atau fitur GeoJSON utuh


def _default(value: Any) -> Any:
    safe = json_safe(value)  # Decimal -> float, date/datetime -> ISO
    return str(value) if safe is value else safe


def _finite(value: Any) -> Any:
    """NaN/Infinity (mis. sel Excel kosong) tidak valid di jsonb -> None."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


def _json(value: Any) -> str:
    return json.dumps(_finite(value), default=_default, ensure_ascii=False)


def save(db: Session, batch_id: UUID, target_table: str, rejected: list[Rejected]) -> int:
    """Simpan baris yang ditolak. Mengembalikan jumlah baris yang dikarantina."""
    if not rejected:
        return 0
    offset = context.current().offset  # part ke-n: nomor fitur global = offset + nomor di part
    db.execute(text("""
        INSERT INTO quarantine.rows (source_table, source_id, reason, reason_code, action, data, upload_batch_id)
        VALUES (:table, :no, :reason, :code, 'NOT_LOADED', CAST(:data AS jsonb), :batch)
    """), [
        {"table": target_table, "no": str(r.no + offset), "reason": r.reason[:2000], "code": r.code[:50],
         "data": _json(r.data), "batch": str(batch_id)}
        for r in rejected
    ])
    return len(rejected)


def from_report(report) -> list[Rejected]:
    """Penolakan UploadReport (GeoJSON) -> Rejected berisi fitur aslinya (report.features)."""
    return [
        Rejected(r["no_preview"], r["kode"], r["alasan"], report.features[r["no_preview"] - 1])
        for r in sorted(report.rejected, key=lambda r: r["no_preview"])
    ]
