"""Pilihan "Semua" di filter kebun tetap dibatasi hak akses data user."""
from app.core import map_cache
from app.services.block_filter import BlockFilter
from app.services.layers import layer_service, sawit_service
from app.services.layers.specs import LAYER_SPECS
from app.services.user_access import DataScope

LEVELS = ("area", "company", "estate", "division")


def test_superadmin_tidak_difilter():
    s = DataScope(unrestricted=True)
    assert all(s.hierarchy_clause(lv) is None for lv in LEVELS)
    assert s.block_clause() is None


def test_tanpa_grant_kosong_di_semua_level():
    s = DataScope()
    assert all(s.hierarchy_clause(lv) == ("FALSE", {}) for lv in LEVELS)
    assert s.block_clause() == ("FALSE", {})
    assert s.hierarchy_clause("lain") == ("FALSE", {})


def test_grant_afdeling_saja_hanya_jalur_induk():
    s = DataScope(divisions=[7], visible_areas=["KUTIM4"])
    area_sql, area_p = s.hierarchy_clause("area")
    assert area_p["dsc_areas"] == ["KUTIM4"] and area_p["dsc_divisions"] == [7]
    co_sql, co_p = s.hierarchy_clause("company")
    assert "dv.id = ANY" in co_sql and co_p == {"dsc_divisions": [7]}
    es_sql, es_p = s.hierarchy_clause("estate")
    assert "FROM master.divisions WHERE id = ANY" in es_sql and es_p == {"dsc_divisions": [7]}
    dv_sql, dv_p = s.hierarchy_clause("division")
    assert dv_sql == "(dv.id = ANY(CAST(:dsc_divisions AS bigint[])))" and dv_p == {"dsc_divisions": [7]}
    bl_sql, bl_p = s.block_clause()
    assert bl_p == {"dsc_divisions": [7]}


def test_grant_estate_dan_pt_multi():
    s = DataScope(companies=[1, 2], estates=[30])
    sql, p = s.block_clause()
    assert " OR " in sql and p == {"dsc_companies": [1, 2], "dsc_estates": [30]}
    assert "dsc_divisions" not in s.hierarchy_clause("division")[1]


def test_grant_area():
    s = DataScope(area_codes=["kutim4"], visible_areas=["kutim4"])
    for lv in ("company", "estate", "division"):
        assert s.hierarchy_clause(lv)[1]["dsc_areas"] == ["KUTIM4"]
    assert s.block_clause()[1] == {"dsc_areas": ["KUTIM4"]}


def test_semua_dengan_scope_tetap_terbatas_dan_id_luar_scope_kosong():
    flt = BlockFilter(kode_pt="PT-LAIN")
    sql, p = DataScope(estates=[30]).block_clause()
    flt.extra_where.append(sql); flt.extra_params.update(p)
    _, where, params = flt.sql()
    assert "es.id = ANY" in where and params["dsc_estates"] == [30]
    assert " AND " in where  # PT yang diminta DAN scope -> di luar scope = kosong


def test_cache_key_beda_per_user_dan_versi():
    a = map_cache.cache_digest("u1", "/api/v1/spatial/geojson", b"simplify=1")
    b = map_cache.cache_digest("u2", "/api/v1/spatial/geojson", b"simplify=1")
    c = map_cache.cache_digest("u1", "/api/v1/spatial/geojson", b"simplify=1", (1, 0))
    assert len({a, b, c}) == 3


def test_perubahan_hak_akses_membatalkan_cache():
    base = "/api/v1"
    for path in ("/akses-data/x", "/roles/x", "/users/x"):
        assert map_cache.is_map_invalidation("PUT", base + path)


class _Db:
    def __init__(self):
        self.sql = None; self.params = None

    def execute(self, sql, params=None):
        self.sql, self.params = str(sql), params or {}
        return self

    def mappings(self):
        return self

    def all(self):
        return []


def _scoped():
    flt = BlockFilter()
    sql, p = DataScope(estates=[30]).block_clause()
    flt.extra_where.append(sql); flt.extra_params.update(p)
    return flt


def test_list_layer_ikut_scope():
    db = _Db()
    layer_service.list_rows(db, next(iter(LAYER_SPECS.values())) if isinstance(LAYER_SPECS, dict) else LAYER_SPECS[0], 1, 2025, None, _scoped())
    assert "es.id = ANY" in db.sql and db.params["dsc_estates"] == [30]


def test_list_sawit_ikut_scope(monkeypatch):
    seen = {}
    monkeypatch.setattr(sawit_service, "_query", lambda db, flt, period: seen.setdefault("flt", flt) and [])
    sawit_service.list_rows(None, 1, 2025, "B01", 2010, _scoped())
    flt = seen["flt"]
    assert flt.blok == "B01" and flt.tahun_tanam == "2010" and flt.extra_params["dsc_estates"] == [30]
