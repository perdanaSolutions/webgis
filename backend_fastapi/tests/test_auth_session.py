"""Sesi JWT Redis (ADR-001): login menulis jti, logout/password mencabut di semua 'instance'."""
import asyncio
import uuid

import pytest
from jwt import decode

from app.core import redis_client
from app.core.auth_session import (
    AuthSessionRevoked,
    assert_session,
    create_session,
    new_jti,
    revoke_jti,
    revoke_user,
)
from app.core.config import settings
from app.core.redis_client import set_client_override
from app.core.security import create_access_token


def _bearer_with_session(user_id: str) -> dict:
    """Token uji yang juga terdaftar di Redis (wajib saat REDIS_AUTH_ENABLED)."""
    jti = new_jti()
    token = create_access_token(user_id, jti=jti)
    asyncio.run(create_session(jti, str(user_id)))
    return {"Authorization": f"Bearer {token}"}


class FakeAuthRedis:
    """Subset perintah Redis yang dipakai auth_session (decode_responses=False)."""

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.strings: dict[str, bytes] = {}
        self.sets: dict[str, set[bytes]] = {}
        self.ttls: dict[str, int] = {}

    def _k(self, key) -> str:
        return key.decode() if isinstance(key, bytes) else str(key)

    async def hset(self, key, mapping=None, **_kwargs):
        k = self._k(key)
        bucket = self.hashes.setdefault(k, {})
        for field, value in (mapping or {}).items():
            f = field if isinstance(field, bytes) else str(field).encode()
            v = value if isinstance(value, bytes) else str(value).encode()
            bucket[f] = v
        return len(mapping or {})

    async def hget(self, key, field):
        bucket = self.hashes.get(self._k(key), {})
        f = field if isinstance(field, bytes) else str(field).encode()
        return bucket.get(f)

    async def exists(self, *keys):
        n = 0
        for key in keys:
            k = self._k(key)
            if k in self.hashes or k in self.strings or k in self.sets:
                n += 1
        return n

    async def delete(self, *keys):
        n = 0
        for key in keys:
            k = self._k(key)
            existed = False
            if k in self.hashes:
                del self.hashes[k]
                existed = True
            if k in self.strings:
                del self.strings[k]
                existed = True
            if k in self.sets:
                del self.sets[k]
                existed = True
            self.ttls.pop(k, None)
            if existed:
                n += 1
        return n

    async def set(self, key, value, ex=None):
        k = self._k(key)
        self.strings[k] = value if isinstance(value, bytes) else str(value).encode()
        if ex is not None:
            self.ttls[k] = int(ex)
        return True

    async def get(self, key):
        return self.strings.get(self._k(key))

    async def sadd(self, key, *members):
        k = self._k(key)
        bucket = self.sets.setdefault(k, set())
        before = len(bucket)
        for m in members:
            bucket.add(m if isinstance(m, bytes) else str(m).encode())
        return len(bucket) - before

    async def srem(self, key, *members):
        k = self._k(key)
        bucket = self.sets.get(k)
        if not bucket:
            return 0
        n = 0
        for m in members:
            raw = m if isinstance(m, bytes) else str(m).encode()
            if raw in bucket:
                bucket.discard(raw)
                n += 1
        return n

    async def smembers(self, key):
        return set(self.sets.get(self._k(key), set()))

    async def expire(self, key, ttl):
        self.ttls[self._k(key)] = int(ttl)
        return True

    async def ttl(self, key):
        return self.ttls.get(self._k(key), -2)

    async def ping(self):
        return True

    async def aclose(self):
        return None


