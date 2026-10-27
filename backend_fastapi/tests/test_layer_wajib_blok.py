"""Semua layer wajib terikat blok: config, upload, template, dan read endpoint ikut scope wilayah."""
import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import geo_catalog
from app.services import user_access
from app.services.block_filter import BlockFilter
from app.services.layers import catalog_service
from app.services.upload import template
from app.services.user_access import DataScope

LAYER = {"kode": "embung", "nama": "Embung", "geometry_type": "POINT", "table_name": "spatial.geo_dyn_embung",
         "relasi_blok": True}
LEGACY_NO_BLOCK = {**LAYER, "relasi_blok": False}


class _NoDb:
    def execute(self, *a, **k):  # pragma: no cover - tidak boleh tersentuh
        raise AssertionError("DB tidak boleh dipanggil")


def _status(exc):
    return getattr(exc, "status_code", None)


def test_create_layer_tolak_relasi_blok_false():
    with pytest.raises(HTTPException) as e:
        catalog_service.create_layer(_NoDb(), kode="x", nama="x", deskripsi=None, geometry_type="POINT",
                                     relasi_blok=False, kolom=[{"nama_kolom": "a", "tipe": "text"}], created_by=None)
    assert _status(e.value) == 400


def test_register_legacy_tolak_relasi_blok_false():
    with pytest.raises(HTTPException) as e:
        catalog_service.register_legacy(_NoDb(), kode="x", nama="x", deskripsi=None, table_name="spatial.x",
                                        geometry_type="POINT", relasi_blok=False, endpoints={})
    assert _status(e.value) == 400


def test_upload_layer_tanpa_relasi_blok_ditolak():
    with pytest.raises(HTTPException):
        catalog_service._prepare(_NoDb(), LEGACY_NO_BLOCK, b"{}")


def test_default_legacy_semua_relasi_blok():
    assert all(layer["relasi_blok"] for layer in catalog_service.DEFAULT_LEGACY_LAYERS)


def test_template_generic_kolom_blok_wajib_walau_flag_lama_false():
    for layer in (LAYER, LEGACY_NO_BLOCK):
        tpl = template.generic_template(layer, [])
        req = {f.name for f in tpl.fields if f.required}
        assert {"Afdeling", "Blok"} <= req and tpl.fields[0].required
        assert tpl.notes == (template.BLOCK_NOTE,)


def _scope(monkeypatch, scope):
    monkeypatch.setattr(user_access, "resolve_scope", lambda db, user: scope)


def test_read_layer_berelasi_blok_ikut_scope(monkeypatch):
    _scope(monkeypatch, DataScope(estates=[30]))
    flt = geo_catalog._scoped_filter(None, object(), LAYER, BlockFilter(), None)
    assert flt.extra_params == {"dsc_estates": [30]}


def test_read_layer_tanpa_relasi_blok_restricted_404(monkeypatch):
    _scope(monkeypatch, DataScope(estates=[30]))
    with pytest.raises(HTTPException) as e:
        geo_catalog._scoped_filter(None, object(), LEGACY_NO_BLOCK, BlockFilter(), None)
    assert _status(e.value) == 404


def test_read_superadmin_lihat_semua(monkeypatch):
    _scope(monkeypatch, DataScope(unrestricted=True))
    assert geo_catalog._scoped_filter(None, object(), LEGACY_NO_BLOCK, BlockFilter(), None).extra_where == []
    assert geo_catalog._scoped_filter(None, object(), LAYER, BlockFilter(), None).extra_where == []


def test_user_tanpa_grant_kosong(monkeypatch):
    _scope(monkeypatch, DataScope())
    flt = geo_catalog._scoped_filter(None, object(), LAYER, BlockFilter(blok="B01"), None)
    assert flt.extra_where == ["FALSE"]


def test_where_generic_join_blok_dan_scope():
    flt = BlockFilter()
    flt.extra_where.append("(es.id = ANY(CAST(:dsc_estates AS bigint[])))")
    flt.extra_params["dsc_estates"] = [30]
    joins, where, params = catalog_service._where(LAYER, None, flt)
    assert "JOIN master.blocks bl ON bl.id = t.block_id" in joins and "es.id = ANY" in where
