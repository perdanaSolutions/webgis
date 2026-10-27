"""Filter Kebun: 'Semua area' (area kosong) tetap dibatasi hak akses user di backend (tanpa database)."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import spatial as ep
from app.main import app
from app.services import map_service
from app.services.block_filter import BlockFilter

SCOPE = ("(es.area_id IN (SELECT id FROM master.areas WHERE upper(code) = ANY(:dsc_areas)))", {"dsc_areas": ["BERAU"]})


class FakeScope:
    def __init__(self, clause):
        self.clause = clause

    def block_clause(self):
        return self.clause


@pytest.fixture
def client(monkeypatch):
    seen = {}
    monkeypatch.setattr(ep.user_access, "resolve_scope", lambda db, user: FakeScope(user.scope))
    monkeypatch.setattr(ep.user_access, "hidden_feature_keys", lambda db, user: ())

    def fake_options(db, flt):
        seen["flt"] = flt
        return [{"blok_id": "1", "kode_blok": "B001", "kode_afd": "A1", "kode_est": "E1"}]

    def fake_geojson(db, flt, bulan, tahun, **kw):
        seen["flt"], seen["kw"] = flt, kw
        return {"type": "FeatureCollection", "features": []}

    monkeypatch.setattr(ep.map_service, "block_options", fake_options)
    monkeypatch.setattr(ep.map_service, "blocks_geojson", fake_geojson)
    user = SimpleNamespace(id=uuid.uuid4(), email="kebun@x", scope=SCOPE)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: None
    try:
        yield TestClient(app), seen, user
    finally:
        app.dependency_overrides.clear()


def test_semua_area_options_still_scoped_to_user(client):
    c, seen, _ = client
    r = c.get("/api/v1/spatial/blok/options")
    assert r.status_code == 200 and r.json()["data"][0]["kode_blok"] == "B001"
    flt = seen["flt"]
    assert flt.area is None  # Semua area
    assert SCOPE[0] in flt.extra_where and flt.extra_params["dsc_areas"] == ["BERAU"]


def test_semua_area_geojson_scoped_and_simplify_param(client):
    c, seen, _ = client
    r = c.get("/api/v1/spatial/geojson", params={"tahun": 2026, "simplify": 1})
    assert r.status_code == 200
    assert seen["flt"].area is None and SCOPE[0] in seen["flt"].extra_where
    assert seen["kw"]["simplify_m"] == 1


def test_user_without_access_gets_false_clause(client):
    c, seen, user = client
    user.scope = ("FALSE", {})
    c.get("/api/v1/spatial/blok/options", params={"area_id": "KUKAR"})
    assert seen["flt"].area == "KUKAR" and "FALSE" in seen["flt"].extra_where


def test_simplify_param_validated(client):
    c, _, _ = client
    assert c.get("/api/v1/spatial/geojson", params={"simplify": 50}).status_code == 422


def test_simplify_tolerance():
    assert map_service.simplify_tolerance(None) is None
    assert map_service.simplify_tolerance(0) is None
    assert map_service.simplify_tolerance(1) == pytest.approx(1 / 111_320)
    assert map_service.simplify_tolerance(999) == pytest.approx(20 / 111_320)


def test_block_options_query_uses_filter_and_limit():
    captured = {}

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [{"id": 7, "code": "B7", "kode_afd": "A1", "kode_est": "E1"}]

    class DB:
        def execute(self, sql, params):
            captured["sql"], captured["params"] = str(sql), params
            return Result()

    flt = BlockFilter(area="BERAU")
    flt.extra_where.append("FALSE")
    rows = map_service.block_options(DB(), flt)
    assert rows == [{"blok_id": "7", "kode_blok": "B7", "kode_afd": "A1", "kode_est": "E1"}]
    assert "FALSE" in captured["sql"] and captured["params"]["f_area"] == "BERAU"
    assert captured["params"]["lim"] == map_service.BLOCK_OPTIONS_LIMIT
