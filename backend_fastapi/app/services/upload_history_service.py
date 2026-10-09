"""Riwayat upload (audit.upload_batches): siapa mengunggah file apa, ke tabel mana, dan hasilnya.

Memakai SQL mentah: model ORM di app/models/audit.py memakai Base yang berbeda dari User
(app/core/database.py), sehingga tidak bisa di-join lewat ORM.
"""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, not_found
from app.schemas.upload_history import UploadHistoryDetail, UploadHistoryResponse, Uploader
from app.utils.pagination import paginate_sql

STATUSES = ("IN_PROGRESS", "SUCCESS", "PARTIAL_SUCCESS", "FAILED", "ABANDONED")

_SELECT = """
    SELECT b.id, b.source_type, b.target_table, b.source_name, b.period, b.record_count, b.status,
           b.error_message, b.metadata, b.started_at, b.finished_at,
           u.id AS user_id, u.full_name AS user_full_name, u.username AS user_username
    FROM audit.upload_batches b
    LEFT JOIN auth.users u ON u.id = b.uploaded_by
"""


def _to_response(row: dict, schema=UploadHistoryResponse):
    finished, started = row["finished_at"], row["started_at"]
    extra = {"metadata": row["metadata"]} if schema is UploadHistoryDetail else {}
    return schema(
        id=row["id"],
        jenis_sumber=row["source_type"],
        tabel_tujuan=row["target_table"],
        layer=(row["metadata"] or {}).get("layer"),
        nama_file=row["source_name"],
        periode=row["period"],
        jumlah_data=row["record_count"] or 0,
        status=row["status"],
        pesan_error=row["error_message"],
        diupload_oleh=Uploader(id=row["user_id"], nama_lengkap=row["user_full_name"], username=row["user_username"])
        if row["user_id"] else None,
        mulai=started,
        selesai=finished,
        durasi_detik=(finished - started).total_seconds() if finished else None,
        **extra,
    )


def list_uploads(db: Session, *, own_only_user_id: UUID | None, search: str | None, status: str | None,
                 source_type: str | None, target_table: str | None, layer: str | None, uploaded_by: UUID | None,
                 bulan: int | None, tahun: int | None, tanggal_dari: date | None, tanggal_sampai: date | None,
                 page: int, limit: int) -> dict:
    """`own_only_user_id` diisi untuk user tanpa hak kelola upload: hanya riwayat miliknya yang terlihat."""
    where, params = [], {}
    uploader = own_only_user_id or uploaded_by
    if uploader:
        where.append("b.uploaded_by = CAST(:uploader AS uuid)")
        params["uploader"] = str(uploader)
    if status:
        if status.upper() not in STATUSES:
            raise bad_request(f"status harus salah satu dari: {', '.join(STATUSES)}", field="status")
        where.append("b.status = :status")
        params["status"] = status.upper()
    if source_type:
        where.append("b.source_type = :source_type")
        params["source_type"] = source_type.upper()
    if target_table:
        where.append("b.target_table = :target_table")
        params["target_table"] = target_table
    if layer:
        where.append("b.metadata->>'layer' = :layer")
        params["layer"] = layer
    if bulan:
        where.append("EXTRACT(MONTH FROM b.period) = :bulan")
        params["bulan"] = bulan
    if tahun:
        where.append("EXTRACT(YEAR FROM b.period) = :tahun")
        params["tahun"] = tahun
    if tanggal_dari and tanggal_sampai and tanggal_sampai < tanggal_dari:
        raise bad_request("tanggal_sampai tidak boleh lebih awal dari tanggal_dari", field="tanggal_sampai")
    if tanggal_dari:
        where.append("b.started_at >= :tanggal_dari")
        params["tanggal_dari"] = tanggal_dari
    if tanggal_sampai:
        where.append("b.started_at < :tanggal_sampai")
        params["tanggal_sampai"] = tanggal_sampai + timedelta(days=1)
    if search:
        where.append("(b.source_name ILIKE :search OR b.target_table ILIKE :search"
                     " OR u.full_name ILIKE :search OR u.username ILIKE :search)")
        params["search"] = f"%{search}%"

    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "")
    return paginate_sql(db, sql, params, "started_at DESC, id", page, limit, _to_response)


def get_upload(db: Session, batch_id: UUID, *, own_only_user_id: UUID | None) -> UploadHistoryDetail:
    sql = _SELECT + " WHERE b.id = CAST(:id AS uuid)"
    params = {"id": str(batch_id)}
    if own_only_user_id:
        sql += " AND b.uploaded_by = CAST(:uploader AS uuid)"
        params["uploader"] = str(own_only_user_id)
    row = db.execute(text(sql), params).mappings().first()
    if row is None:
        raise not_found("Riwayat upload tidak ditemukan")
    return _to_response(dict(row), UploadHistoryDetail)
