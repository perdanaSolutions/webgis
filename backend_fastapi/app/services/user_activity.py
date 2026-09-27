"""Catatan aktivitas user di audit.user_activities, plus pelaku untuk trigger audit database."""
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.client_ip import current_client_ip

_INSERT_ACTIVITY = text("""
    INSERT INTO audit.user_activities
        (user_id, action, resource, record_id, ip_address, status, detail)
    VALUES
        (CAST(:user_id AS uuid), :action, :resource, :record_id,
         CAST(:ip_address AS inet), :status, CAST(:detail AS jsonb))
""")


def insert_user_activity(
    db: Session,
    *,
    user_id,
    action: str,
    resource: str,
    status: str = "SUCCESS",
    record_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Satu baris audit. ip_address wajib dan dikonversi ke inet."""
    ip = ip_address or current_client_ip()
    db.execute(
        _INSERT_ACTIVITY,
        {
            "user_id": str(user_id) if user_id else None,
            "action": action,
            "resource": resource,
            "record_id": record_id,
            "ip_address": ip,
            "status": status,
            "detail": json.dumps(detail) if detail is not None else None,
        },
    )


def record_user_activity(
    db: Session,
    user,
    action: str,
    resource: str,
    record_id: str | None = None,
    detail: dict | None = None,
) -> None:
    """Satu transaksi dengan perubahan data. Caller yang melakukan commit."""
    user_id = str(user.id)
    db.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
    insert_user_activity(
        db,
        user_id=user.id,
        action=action,
        resource=resource,
        record_id=record_id,
        detail=detail,
    )
