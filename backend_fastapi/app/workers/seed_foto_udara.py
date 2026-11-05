"""
Isi cache Redis ubin Foto Udara lebih awal (pre-seed) untuk area kebun, agar pengguna tidak menunggu GeoServer
merender ubin baru (uji 5 Nov 2026: 2–6 dtk per ubin baru, ~0,5 dtk bila sudah di cache).

    python -m app.workers.seed_foto_udara --dry-run            # hitung ubin & yang sudah di cache
    python -m app.workers.seed_foto_udara                      # z8..z15, 2 permintaan serentak
    python -m app.workers.seed_foto_udara --max-zoom 14 --estate E005,E023

Ubin dipilih dari batas blok (spatial.block_boundaries): ubin XYZ yang menyentuh bbox blok. Perkiraan 5 Nov 2026
(3.759 blok, 33 estate): z8..z14 = 666 ubin, z15 = 1.250, z16 = 4.085 (~290 MB), z17..z18 = 67 rb (terlalu besar
untuk redis-cache 384 MB), jadi default berhenti di z15 (~110 MB).

Cache key harus sama persis dengan permintaan browser: bbox dihitung dengan rumus Leaflet 1.9.4 (WMS EPSG:3857,
ubin 256 px CSS) dan parameter lain mengikuti gis-dashboard/utils/mapLayers.ts (BASEMAPS "tpa-sga") dan
WMS_HIDPI_TILE_PX di gis-dashboard/utils/mapBasemap.ts. Bila salah satunya berubah, ubah konstanta di sini.

redis-cache prod tanpa persistensi (restart = cache kosong) dan LRU: seeder melewati ubin yang sudah ada, jadi aman
dijalankan ulang (mis. cron malam), dan berhenti bila memori Redis melewati --max-memory-ratio agar tidak
menggusur cache lain.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import signal
import time

from sqlalchemy import text

from app.core import redis_client
from app.core.database import engine
from app.services import foto_udara_service as fu

logger = logging.getLogger("app.workers.seed_foto_udara")

# Sama dengan frontend (lihat docstring).
TILE_PARAMS = {
    "service": "WMS", "request": "GetMap", "layers": "tpgis:tpgis_fu", "styles": "", "format": "image/jpeg",
    "transparent": "false", "version": "1.1.1", "srs": "EPSG:3857",
}
TILE_PX = 512

# --- Rumus Leaflet 1.9.4 (SphericalMercator + CRS.EPSG3857 + GridLayer._tileCoordsToNwSe + TileLayer.WMS) ---
_R = 6378137
_MAX_LAT = 85.0511287798
_T = 0.5 / (math.pi * _R)  # transformation(a=_T, b=0.5, c=-_T, d=0.5)


def _unproject_point(px: float, py: float, z: int) -> tuple[float, float]:
    """map.unproject(point, z) -> (lat, lng)."""
    scale = 256 * math.pow(2, z)
    x = (px / scale - 0.5) / _T
    y = (py / scale - 0.5) / -_T
    d = 180 / math.pi
    return (2 * math.atan(math.exp(y / _R)) - (math.pi / 2)) * d, x * d / _R


def _project(lat: float, lng: float) -> tuple[float, float]:
    d = math.pi / 180
    lat = max(min(_MAX_LAT, lat), -_MAX_LAT)
    s = math.sin(lat * d)
    return _R * lng * d, _R * math.log((1 + s) / (1 - s)) / 2


def leaflet_bbox(x: int, y: int, z: int) -> list[float]:
    """BBOX yang dikirim L.TileLayer.WMS (EPSG:3857, WMS 1.1.1) untuk ubin XYZ (x, y, z), urutan min x/y, max x/y."""
    nw = _project(*_unproject_point(x * 256, y * 256, z))
    se = _project(*_unproject_point(x * 256 + 256, y * 256 + 256, z))
    return [min(nw[0], se[0]), min(nw[1], se[1]), max(nw[0], se[0]), max(nw[1], se[1])]


def _js_number(v: float) -> str:
    """Number.prototype.toString untuk nilai biasa (repr Python sama-sama representasi terpendek)."""
    s = repr(v)
    return s[:-2] if s.endswith(".0") else s


def tile_params(x: int, y: int, z: int, px: int = TILE_PX) -> dict[str, str]:
    return {**TILE_PARAMS, "width": str(px), "height": str(px),
            "bbox": ",".join(_js_number(v) for v in leaflet_bbox(x, y, z))}


# --- Ubin yang menyentuh blok ---
def _tile_x(lon: float, n: int) -> int:
    return int((lon + 180) / 360 * n)


def _tile_y(lat: float, n: int) -> int:
    r = math.radians(max(min(lat, _MAX_LAT), -_MAX_LAT))
    return int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)


def tiles_for_envelopes(envelopes: list[tuple[float, float, float, float]], z: int) -> list[tuple[int, int]]:
    """Ubin zoom z yang menyentuh salah satu bbox (lon0, lat0, lon1, lat1), urut agar ubin bertetangga berdekatan."""
    n = 2 ** z
    tiles: set[tuple[int, int]] = set()
    for lon0, lat0, lon1, lat1 in envelopes:
        for tx in range(_tile_x(lon0, n), _tile_x(lon1, n) + 1):
            for ty in range(_tile_y(lat1, n), _tile_y(lat0, n) + 1):
                tiles.add((tx, ty))
    return sorted(tiles, key=lambda t: (t[1], t[0]))


def load_block_envelopes(estates: list[str] | None = None) -> list[tuple[float, float, float, float]]:
    sql = """
        SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e) FROM (
          SELECT ST_Envelope(ST_Transform(b.geom, 4326)) AS e
          FROM spatial.block_boundaries b
          JOIN master.blocks bl ON bl.id = b.block_id
          JOIN master.divisions dv ON dv.id = bl.division_id
          JOIN master.estates es ON es.id = dv.estate_id
          WHERE b.geom IS NOT NULL {estate_filter}
        ) t
    """
    params = {}
    estate_filter = ""
    if estates:
        estate_filter = "AND es.code = ANY(:estates)"
        params["estates"] = estates
    with engine.connect() as conn:
        rows = conn.execute(text(sql.format(estate_filter=estate_filter)), params).fetchall()
    return [tuple(float(v) for v in row) for row in rows if None not in row]


# --- Seeder ---
class _Stop(Exception):
    pass


async def _memory_ratio(client) -> float | None:
    info = await client.info("memory")
    used, cap = int(info.get("used_memory", 0)), int(info.get("maxmemory", 0))
    return used / cap if cap else None


async def seed(
    tiles: list[tuple[int, int, int]],
    *,
    concurrency: int = 2,
    dry_run: bool = False,
    max_memory_ratio: float = 0.7,
    max_consecutive_failures: int = 20,
    stopping=lambda: False,
) -> dict:
    """Render ubin yang belum ada di cache. Kembalikan ringkasan (dict)."""
    client = await redis_client.get_client()
    if client is None:
        raise RuntimeError("Redis cache tidak tersedia (REDIS_MAP_ENABLED / REDIS_CACHE_URL); tidak ada yang bisa diisi.")
    summary = {"tiles": len(tiles), "cached_before": 0, "seeded": 0, "failed": 0, "bytes": 0,
               "stopped": None, "by_zoom": {}}
    sem = asyncio.Semaphore(max(1, concurrency))
    state = {"consecutive_failures": 0, "done": 0}
    started = time.monotonic()

    async def one(x: int, y: int, z: int) -> None:
        if summary["stopped"] or stopping():
            summary["stopped"] = summary["stopped"] or "dihentikan"
            return
        params = tile_params(x, y, z)
        key = fu._cache_key(fu.build_getmap_query(params))
        zs = summary["by_zoom"].setdefault(f"z{z}", {"tiles": 0, "cached_before": 0, "seeded": 0, "failed": 0})
        zs["tiles"] += 1
        if await client.exists(key):
            summary["cached_before"] += 1
            zs["cached_before"] += 1
            return
        if dry_run:
            return
        async with sem:
            if summary["stopped"]:
                return
            try:
                body, _ctype, _hit = await fu.get_tile(params)
            except fu.FotoUdaraError as exc:
                summary["failed"] += 1
                zs["failed"] += 1
                state["consecutive_failures"] += 1
                logger.warning("Ubin z%s/%s/%s gagal: %s", z, x, y, exc.reason)
                if state["consecutive_failures"] >= max_consecutive_failures:
                    summary["stopped"] = f"{max_consecutive_failures} kegagalan berturut-turut ({exc.reason})"
                return
            state["consecutive_failures"] = 0
            summary["seeded"] += 1
            zs["seeded"] += 1
            summary["bytes"] += len(body)
            state["done"] += 1
            if state["done"] % 50 == 0:
                ratio = await _memory_ratio(client)
                logger.info("%s ubin dirender (%.1f MB), memori Redis %s", state["done"], summary["bytes"] / 1e6,
                            f"{ratio:.0%}" if ratio is not None else "tanpa batas")
                if ratio is not None and ratio >= max_memory_ratio:
                    summary["stopped"] = f"memori Redis {ratio:.0%} >= {max_memory_ratio:.0%}"

    ratio = await _memory_ratio(client)
    if not dry_run and ratio is not None and ratio >= max_memory_ratio:
        summary["stopped"] = f"memori Redis {ratio:.0%} >= {max_memory_ratio:.0%} sebelum mulai"
        return summary
    # Per zoom berurutan (zoom rendah dulu); di dalam satu zoom serentak sebatas `concurrency`.
    for z in sorted({t[2] for t in tiles}):
        await asyncio.gather(*(one(x, y, zz) for x, y, zz in tiles if zz == z))
        if summary["stopped"]:
            break
    summary["seconds"] = round(time.monotonic() - started, 1)
    summary["memory_ratio_after"] = await _memory_ratio(client)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isi cache Redis ubin Foto Udara untuk area kebun.")
    parser.add_argument("--min-zoom", type=int, default=8)
    parser.add_argument("--max-zoom", type=int, default=15)
    parser.add_argument("--estate", default="", help="Kode estate dipisah koma (default: semua).")
    parser.add_argument("--concurrency", type=int, default=2, help="Permintaan serentak ke GeoServer (default 2).")
    parser.add_argument("--max-memory-ratio", type=float, default=0.7,
                        help="Berhenti bila used_memory/maxmemory Redis cache mencapai nilai ini (default 0,7).")
    parser.add_argument("--dry-run", action="store_true", help="Hanya hitung ubin dan yang sudah di cache.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not fu.configured():
        logger.error("FOTO_UDARA_WMS_URL / FOTO_UDARA_WMS_TOKEN belum diisi.")
        return 2
    estates = [e.strip() for e in args.estate.split(",") if e.strip()] or None
    envelopes = load_block_envelopes(estates)
    tiles = [(x, y, z) for z in range(args.min_zoom, args.max_zoom + 1) for x, y in tiles_for_envelopes(envelopes, z)]
    logger.info("%s blok, %s ubin (z%s..z%s)%s", len(envelopes), len(tiles), args.min_zoom, args.max_zoom,
                " [dry-run]" if args.dry_run else "")

    stop = {"flag": False}

    def request_stop(signum, _frame):
        stop["flag"] = True
        logger.info("Sinyal %s diterima, berhenti setelah ubin berjalan selesai", signum)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    async def run():
        try:
            return await seed(tiles, concurrency=args.concurrency, dry_run=args.dry_run,
                              max_memory_ratio=args.max_memory_ratio, stopping=lambda: stop["flag"])
        finally:
            await redis_client.shutdown()

    summary = asyncio.run(run())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failed"] and not summary["seeded"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
