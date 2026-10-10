"""Cache Redis API peta: kunci per user, dan versi naik setelah data ditulis."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt import encode

from app.core.config import settings
from app.core.map_cache import (
    MapRedisCacheMiddleware,
    cache_digest,
    is_map_invalidation,
    is_map_read,
    pack_body,
    set_store_versions_reader,
    unpack_body,
)
from app.core.redis_client import set_client_override


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.data: dict[str, bytes] = {}
        self.fail = fail
        self.sets = 0
        self.incrs = 0

    async def get(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        if self.fail:
            raise ConnectionError("redis down")
        self.data[key] = value
        self.sets += 1
        return True

    async def incr(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        current = int(self.data.get(key) or b"0") + 1
        self.data[key] = str(current).encode()
        self.incrs += 1
        return current

    async def ping(self):
        return True

    async def aclose(self):
        return None


def _token(user_id: str) -> str:
    return encode({"sub": user_id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture
def cached_app():
    fake = FakeRedis()
    set_client_override(fake)
    app = FastAPI()
    app.add_middleware(MapRedisCacheMiddleware)
    calls = {"n": 0}

    @app.get("/api/v1/spatial/geojson")
    def geojson(b: str = "", a: str = ""):
        calls["n"] += 1
        return {"type": "FeatureCollection", "n": calls["n"], "a": a, "b": b}

    @app.get("/api/v1/spatial/blok/detail")
    def missing():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="tidak ada")

    @app.post("/api/v1/spatial/sawit/upload-execute")
    def upload():
        return {"ok": True}

    @app.post("/api/v1/spatial/sawit/upload-analyze")
    def analyze():
        return {"ok": True}

    @app.post("/api/v1/areal-statement/import-excel")
    def imported():
        return {"ok": True}

    client = TestClient(app)
    yield client, fake, calls
    set_client_override(None)
    set_store_versions_reader(None)


def test_read_and_write_policy():
    assert is_map_read("GET", "/api/v1/spatial/geojson")
    assert is_map_read("GET", "/api/v1/spatial/sawit/geojson")
    assert is_map_read("GET", "/api/v1/spatial/blok/detail")
    assert is_map_read("GET", "/api/v1/spatial/history")
    assert not is_map_read("POST", "/api/v1/spatial/geojson")
    assert not is_map_read("GET", "/api/v1/users")

    assert is_map_invalidation("POST", "/api/v1/spatial/sawit/upload-execute")
    assert is_map_invalidation("POST", "/api/v1/spatial/sawit/upload")
    assert is_map_invalidation("DELETE", "/api/v1/spatial/cleanup-period")
    assert is_map_invalidation("POST", "/api/v1/areal-statement/import-excel")
    assert is_map_invalidation("POST", "/api/v1/pokok-produksi/import-produksi-tbs")
    assert is_map_invalidation("POST", "/api/v1/trx-rotasi-pusingan/import-rotasi-pusingan")
    assert is_map_invalidation("PUT", "/api/v1/akses-data/data/role/1")
    assert not is_map_invalidation("POST", "/api/v1/spatial/sawit/upload-analyze")
    assert not is_map_invalidation("POST", "/api/v1/spatial/sawit/analyze")
    assert not is_map_invalidation("GET", "/api/v1/spatial/geojson")


def test_query_order_does_not_change_key():
    user = "user-1"
    path = "/api/v1/spatial/geojson"
    assert cache_digest(user, path, b"b=2&a=1") == cache_digest(user, path, b"a=1&b=2")
    assert cache_digest(user, path, b"a=1") != cache_digest("user-2", path, b"a=1")
    assert cache_digest(user, path, b"a=1", (1, 3)) != cache_digest(user, path, b"a=1", (2, 3))
    assert cache_digest(user, path, b"a=1", (1, 3)) != cache_digest(user, path, b"a=1", (1, 4))


def test_new_store_version_is_not_served_from_old_cache(cached_app):
    client, _fake, calls = cached_app
    current = {"value": (3, 1)}
    set_store_versions_reader(lambda: current["value"])
    headers = {"Authorization": f"Bearer {_token('user-a')}"}
    first = client.get("/api/v1/spatial/geojson", headers=headers)
    assert first.headers["x-cache"] == "MISS"
    current["value"] = (4, 1)
    fresh = client.get("/api/v1/spatial/geojson", headers=headers)
    assert fresh.headers["x-cache"] == "MISS"
    assert fresh.json()["n"] == 2
    assert calls["n"] == 2


def test_pack_roundtrip_compresses_large_json():
    body = ('{"features":[' + ",".join(['{"t":"Point"}'] * 200) + "]}").encode()
    packed = pack_body(body)
    assert packed.startswith(b"\x01")
    assert unpack_body(packed) == body
    assert unpack_body(pack_body(b"{}")) == b"{}"


def test_second_get_is_served_from_redis(cached_app):
    client, fake, calls = cached_app
    headers = {"Authorization": f"Bearer {_token('user-a')}"}
    first = client.get("/api/v1/spatial/geojson", headers=headers, params={"a": "1", "b": "2"})
    second = client.get("/api/v1/spatial/geojson", headers=headers, params={"b": "2", "a": "1"})
    assert first.status_code == 200
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert second.json()["n"] == 1
    assert calls["n"] == 1
    assert fake.sets == 1


def test_users_do_not_share_cache(cached_app):
    client, _fake, calls = cached_app
    client.get("/api/v1/spatial/geojson", headers={"Authorization": f"Bearer {_token('user-a')}"})
    other = client.get("/api/v1/spatial/geojson", headers={"Authorization": f"Bearer {_token('user-b')}"})
    assert other.headers["x-cache"] == "MISS"
    assert other.json()["n"] == 2
    assert calls["n"] == 2


def test_anonymous_request_is_not_cached(cached_app):
    client, fake, calls = cached_app
    client.get("/api/v1/spatial/geojson")
    client.get("/api/v1/spatial/geojson")
    assert calls["n"] == 2
    assert fake.sets == 0


def test_errors_are_not_cached(cached_app):
    client, fake, calls = cached_app
    headers = {"Authorization": f"Bearer {_token('user-a')}"}
    first = client.get("/api/v1/spatial/blok/detail", headers=headers)
    second = client.get("/api/v1/spatial/blok/detail", headers=headers)
    assert first.status_code == 404
    assert second.status_code == 404
    assert fake.sets == 0


def test_successful_write_drops_cache_analyze_does_not(cached_app):
    client, fake, calls = cached_app
    headers = {"Authorization": f"Bearer {_token('user-a')}"}
    client.get("/api/v1/spatial/geojson", headers=headers)
    client.post("/api/v1/spatial/sawit/upload-analyze", headers=headers)
    cached = client.get("/api/v1/spatial/geojson", headers=headers)
    assert cached.headers["x-cache"] == "HIT"
    assert fake.incrs == 0

    client.post("/api/v1/spatial/sawit/upload-execute", headers=headers)
    client.post("/api/v1/areal-statement/import-excel", headers=headers)
    assert fake.incrs == 2
    fresh = client.get("/api/v1/spatial/geojson", headers=headers)
    assert fresh.headers["x-cache"] == "MISS"
    assert fresh.json()["n"] == 2
    assert calls["n"] == 2


def test_redis_outage_still_returns_data(cached_app):
    client, fake, calls = cached_app
    fake.fail = True
    headers = {"Authorization": f"Bearer {_token('user-a')}"}
    first = client.get("/api/v1/spatial/geojson", headers=headers)
    second = client.get("/api/v1/spatial/geojson", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["n"] == 2
    assert "x-cache" not in first.headers


def test_spatial_get_routes_are_covered():
    pytest.importorskip("geopandas")
    from fastapi.routing import APIRoute
    from app.main import app

    found = False
    for route in app.routes:
        if not isinstance(route, APIRoute) or "GET" not in route.methods:
            continue
        if not route.path.startswith(f"{settings.API_V1_STR}/spatial"):
            continue
        found = True
        assert is_map_read("GET", route.path), route.path
    assert found
