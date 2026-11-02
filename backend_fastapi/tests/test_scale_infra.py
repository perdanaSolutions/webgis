"""
Kesiapan horizontal scale: satu engine DB per proses, pool dari env, Redis cache terpisah opsional,
dan file liveness worker. Tidak butuh Postgres/Redis sungguhan.
"""
import asyncio
import os

import pytest

from app.core import redis_client
from app.core.config import settings


def test_satu_engine_bersama_dan_pool_dari_env():
    from app.core import database
    from app.db import session

    assert database.engine is session.engine  # dulu 2 engine -> 2x koneksi per proses
    opts = session.engine_options()
    assert opts["pool_size"] == settings.DB_POOL_SIZE
    assert opts["max_overflow"] == settings.DB_MAX_OVERFLOW
    assert opts["pool_recycle"] == settings.DB_POOL_RECYCLE_SECONDS
    assert opts["pool_timeout"] == settings.DB_POOL_TIMEOUT
    assert opts["pool_pre_ping"] is True
    assert session.engine.pool.size() == settings.DB_POOL_SIZE


def test_ddl_startup_dikunci_advisory_lock_transaksi():
    from app.db.ensure_activity_ip import REQUIRE_ACTIVITY_IP_SQL
    from app.services.data_version import _ENSURE_SQL

    for sql in (REQUIRE_ACTIVITY_IP_SQL, _ENSURE_SQL):
        assert "pg_advisory_xact_lock" in sql.split("CREATE", 1)[0]


@pytest.fixture()
def fresh_redis(monkeypatch):
    for name, value in (("_client", None), ("_cache_client", None), ("_override", None),
                        ("_down_until", 0.0), ("_cache_down_until", 0.0)):
        monkeypatch.setattr(redis_client, name, value)
    monkeypatch.setattr(settings, "REDIS_MAP_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://auth:6379/0")


def test_tanpa_redis_cache_url_cache_pakai_redis_url(fresh_redis, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_CACHE_URL", "")
    assert redis_client.cache_url() == "redis://auth:6379/0"
    assert not redis_client.cache_is_separate()
    monkeypatch.setattr(settings, "REDIS_CACHE_URL", "redis://auth:6379/0")
    assert not redis_client.cache_is_separate()


def test_redis_cache_terpisah_tidak_mengganggu_auth(fresh_redis, monkeypatch):
    monkeypatch.setattr(settings, "REDIS_CACHE_URL", "redis://cache:6379/0")
    opened = []

    class Fake:
        def __init__(self, url):
            self.url, self.closed = url, False

        async def aclose(self):
            self.closed = True

    async def fake_open(url):
        opened.append(url)
        return Fake(url)

    monkeypatch.setattr(redis_client, "_open", fake_open)

    async def scenario():
        cache = await redis_client.get_client()
        auth = await redis_client.get_auth_redis()
        assert cache.url == "redis://cache:6379/0" and auth.url == "redis://auth:6379/0"
        # Redis cache putus -> hanya cache yang ditandai mati; klien auth tetap.
        await redis_client.mark_down(cache, ConnectionError("reset"))
        assert redis_client._cache_client is None and cache.closed
        assert redis_client._client is auth and redis_client._down_until == 0.0
        assert await redis_client.get_client() is None  # jeda retry cache
        assert await redis_client.get_auth_redis() is auth
        await redis_client.shutdown()
        assert auth.closed

    asyncio.run(scenario())
    assert opened == ["redis://cache:6379/0", "redis://auth:6379/0"]


def test_worker_touch_alive(tmp_path, monkeypatch):
    from app.services.upload import jobs

    alive = tmp_path / "alive"
    monkeypatch.setattr(settings, "UPLOAD_WORKER_ALIVE_FILE", "")
    jobs.touch_alive()
    assert not alive.exists()
    monkeypatch.setattr(settings, "UPLOAD_WORKER_ALIVE_FILE", str(alive))
    jobs.touch_alive()
    first = alive.stat().st_mtime
    os.utime(alive, (first - 100, first - 100))
    jobs.touch_alive()
    assert alive.stat().st_mtime > first - 100
