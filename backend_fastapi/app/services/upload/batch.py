"""Pencatatan proses upload di audit.upload_batches (dulu sys_upload_log)."""
import json
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def start_batch(
    db: Session,
    *,
    source_type: str,
    target_table: str,
    source_name: str | None,
    user_id: UUID | None,
    period: date | None,
    metadata: dict | None = None,
) -> UUID:
    batch_id = db.execute(
        text("""
            INSERT INTO audit.upload_batches (source_type, target_table, source_name, uploaded_by, period, metadata)
            VALUES (:source_type, :target_table, :source_name, :user_id, :period, CAST(:metadata AS jsonb))
            RETURNING id
        """),
        {
            "source_type": source_type, "target_table": target_table, "source_name": (source_name or "")[:255] or None,
            "user_id": str(user_id) if user_id else None, "period": period, "metadata": json.dumps(metadata or {}),
        },
    ).scalar_one()
    db.commit()
    return batch_id


def finish_batch(db: Session, batch_id: UUID, status: str, record_count: int, error: str | None, metadata: dict) -> None:
    db.execute(
        text("""
            UPDATE audit.upload_batches
            SET status = :status, record_count = :count, error_message = :error,
                metadata = COALESCE(metadata, '{}'::jsonb) || CAST(:metadata AS jsonb), finished_at = now()
            WHERE id = :id
        """),
        {"id": str(batch_id), "status": status, "count": max(record_count, 0), "error": error,
         "metadata": json.dumps(metadata, default=str)},
    )
    db.commit()


def final_status(success: int, total: int) -> str:
    if total > 0 and success == total:
        return "SUCCESS"
    if success > 0:
        return "PARTIAL_SUCCESS"
    return "FAILED"
