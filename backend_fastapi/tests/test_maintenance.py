"""Mode maintenance: endpoint status, middleware 503, path yang dikecualikan, fail open."""
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core import maintenance as m

API = "/api/v1"
ORIGIN = "https://webgis-uat.perdanasolusiteknologi.com"


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(m.MaintenanceMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get(f"{API}/system/maintenance")
    async def status():
        s = await m.get_status()
        return {"maintenance": bool(s["maintenance"]), "message": s["message"]}

    @app.get(f"{API}/pengumuman/")
    def pengumuman():
        return {"items": []}

    @app.get(f"{API}/users")
    def users():
        return {"items": []}

    return app


@pytest.fixture()
def client():
    yield TestClient(_app())
    m.set_status_override(None)


def test_off_passes(client):
    m.set_status_override({"maintenance": False, "message": "x"})
    assert client.get(f"{API}/users").status_code == 200
    assert client.get(f"{API}/system/maintenance").json()["maintenance"] is False


def test_on_blocks_with_503_and_cors(client):
    m.set_status_override({"maintenance": True, "message": "Sedang upgrade"})
    r = client.get(f"{API}/users", headers={"Origin": ORIGIN, "Authorization": "Bearer t"})
    assert r.status_code == 503
    assert r.headers["retry-after"] == str(m.RETRY_AFTER_SECONDS)
    assert r.headers["access-control-allow-origin"] == ORIGIN
    body = r.json()
    assert body["maintenance"] is True and body["message"] == "Sedang upgrade"


def test_on_exempt_paths(client):
    m.set_status_override({"maintenance": True, "message": "m"})
    assert client.get("/health").json() == {"status": "ok"}
    s = client.get(f"{API}/system/maintenance").json()
    assert s == {"maintenance": True, "message": "m"}
    pre = client.options(f"{API}/users", headers={
        "Origin": ORIGIN, "Access-Control-Request-Method": "GET"})
    assert pre.status_code == 200
    # cek deploy: pengumuman tanpa token lolos, dengan token diblokir
    assert client.get(f"{API}/pengumuman/").status_code == 200
    assert client.get(f"{API}/pengumuman/", headers={"Authorization": "Bearer t"}).status_code == 503


def test_fail_open_when_db_errors(monkeypatch, client):
    m.set_status_override(None)

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(m, "_read_from_db", boom)
    assert m.read_status_sync()["maintenance"] is False
    assert client.get(f"{API}/users").status_code == 200


def test_cache_and_parse(monkeypatch):
    m.set_status_override(None)
    calls = []

    def fake():
        calls.append(1)
        return {"maintenance": True, "message": "m"}

    monkeypatch.setattr(m, "_read_from_db", fake)
    m.read_status_sync()
    m.read_status_sync()
    assert len(calls) == 1
    m.clear_cache()
    for raw, want in [("true", True), ("TRUE", True), ('"true"', True), ("1", True),
                      ("false", False), ("", False), (None, False)]:
        assert m._parse_bool(raw) is want
