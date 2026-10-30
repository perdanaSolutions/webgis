"""Proxy WMS Foto Udara (GeoServer digilink): token disimpan di backend, browser tidak pernah melihatnya.

Alur: browser (Leaflet) -> GET /api/v1/basemap/foto-udara/wms?bbox=..&width=..  (JWT user)
      -> backend menambah token + layer yang diizinkan -> GeoServer -> gambar (cache Redis).
GeoServer menolak tanpa token (401) dan menjawab XML ServiceException (HTTP 200) untuk layer yang tidak ada,
jadi jawaban upstream diklasifikasikan supaya frontend bisa menampilkan penyebab yang benar.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings
from app.core.redis_client import get_client, mark_down

logger = logging.getLogger(__name__)

_FORMATS = {"image/png", "image/jpeg", "image/png8", "image/webp"}
_SRS = {"EPSG:3857", "EPSG:900913", "EPSG:4326"}
_TIMEOUT = 20
_MAX_CACHE_BYTES = 1_500_000
_caps_cache: dict = {"at": 0.0, "value": None}
_CAPS_TTL = 600


class FotoUdaraError(Exception):
    """reason: not_configured | unauthorized | layer_not_found | bad_request | upstream_error | unreachable"""

    def __init__(self, reason: str, message: str, status: int = 424):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.status = status


def allowed_layers() -> list[str]:
    return [x.strip() for x in (settings.FOTO_UDARA_WMS_LAYERS or "").split(",") if x.strip()]


def configured() -> bool:
    return bool((settings.FOTO_UDARA_WMS_URL or "").strip() and (settings.FOTO_UDARA_WMS_TOKEN or "").strip())


def _upstream_url(query: dict[str, str]) -> str:
    base = settings.FOTO_UDARA_WMS_URL.strip()
    parts = urllib.parse.urlsplit(base)
    q = dict(urllib.parse.parse_qsl(parts.query))
    q.update(query)
    q["token"] = settings.FOTO_UDARA_WMS_TOKEN.strip()
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(q)))


def build_getmap_query(params: dict[str, str]) -> dict[str, str]:
    """Hanya parameter GetMap yang aman diteruskan; layer harus termasuk daftar yang diizinkan."""
    p = {k.lower(): v for k, v in params.items()}
    layers = p.get("layers") or (allowed_layers()[:1] or [""])[0]
    allowed = allowed_layers()
    if not layers or any(layer not in allowed for layer in layers.split(",")):
        raise FotoUdaraError("layer_not_found", f"Layer '{layers}' tidak diizinkan. Layer tersedia: {', '.join(allowed) or '-'}", 404)
    version = p.get("version") or "1.1.1"
    if version not in ("1.1.1", "1.1.0", "1.3.0"):
        raise FotoUdaraError("bad_request", "Versi WMS tidak didukung.", 400)
    srs = (p.get("crs") if version == "1.3.0" else p.get("srs")) or p.get("srs") or p.get("crs") or "EPSG:3857"
    if srs.upper() not in _SRS:
        raise FotoUdaraError("bad_request", f"SRS {srs} tidak didukung.", 400)
    fmt = (p.get("format") or "image/png").lower()
    if fmt not in _FORMATS:
        raise FotoUdaraError("bad_request", f"Format {fmt} tidak didukung.", 400)
    try:
        bbox = [float(x) for x in (p.get("bbox") or "").split(",")]
        width, height = int(p.get("width", "256")), int(p.get("height", "256"))
    except ValueError as exc:
        raise FotoUdaraError("bad_request", "bbox/width/height tidak valid.", 400) from exc
    if len(bbox) != 4 or not (1 <= width <= 1024 and 1 <= height <= 1024):
        raise FotoUdaraError("bad_request", "bbox harus 4 angka, ukuran 1–1024 px.", 400)
    query = {
        "service": "WMS", "request": "GetMap", "version": version, "layers": layers, "styles": p.get("styles", ""),
        "format": fmt, "transparent": "true" if str(p.get("transparent", "false")).lower() == "true" else "false",
        "width": str(width), "height": str(height), "bbox": ",".join(repr(round(v, 6)) for v in bbox),
        ("crs" if version == "1.3.0" else "srs"): srs.upper(),
    }
    return query


def classify(status: int, content_type: str, body: bytes) -> FotoUdaraError | None:
    """None = gambar sah. Selain itu alasan kegagalan yang bisa dibaca pengguna."""
    ctype = (content_type or "").lower()
    if status == 401 or status == 403:
        return FotoUdaraError("unauthorized", "Server foto udara menolak token (401). Token salah, kedaluwarsa, atau belum diisi.")
    if status >= 400:
        return FotoUdaraError("upstream_error", f"Server foto udara menjawab HTTP {status}.")
    if ctype.startswith("image/"):
        return None
    text = body[:4000].decode("utf-8", "replace")
    if "LayerNotDefined" in text or "Could not find layer" in text:
        found = re.search(r"Could not find layer ([^\s<]+)", text)
        return FotoUdaraError("layer_not_found", f"Layer {found.group(1) if found else ''} tidak ada di GeoServer.".replace("  ", " "), 404)
    snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()[:200]
    return FotoUdaraError("upstream_error", f"Server foto udara tidak mengirim gambar: {snippet}")


def _http_get(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "webgis-foto-udara-proxy"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", "") if exc.headers else "", exc.read() if exc.fp else b""
    except Exception as exc:  # DNS, timeout, koneksi ditolak
        raise FotoUdaraError("unreachable", "Server foto udara tidak terjangkau dari backend.") from exc


def _cache_key(query: dict[str, str]) -> str:
    raw = "&".join(f"{k}={query[k]}" for k in sorted(query))
    return "fu:tile:" + hashlib.sha1(raw.encode()).hexdigest()


async def get_tile(params: dict[str, str]) -> tuple[bytes, str, bool]:
    """(gambar, content-type, dari_cache)."""
    if not configured():
        raise FotoUdaraError("not_configured", "FOTO_UDARA_WMS_URL / FOTO_UDARA_WMS_TOKEN belum diisi di backend.", 424)
    query = build_getmap_query(params)
    key = _cache_key(query)
    client = await get_client()
    if client is not None:
        try:
            hit = await client.get(key)
            if hit:
                return hit, query["format"], True
        except Exception:
            await mark_down(client)
            client = None
    status, ctype, body = await asyncio.to_thread(_http_get, _upstream_url(query))
    problem = classify(status, ctype, body)
    if problem:
        raise problem
    if client is not None and len(body) <= _MAX_CACHE_BYTES:
        try:
            await client.set(key, body, ex=settings.FOTO_UDARA_CACHE_SECONDS)
        except Exception:
            await mark_down(client)
    return body, ctype.split(";")[0] or query["format"], False


def parse_capabilities(xml: str, wanted: list[str]) -> dict:
    """Cek layer yang diminta ada + ambil cakupan (LatLonBoundingBox / EX_GeographicBoundingBox)."""
    out: dict = {"layers": {}}
    for name in wanted:
        i = xml.find(f"<Name>{name}</Name>")
        if i < 0:
            continue
        chunk = xml[i:i + 4000]
        m = re.search(r'<LatLonBoundingBox minx="([-\d.eE]+)" miny="([-\d.eE]+)" maxx="([-\d.eE]+)" maxy="([-\d.eE]+)"', chunk)
        if not m:
            m2 = re.search(r"<westBoundLongitude>([-\d.eE]+)</westBoundLongitude>\s*<eastBoundLongitude>([-\d.eE]+)</eastBoundLongitude>\s*"
                           r"<southBoundLatitude>([-\d.eE]+)</southBoundLatitude>\s*<northBoundLatitude>([-\d.eE]+)</northBoundLatitude>", chunk)
            bbox = [float(m2.group(1)), float(m2.group(3)), float(m2.group(2)), float(m2.group(4))] if m2 else None
        else:
            bbox = [float(v) for v in m.groups()]
        out["layers"][name] = {"bbox": bbox}
    return out


async def status() -> dict:
    """Ringkasan untuk dialog frontend: terkonfigurasi? token diterima? layer ada? cakupan?"""
    layers = allowed_layers()
    base = {"configured": configured(), "layers": layers, "ok": False, "reason": None, "message": None, "bbox": None}
    if not configured():
        return {**base, "reason": "not_configured", "message": "FOTO_UDARA_WMS_URL / FOTO_UDARA_WMS_TOKEN belum diisi di backend."}
    now = time.monotonic()
    cached = _caps_cache["value"]
    if cached is None or now - _caps_cache["at"] > _CAPS_TTL:
        try:
            st, ctype, body = await asyncio.to_thread(_http_get, _upstream_url({"service": "WMS", "version": "1.1.1", "request": "GetCapabilities"}))
        except FotoUdaraError as exc:
            return {**base, "reason": exc.reason, "message": exc.message}
        if st in (401, 403):
            return {**base, "reason": "unauthorized", "message": "Server foto udara menolak token (401). Token salah, kedaluwarsa, atau belum diisi."}
        if st >= 400:
            return {**base, "reason": "upstream_error", "message": f"GetCapabilities gagal (HTTP {st})."}
        cached = parse_capabilities(body.decode("utf-8", "replace"), layers)
        _caps_cache.update(at=now, value=cached)
    missing = [name for name in layers if name not in cached["layers"]]
    if missing:
        return {**base, "reason": "layer_not_found", "message": f"Layer {', '.join(missing)} tidak ada di GeoServer."}
    boxes = [v["bbox"] for v in cached["layers"].values() if v["bbox"]]
    bbox = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None
    return {**base, "ok": True, "bbox": bbox}
