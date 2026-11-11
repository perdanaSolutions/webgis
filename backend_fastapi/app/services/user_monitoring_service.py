"""
Monitoring user: siapa yang sedang login (online) dan siapa yang tidak.

Sumber status:
- REDIS_AUTH_ENABLED=true  -> registry sesi Redis (akurat: logout, login di perangkat lain, ganti password,
  dan kedaluwarsa sudah tercermin). `sumber` = "redis".
- REDIS_AUTH_ENABLED=false -> perkiraan dari log aktivitas: LOGIN sukses terakhir lebih baru daripada LOGOUT
  terakhir dan belum melewati masa berlaku token. `sumber` = "log_aktivitas".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.auth_session import active_sessions, auth_ttl_seconds
from app.utils.pagination import page_response

_LAST_ACTIVITY = """
    LEFT JOIN LATERAL (
        SELECT created_at, ip_address::text AS ip FROM audit.user_activities a
        WHERE a.user_id = u.id AND a.action = 'LOGIN' AND a.status = 'SUCCESS'
        ORDER BY created_at DESC LIMIT 1) li ON true
    LEFT JOIN LATERAL (
        SELECT created_at FROM audit.user_activities a
        WHERE a.user_id = u.id AND a.action = 'LOGOUT'
        ORDER BY created_at DESC LIMIT 1) lo ON true
    LEFT JOIN LATERAL (
        SELECT created_at FROM audit.user_activities a
        WHERE a.user_id = u.id
        ORDER BY created_at DESC LIMIT 1) la ON true
"""


def fetch_users(db: Session, search: str | None) -> list[dict]:
    """Semua akun non-service (opsional dicari) beserta jejak login/logout/aktivitas terakhirnya."""
    rows = db.execute(text(f"""
        SELECT u.id::text AS id, u.username, u.full_name, u.email, u.is_active, u.locked_at,
               COALESCE((SELECT array_agg(r.name ORDER BY r.name) FROM auth.user_roles ur
                         JOIN auth.roles r ON r.id = ur.role_id WHERE ur.user_id = u.id), '{{}}') AS roles,
               li.created_at AS login_terakhir, li.ip AS ip_terakhir,
               lo.created_at AS logout_terakhir, la.created_at AS aktivitas_terakhir
        FROM auth.users u {_LAST_ACTIVITY}
        WHERE NOT u.is_service_account
          AND (CAST(:q AS text) IS NULL OR u.username ILIKE :q OR u.full_name ILIKE :q OR u.email ILIKE :q)
    """), {"q": f"%{search.strip()}%" if search and search.strip() else None}).mappings().all()
    return [dict(r) for r in rows]


def _online_from_log(row: dict, now: datetime) -> bool:
    login, logout = row["login_terakhir"], row["logout_terakhir"]
    if not row["is_active"] or row["locked_at"] is not None or login is None:
        return False
    if logout is not None and logout >= login:
        return False
    return now - login < timedelta(seconds=auth_ttl_seconds())


def build_monitoring(users: list[dict], sessions: dict[str, dict] | None, *, status: str | None,
                     page: int, limit: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    items = []
    for row in users:
        session = sessions.get(row["id"]) if sessions is not None else None
        online = session is not None if sessions is not None else _online_from_log(row, now)
        login_sesi = datetime.fromtimestamp(session["login_terakhir"], timezone.utc) if session else None
        items.append({
            "id": row["id"],
            "username": row["username"],
            "nama_lengkap": row["full_name"],
            "email": row["email"],
            "role": list(row["roles"] or []),
            "akun_aktif": bool(row["is_active"]),
            "terkunci": row["locked_at"] is not None,
            "status": "online" if online else "offline",
            "jumlah_sesi": session["jumlah"] if session else (1 if online else 0),
            "login_terakhir": login_sesi or row["login_terakhir"],
            "logout_terakhir": row["logout_terakhir"],
            "aktivitas_terakhir": row["aktivitas_terakhir"],
            "ip_terakhir": row["ip_terakhir"],
        })
    online_count = sum(1 for i in items if i["status"] == "online")
    ringkasan = {"total_user": len(items), "online": online_count, "offline": len(items) - online_count}
    if status in ("online", "offline"):
        items = [i for i in items if i["status"] == status]
    floor = datetime.min.replace(tzinfo=timezone.utc)
    items.sort(key=lambda i: (i["status"] != "online", -(i["aktivitas_terakhir"] or floor).timestamp(),
                              (i["nama_lengkap"] or "").lower()))
    start = (page - 1) * limit
    response = page_response(len(items), page, limit, items[start:start + limit])
    response["ringkasan"] = ringkasan
    response["sumber"] = "redis" if sessions is not None else "log_aktivitas"
    return response


async def monitoring_users(db: Session, *, search: str | None, status: str | None, page: int, limit: int) -> dict:
    users = await run_in_threadpool(fetch_users, db, search)
    sessions = await active_sessions([u["id"] for u in users])
    return build_monitoring(users, sessions, status=status, page=page, limit=limit)
