"""Daftar data karantina (quarantine.rows): baris/fitur upload yang tidak lolos validasi.

Aturan akses sama dengan riwayat upload: pengelola upload melihat semua (termasuk karantina
migrasi lama tanpa batch), user lain hanya karantina dari upload miliknya sendiri.
"""
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.utils.pagination import paginate_sql

_SELECT = """
    SELECT q.id, q.source_table, q.source_id, q.reason_code, q.reason, q.quarantined_at,
           q.upload_batch_id, b.source_type, b.source_name, b.period, b.uploaded_by,
           u.full_name AS user_full_name, u.username AS user_username,
           {data} AS data
    FROM quarantine.rows q
    LEFT JOIN audit.upload_batches b ON b.id = q.upload_batch_id
    LEFT JOIN auth.users u ON u.id = b.uploaded_by
"""
# Daftar: fitur GeoJSON cukup properti-nya (geometri bisa besar); detail: data utuh.
_LIST_DATA = "CASE WHEN q.data ? 'properties' THEN q.data->'properties' ELSE q.data END"


def _to_response(row: dict) -> dict:
    return {
        "id": row["id"],
        "upload_batch_id": row["upload_batch_id"],
        "tabel_tujuan": row["source_table"],
        "no_baris": row["source_id"],
        "kode_alasan": row["reason_code"],
        "alasan": row["reason"],
        "data": row["data"],
        "jenis_sumber": row["source_type"],
        "nama_file": row["source_name"],
        "periode": row["period"],
        "diupload_oleh": {"id": row["uploaded_by"], "nama_lengkap": row["user_full_name"], "username": row["user_username"]}
        if row["uploaded_by"] else None,
        "dikarantina_pada": row["quarantined_at"],
    }


def _scope(own_only_user_id: UUID | None, where: list[str], params: dict) -> None:
    if own_only_user_id:
        where.append("b.uploaded_by = CAST(:uploader AS uuid)")
        params["uploader"] = str(own_only_user_id)


def list_rows(db: Session, *, own_only_user_id: UUID | None, upload_batch_id: UUID | None, target_table: str | None,
              reason_code: str | None, search: str | None, page: int, limit: int) -> dict:
    where, params = [], {}
    _scope(own_only_user_id, where, params)
    if upload_batch_id:
        where.append("q.upload_batch_id = CAST(:batch AS uuid)")
        params["batch"] = str(upload_batch_id)
    if target_table:
        where.append("q.source_table = :table")
        params["table"] = target_table
    if reason_code:
        where.append("q.reason_code = :code")
        params["code"] = reason_code.upper()
    if search:
        where.append("(q.reason ILIKE :search OR q.data::text ILIKE :search OR b.source_name ILIKE :search)")
        params["search"] = f"%{search}%"
    sql = _SELECT.format(data=_LIST_DATA) + (" WHERE " + " AND ".join(where) if where else "")
    return paginate_sql(db, sql, params, "quarantined_at DESC, id DESC", page, limit, _to_response)


def get_row(db: Session, row_id: int, *, own_only_user_id: UUID | None) -> dict:
    where, params = ["q.id = :id"], {"id": row_id}
    _scope(own_only_user_id, where, params)
    row = db.execute(text(_SELECT.format(data="q.data") + " WHERE " + " AND ".join(where)), params).mappings().first()
    if row is None:
        raise not_found("Data karantina tidak ditemukan")
    return _to_response(dict(row))