@pytest.fixture
def auth_redis(monkeypatch):
    fake = FakeAuthRedis()
    monkeypatch.setattr(settings, "REDIS_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
    set_client_override(fake)
    yield fake
    set_client_override(None)


def test_create_assert_revoke_jti(auth_redis):
    async def _run():
        jti = "jti-one"
        uid = str(uuid.uuid4())
        await create_session(jti, uid, ttl=120)
        assert await auth_redis.exists(f"gis:auth:sess:{jti}") == 1
        await assert_session(jti)
        await revoke_jti(jti, user_id=uid)
        with pytest.raises(AuthSessionRevoked):
            await assert_session(jti)
        assert await auth_redis.exists(f"gis:auth:deny:{jti}") == 1

    asyncio.run(_run())


def test_revoke_user_all_jti(auth_redis):
    async def _run():
        uid = str(uuid.uuid4())
        await create_session("a", uid, ttl=60)
        await create_session("b", uid, ttl=60)
        await revoke_user(uid)
        with pytest.raises(AuthSessionRevoked):
            await assert_session("a")
        with pytest.raises(AuthSessionRevoked):
            await assert_session("b")

    asyncio.run(_run())


def test_access_token_contains_jti():
    token = create_access_token("user-1", jti="fixed-jti")
    payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["jti"] == "fixed-jti"
    assert payload["sub"] == "user-1"
    assert "iat" in payload


def test_logout_revokes_token_across_requests(client, superadmin_id, auth_redis):
    """Simulasi multi-instance: registry Redis bersama; setelah logout token ditolak."""
    admin = _bearer_with_session(superadmin_id)
    roles = client.get("/api/v1/roles/", headers=admin).json()
    viewer = next(r for r in roles if r["nama"] != "superadmin")
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "username": f"sess_{suffix}",
        "email": f"sess_{suffix}@example.com",
        "nama_lengkap": "Sesi Redis",
        "role_ids": [viewer["id"]],
        "password": "rahasia123",
    }
    assert client.post("/api/v1/users/", headers=admin, json=payload).status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": payload["username"], "password": "rahasia123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    claims = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert claims.get("jti")
    assert f"gis:auth:sess:{claims['jti']}" in auth_redis.hashes

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    # Request berikutnya (instance mana pun yang baca Redis yang sama) harus 401
    denied = client.get("/api/v1/auth/me", headers=headers)
    assert denied.status_code == 401
    assert denied.json()["errors"][0]["field"] == "auth"


def test_password_change_revokes_all_sessions(client, superadmin_id, auth_redis):
    admin = _bearer_with_session(superadmin_id)
    roles = client.get("/api/v1/roles/", headers=admin).json()
    viewer = next(r for r in roles if r["nama"] != "superadmin")
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "username": f"pwd2_{suffix}",
        "email": f"pwd2_{suffix}@example.com",
        "nama_lengkap": "Revoke Password",
        "role_ids": [viewer["id"]],
        "password": "rahasia123",
    }
    assert client.post("/api/v1/users/", headers=admin, json=payload).status_code == 201

    t1 = client.post("/api/v1/auth/login", json={"email": payload["username"], "password": "rahasia123"}).json()["access_token"]
    h1 = {"Authorization": f"Bearer {t1}"}

    assert client.put(
        "/api/v1/auth/me/password",
        headers=h1,
        json={"password_lama": "rahasia123", "password_baru": "baru12345"},
    ).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h1).status_code == 401


def test_non_admin_login_revokes_previous_session(client, superadmin_id, auth_redis):
    """Satu akun satu pengguna: login baru non-Admin mencabut sesi lama."""
    admin = _bearer_with_session(superadmin_id)
    roles = client.get("/api/v1/roles/", headers=admin).json()
    viewer = next(r for r in roles if r["nama"] != "superadmin")
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "username": f"single_{suffix}",
        "email": f"single_{suffix}@example.com",
        "nama_lengkap": "Single Session",
        "role_ids": [viewer["id"]],
        "password": "rahasia123",
    }
    assert client.post("/api/v1/users/", headers=admin, json=payload).status_code == 201
    cred = {"email": payload["username"], "password": "rahasia123"}

    h1 = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json=cred).json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=h1).status_code == 200
    h2 = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json=cred).json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=h1).status_code == 401
    assert client.get("/api/v1/auth/me", headers=h2).status_code == 200


def test_admin_login_keeps_multiple_sessions(client, auth_redis):
    cred = {"email": settings.SEED_ADMIN_USERNAME, "password": settings.SEED_ADMIN_PASSWORD}
    r1 = client.post("/api/v1/auth/login", json=cred)
    if r1.status_code != 200:
        pytest.skip("kredensial superadmin seed tidak tersedia di env tes")
    h1 = {"Authorization": "Bearer " + r1.json()["access_token"]}
    h2 = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json=cred).json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=h1).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h2).status_code == 200


def test_health_reports_redis_auth_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_AUTH_ENABLED", False)
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["auth"] == "stateless"
    assert body["redis_auth"] == "disabled"

    monkeypatch.setattr(settings, "REDIS_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
    assert redis_client.auth_enabled() is True
    assert client.get("/health").json()["redis_auth"] == "enabled"


def test_token_without_session_rejected_when_auth_on(client, auth_redis, superadmin_id):
    """Token dibuat tanpa create_session (mis. skrip) ditolak bila REDIS_AUTH_ENABLED."""
    headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


# ---------- Monitoring user (GET /monitoring/users) ----------

def _create_user(client, admin_headers, prefix: str) -> dict:
    roles = client.get("/api/v1/roles/", headers=admin_headers).json()
    viewer = next(r for r in roles if r["nama"] != "superadmin")
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "username": f"{prefix}_{suffix}",
        "email": f"{prefix}_{suffix}@example.com",
        "nama_lengkap": f"Monitor {suffix}",
        "role_ids": [viewer["id"]],
        "password": "rahasia123",
    }
    assert client.post("/api/v1/users/", headers=admin_headers, json=payload).status_code == 201
    return payload


