"""Pre-seed cache ubin Foto Udara: kunci cache harus sama dengan permintaan Leaflet, dan seeder tidak boros."""
import asyncio

import pytest

from app.core import redis_client
from app.services import foto_udara_service as fu
from app.workers import seed_foto_udara as seeder

# Keluaran rumus Leaflet 1.9.4 di V8 (Node) untuk ubin yang sama. Uji 5 Nov 2026: 20.000 ubin acak z8..z20 di
# Kalimantan -> kunci cache identik 100% (string bbox kadang beda digit terakhir, dibulatkan 6 desimal oleh backend).
LEAFLET = {
    (13546, 8211, 14): "13095803.182042679,-48919.69810251226,13098249.166947804,-46473.713197386634",
    (216776, 131534, 18): "13101918.144305492,-70780.68819207241,13102071.018362064,-70627.81413550205",
}


def _key(params):
    return fu._cache_key(fu.build_getmap_query(params))


@pytest.mark.parametrize("xyz,js_bbox", LEAFLET.items())
def test_kunci_cache_sama_dengan_permintaan_browser(xyz, js_bbox):
    browser = {  # seperti yang dikirim L.TileLayer.WMS (uppercase: true) dari gis-dashboard
        "SERVICE": "WMS", "REQUEST": "GetMap", "LAYERS": "tpgis:tpgis_fu", "STYLES": "", "FORMAT": "image/jpeg",
        "TRANSPARENT": "false", "VERSION": "1.1.1", "WIDTH": "512", "HEIGHT": "512", "SRS": "EPSG:3857", "BBOX": js_bbox,
    }
    assert _key(seeder.tile_params(*xyz)) == _key(browser)


def test_ubin_yang_menyentuh_blok():
    # Satu blok kecil ~100 m di Berau: 1 ubin di z14, beberapa di z18; dua blok di ubin yang sama tidak dobel.
    blok = (117.6400, 2.0500, 117.6409, 2.0509)
    assert len(seeder.tiles_for_envelopes([blok], 14)) == 1
    assert len(seeder.tiles_for_envelopes([blok, blok], 14)) == 1
    assert 1 <= len(seeder.tiles_for_envelopes([blok], 18)) <= 4


class _FakeRedis:
    def __init__(self, cached=(), used=0, cap=0):
        self.keys = set(cached)
        self.used, self.cap = used, cap

    async def exists(self, key):
        return key in self.keys

    async def info(self, section):
        return {"used_memory": self.used, "maxmemory": self.cap}


@pytest.fixture()
def fake(monkeypatch):
    state = {"client": _FakeRedis(), "rendered": [], "fail": None}

    async def get_client():
        return state["client"]

    async def get_tile(params):
        if state["fail"]:
            raise fu.FotoUdaraError(state["fail"], "gagal")
        state["rendered"].append(params["bbox"])
        state["client"].keys.add(_key(params))
        state["client"].used += 50_000
        return b"\xff\xd8" + b"0" * 1000, "image/jpeg", False

    monkeypatch.setattr(redis_client, "get_client", get_client)
    monkeypatch.setattr(fu, "get_tile", get_tile)
    return state


TILES = [(x, 8211, 14) for x in range(13540, 13550)]


def test_ubin_yang_sudah_di_cache_dilewati(fake):
    fake["client"] = _FakeRedis(cached={_key(seeder.tile_params(*t)) for t in TILES[:4]})
    summary = asyncio.run(seeder.seed(TILES))
    assert summary["cached_before"] == 4
    assert summary["seeded"] == 6
    assert len(fake["rendered"]) == 6
    # Dijalankan ulang: semua sudah ada, GeoServer tidak dipanggil lagi.
    again = asyncio.run(seeder.seed(TILES))
    assert again["seeded"] == 0 and again["cached_before"] == 10
    assert len(fake["rendered"]) == 6


def test_dry_run_tidak_merender(fake):
    summary = asyncio.run(seeder.seed(TILES, dry_run=True))
    assert summary["seeded"] == 0 and fake["rendered"] == []
    assert summary["by_zoom"]["z14"]["tiles"] == 10


def test_berhenti_bila_memori_redis_hampir_penuh(fake):
    fake["client"] = _FakeRedis(used=80, cap=100)
    summary = asyncio.run(seeder.seed(TILES))
    assert summary["seeded"] == 0 and "memori Redis" in summary["stopped"]


def test_berhenti_setelah_kegagalan_berturut_turut(fake):
    fake["fail"] = "unreachable"
    summary = asyncio.run(seeder.seed(TILES, max_consecutive_failures=3, concurrency=1))
    assert summary["failed"] == 3
    assert "unreachable" in summary["stopped"]


def test_serentak_dibatasi(fake, monkeypatch):
    state = {"now": 0, "peak": 0}

    async def slow(params):
        state["now"] += 1
        state["peak"] = max(state["peak"], state["now"])
        await asyncio.sleep(0.02)
        state["now"] -= 1
        return b"x", "image/jpeg", False

    monkeypatch.setattr(fu, "get_tile", slow)
    asyncio.run(seeder.seed(TILES, concurrency=2))
    assert state["peak"] == 2


def test_tanpa_redis_ditolak(monkeypatch):
    async def none():
        return None

    monkeypatch.setattr(redis_client, "get_client", none)
    with pytest.raises(RuntimeError):
        asyncio.run(seeder.seed(TILES))
