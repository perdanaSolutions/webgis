"""
Cek login tidak boleh membekukan event loop saat DB lambat (insiden 4 Nov 2026: PgBouncer penuh, query menunggu
sampai 120 dtk, /health tidak terjawab, HAProxy menandai semua replika DOWN), dan ubin foto udara tidak
menjadi satu query DB per ubin.
"""
import asyncio
import time
import uuid

import pytest
from fastapi import HTTPException

from app.api import deps
from app.core.config import settings
from app.core.security import create_access_token

DB_LAMBAT = 0.5


async def _loop_tetap_jalan(coro) -> int:
    """Jalankan `coro` sambil menghitung detak event loop tiap 10 ms selama coro berjalan."""
    ticks = 0
    done = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        await coro
    finally:
        done.set()
        await task
    return ticks


class _User:
    def __init__(self, user_id):
        self.id = user_id
        self.is_active = True
        self.is_service_account = False


class _Session:
    def expunge(self, obj):
        pass

    def close(self):
        pass


@pytest.fixture()
def fake_db(monkeypatch):
    """DB tiruan yang lambat; menghitung berapa kali user dibaca."""
    calls = []

    def slow_load(db, payload, is_service_token, set_actor=True):
        calls.append(payload["sub"])
        time.sleep(DB_LAMBAT)  # sinkron, seperti query yang menunggu PgBouncer
        return _User(payload["sub"])

    monkeypatch.setattr(deps, "_load_user", slow_load)
    monkeypatch.setattr(deps, "SessionLocal", _Session)
    deps.clear_user_cache()
    yield calls
    deps.clear_user_cache()


def _token(user_id=None):
    return create_access_token(user_id or str(uuid.uuid4()))


def test_get_current_user_tidak_membekukan_event_loop(fake_db):
    ticks = asyncio.run(_loop_tetap_jalan(deps.get_current_user(db=_Session(), token=_token())))
    # Loop beku -> ticks ~0. Loop bebas -> ~DB_LAMBAT / 10 ms = ~50.
    assert ticks >= 20
    assert len(fake_db) == 1


def test_ubin_tidak_membekukan_event_loop(fake_db):
    ticks = asyncio.run(_loop_tetap_jalan(deps.get_current_user_released(token=_token())))
    assert ticks >= 20


def test_cek_permission_tidak_membekukan_event_loop(monkeypatch):
    def slow_permission(db, user, permission):
        time.sleep(DB_LAMBAT)
        return True

    monkeypatch.setattr(deps, "user_has_permission", slow_permission)
    checker = deps.PermissionChecker("upload:geojson")
    ticks = asyncio.run(_loop_tetap_jalan(checker(current_user=_User("u"), db=_Session())))
    assert ticks >= 20


def test_ubin_satu_layar_cukup_satu_query_user(fake_db):
    token = _token()

    async def satu_layar():
        await deps.get_current_user_released(token=token)  # ubin pertama mengisi cache
        await asyncio.gather(*[deps.get_current_user_released(token=token) for _ in range(30)])

    asyncio.run(satu_layar())
    assert len(fake_db) == 1


def test_cache_user_kedaluwarsa_dibaca_ulang(fake_db, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_USER_CACHE_SECONDS", 0)  # tanpa cache
    token = _token()
    asyncio.run(deps.get_current_user_released(token=token))
    asyncio.run(deps.get_current_user_released(token=token))
    assert len(fake_db) == 2


def test_cache_per_user(fake_db):
    asyncio.run(deps.get_current_user_released(token=_token()))
    asyncio.run(deps.get_current_user_released(token=_token()))
    assert len(fake_db) == 2


def test_user_ditolak_tidak_masuk_cache(monkeypatch):
    calls = []

    def inactive(db, payload, is_service_token, set_actor=True):
        calls.append(1)
        raise HTTPException(status_code=400, detail="Akun tidak aktif")

    monkeypatch.setattr(deps, "_load_user", inactive)
    monkeypatch.setattr(deps, "SessionLocal", _Session)
    deps.clear_user_cache()
    token = _token()
    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(deps.get_current_user_released(token=token))
        assert exc.value.status_code == 400
    assert len(calls) == 2
    deps.clear_user_cache()


def test_ubin_tetap_cek_sesi_redis_setiap_request(fake_db, monkeypatch):
    """Logout harus langsung berlaku walau user ada di cache."""
    from app.core.auth_session import AuthSessionRevoked

    state = {"revoked": False, "checks": 0}

    async def assert_session(jti):
        state["checks"] += 1
        if state["revoked"]:
            raise AuthSessionRevoked("logout")

    monkeypatch.setattr(deps, "assert_session", assert_session)
    token = _token()
    asyncio.run(deps.get_current_user_released(token=token))
    state["revoked"] = True
    with pytest.raises(HTTPException) as exc:
        asyncio.run(deps.get_current_user_released(token=token))
    assert exc.value.status_code == 401
    assert state["checks"] == 2
    assert len(fake_db) == 1  # DB tidak ditanya ulang, tapi sesi tetap dicek


def test_user_nonaktif_sungguhan_ditolak(client, superadmin_id, monkeypatch):
    """Integrasi dengan DB test: user tidak ada -> 404, tanpa token -> 401 (cache tidak melonggarkan)."""
    deps.clear_user_cache()
    response = client.get("/api/v1/basemap/foto-udara/status",
                          headers={"Authorization": f"Bearer {_token(str(uuid.uuid4()))}"})
    assert response.status_code == 404
    assert client.get("/api/v1/basemap/foto-udara/status").status_code == 401