def _monitor(client, headers, **params) -> dict:
    response = client.get("/api/v1/monitoring/users", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_monitoring_users_online_then_offline_after_logout(client, superadmin_id, auth_redis):
    admin = _bearer_with_session(superadmin_id)
    user = _create_user(client, admin, "mon")

    before = _monitor(client, admin, search=user["username"])
    assert before["sumber"] == "redis"
    assert [r["status"] for r in before["data"]] == ["offline"]
    assert before["ringkasan"] == {"total_user": 1, "online": 0, "offline": 1}

    token = client.post("/api/v1/auth/login", json={"email": user["username"], "password": "rahasia123"}).json()["access_token"]
    online = _monitor(client, admin, search=user["username"])
    row = online["data"][0]
    assert (row["status"], row["jumlah_sesi"]) == ("online", 1)
    assert row["login_terakhir"] and row["ip_terakhir"]
    assert _monitor(client, admin, search=user["username"], status="offline")["data"] == []

    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    after = _monitor(client, admin, search=user["username"])
    assert after["data"][0]["status"] == "offline"
    assert after["data"][0]["logout_terakhir"]


def test_monitoring_users_requires_permission(client, superadmin_id, auth_redis):
    admin = _bearer_with_session(superadmin_id)
    user = _create_user(client, admin, "monforbid")
    token = client.post("/api/v1/auth/login", json={"email": user["username"], "password": "rahasia123"}).json()["access_token"]
    denied = client.get("/api/v1/monitoring/users", headers={"Authorization": f"Bearer {token}"})
    assert denied.status_code == 403
    assert client.get("/api/v1/monitoring/users").status_code == 401


def test_monitoring_users_log_fallback_when_redis_auth_off(client, superadmin_id, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_AUTH_ENABLED", False)
    headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}
    result = _monitor(client, headers, limit=100)
    assert result["sumber"] == "log_aktivitas"
    assert result["ringkasan"]["total_user"] == result["ringkasan"]["online"] + result["ringkasan"]["offline"]


def test_active_sessions_ignores_expired_jti(auth_redis):
    live, expired = new_jti(), new_jti()
    asyncio.run(create_session(live, "u-1"))
    asyncio.run(create_session(expired, "u-1"))
    del auth_redis.hashes[f"gis:auth:sess:{expired}"]  # sess kedaluwarsa, jti masih tercatat di set user
    from app.core.auth_session import active_sessions
    result = asyncio.run(active_sessions(["u-1", "u-2"]))
    assert set(result) == {"u-1"} and result["u-1"]["jumlah"] == 1


def test_active_sessions_none_when_redis_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_AUTH_ENABLED", False)
    from app.core.auth_session import active_sessions
    assert asyncio.run(active_sessions(["u-1"])) is None


def test_build_monitoring_log_mode_rules():
    from datetime import datetime, timedelta, timezone
    from app.services.user_monitoring_service import build_monitoring

    now = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)

    def row(uid, login, logout=None, active=True, locked=None):
        return {"id": uid, "username": uid, "full_name": uid, "email": f"{uid}@x", "is_active": active,
                "locked_at": locked, "roles": ["viewer"], "login_terakhir": login, "ip_terakhir": "10.0.0.1",
                "logout_terakhir": logout, "aktivitas_terakhir": login}

    ttl = timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    users = [
        row("masuk", now - timedelta(minutes=5)),
        row("sudah_keluar", now - timedelta(minutes=5), logout=now - timedelta(minutes=1)),
        row("login_ulang", now - timedelta(minutes=5), logout=now - timedelta(minutes=9)),
        row("kedaluwarsa", now - ttl - timedelta(minutes=1)),
        row("nonaktif", now - timedelta(minutes=5), active=False),
        row("terkunci", now - timedelta(minutes=5), locked=now),
        row("belum_pernah", None),
    ]
    result = build_monitoring(users, None, status=None, page=1, limit=50, now=now)
    status = {r["username"]: r["status"] for r in result["data"]}
    assert status == {"masuk": "online", "login_ulang": "online", "sudah_keluar": "offline",
                      "kedaluwarsa": "offline", "nonaktif": "offline", "terkunci": "offline",
                      "belum_pernah": "offline"}
    assert result["ringkasan"] == {"total_user": 7, "online": 2, "offline": 5}
    assert [r["status"] for r in result["data"][:2]] == ["online", "online"]  # online di urutan teratas
    only_online = build_monitoring(users, None, status="online", page=1, limit=1, now=now)
    assert only_online["total_data"] == 2 and only_online["total_page"] == 2 and len(only_online["data"]) == 1
