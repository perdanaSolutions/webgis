import asyncio

import pytest

from app.core.config import settings
from app.services import foto_udara_service as fu


@pytest.fixture(autouse=True)
def _cfg(monkeypatch):
    monkeypatch.setattr(settings, "FOTO_UDARA_WMS_URL", "https://digilink.example/fu/wms")
    monkeypatch.setattr(settings, "FOTO_UDARA_WMS_TOKEN", "tok-rahasia")
    monkeypatch.setattr(settings, "FOTO_UDARA_WMS_LAYERS", "tpgis:tpgis_fu")


def test_getmap_query_aman_dan_token_hanya_di_upstream():
    q = fu.build_getmap_query({"BBOX": "1,2,3,4", "WIDTH": "256", "HEIGHT": "256", "SRS": "EPSG:3857",
                               "LAYERS": "tpgis:tpgis_fu", "FORMAT": "image/png", "token": "dari-browser", "evil": "x"})
    assert q["layers"] == "tpgis:tpgis_fu" and q["srs"] == "EPSG:3857" and "evil" not in q and "token" not in q
    url = fu._upstream_url(q)
    assert "token=tok-rahasia" in url and "dari-browser" not in url


def test_layer_lain_ditolak():
    with pytest.raises(fu.FotoUdaraError) as exc:
        fu.build_getmap_query({"bbox": "1,2,3,4", "layers": "tpgis:TPA-SGA"})
    assert exc.value.reason == "layer_not_found" and exc.value.status == 404


@pytest.mark.parametrize("params", [{"bbox": "1,2,3"}, {"bbox": "a,b,c,d"}, {"bbox": "1,2,3,4", "width": "5000"},
                                    {"bbox": "1,2,3,4", "srs": "EPSG:32750"}, {"bbox": "1,2,3,4", "format": "text/html"}])
def test_parameter_buruk(params):
    with pytest.raises(fu.FotoUdaraError) as exc:
        fu.build_getmap_query(params)
    assert exc.value.status == 400


def test_klasifikasi_jawaban_geoserver():
    assert fu.classify(200, "image/png", b"\x89PNG") is None
    assert fu.classify(401, "text/html", b"").reason == "unauthorized"
    xml = b'<ServiceExceptionReport><ServiceException code="LayerNotDefined" locator="layers">Could not find layer tpgis:TPA-SGA</ServiceException></ServiceExceptionReport>'
    err = fu.classify(200, "application/vnd.ogc.se_xml", xml)
    assert err.reason == "layer_not_found" and "tpgis:TPA-SGA" in err.message
    assert fu.classify(500, "text/plain", b"x").reason == "upstream_error"


def test_capabilities_layer_dan_cakupan():
    xml = ('<Layer><Name>tpgis:tpgis_fu</Name><Title>t</Title><SRS>EPSG:4326</SRS>'
           '<LatLonBoundingBox minx="116.38" miny="-2.35" maxx="118.57" maxy="1.66"/></Layer>')
    out = fu.parse_capabilities(xml, ["tpgis:tpgis_fu", "tpgis:TPA-SGA"])
    assert out["layers"] == {"tpgis:tpgis_fu": {"bbox": [116.38, -2.35, 118.57, 1.66]}}


def test_tile_cache_redis(monkeypatch):
    asyncio.run(_tile_cache_redis(monkeypatch))


async def _tile_cache_redis(monkeypatch):
    calls = []

    class FakeRedis:
        store = {}
        async def get(self, k): return self.store.get(k)
        async def set(self, k, v, ex=None): self.store[k] = v

    redis = FakeRedis()

    async def client():
        return redis

    monkeypatch.setattr(fu, "get_client", client)
    monkeypatch.setattr(fu, "_http_get", lambda url: calls.append(url) or (200, "image/png", b"\x89PNGdata"))
    p = {"bbox": "1,2,3,4", "width": "256", "height": "256"}
    body, ctype, hit = await fu.get_tile(p)
    assert (body, ctype, hit) == (b"\x89PNGdata", "image/png", False)
    body, ctype, hit = await fu.get_tile(p)
    assert hit is True and len(calls) == 1


def test_belum_dikonfigurasi(monkeypatch):
    asyncio.run(_belum_dikonfigurasi(monkeypatch))


async def _belum_dikonfigurasi(monkeypatch):
    monkeypatch.setattr(settings, "FOTO_UDARA_WMS_TOKEN", "")
    with pytest.raises(fu.FotoUdaraError) as exc:
        await fu.get_tile({"bbox": "1,2,3,4"})
    assert exc.value.reason == "not_configured"
    assert (await fu.status())["reason"] == "not_configured"
