import json
import logging
import re
from typing import Any

import numpy as np
import orjson
import shapely
from fastapi import Response
from shapely import wkb
from shapely.errors import ShapelyError
from pyproj import Transformer
from shapely.geometry import MultiLineString, MultiPoint, MultiPolygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from app.core.exceptions import bad_request
from app.utils.parsing import json_safe

logger = logging.getLogger(__name__)

SRID = 4326

_MULTI = {"Point": MultiPoint, "LineString": MultiLineString, "Polygon": MultiPolygon}


def _loads(content: bytes) -> Any:
    """orjson (±3x lebih cepat); file dengan NaN/Infinity ditolak orjson, jadi jatuh ke json standar."""
    try:
        return orjson.loads(content)
    except orjson.JSONDecodeError:
        return json.loads(content)


def parse_features(content: bytes) -> list[dict]:
    """Isi file GeoJSON -> list feature. FeatureCollection atau satu Feature."""
    try:
        data = _loads(content)
    except (ValueError, UnicodeDecodeError) as exc:
        raise bad_request("Format file tidak valid atau bukan JSON.", field="file") from exc
    if not isinstance(data, dict):
        raise bad_request("Isi file bukan objek GeoJSON.", field="file")
    features = ([f for f in data.get("features") or [] if isinstance(f, dict)]
                if data.get("type") == "FeatureCollection" else [data])
    epsg = _source_epsg(data)
    if epsg is None:
        if _looks_projected(features):
            raise bad_request(
                "Koordinat file bukan derajat lon/lat (kemungkinan UTM/meter) dan file tidak menyertakan "
                "member `crs`. Export ulang GeoJSON dalam EPSG:4326 (WGS84) atau sertakan `crs` "
                "(mis. urn:ogc:def:crs:EPSG::32650).", field="file")
        epsg = SRID
    features = _to_wgs84(features, epsg)
    _ensure_lonlat(features)
    return features


def _iter_xy(features: list[dict]):
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        try:
            coords = shapely.get_coordinates(shape(geometry))
        except (ShapelyError, ValueError, TypeError, KeyError, AttributeError):
            continue
        if len(coords):
            yield coords


def _out_of_lonlat(coords) -> bool:
    return bool((np.abs(coords[:, 0]) > 180).any() or (np.abs(coords[:, 1]) > 90).any()
                or not np.isfinite(coords).all())


def _looks_projected(features: list[dict]) -> bool:
    return any(_out_of_lonlat(c) for c in _iter_xy(features))


def _ensure_lonlat(features: list[dict]) -> None:
    """Guard akhir: setelah reproject semua koordinat wajib di rentang lon [-180,180] / lat [-90,90]."""
    bad = sum(1 for c in _iter_xy(features) if _out_of_lonlat(c))
    if bad:
        raise bad_request(
            f"{bad} feature memiliki koordinat di luar rentang lon/lat WGS84 setelah konversi. "
            "Periksa sistem koordinat (crs) file.", field="file")


def _source_epsg(data: dict) -> int | None:
    """EPSG dari member `crs` (mis. `urn:ogc:def:crs:EPSG::32650`, `EPSG:32650`, `urn:ogc:def:crs:OGC:1.3:CRS84`).
    None bila tidak ada `crs` (pemanggil lalu mengecek rentang koordinat)."""
    crs = data.get("crs") or {}
    name = str((crs.get("properties") or {}).get("name") or "")
    if not name:
        return None
    if re.search(r"CRS84$", name, re.I):
        return SRID
    match = re.search(r"EPSG:+(?:[\d.]*:)?(\d+)$", name) or re.search(r"EPSG:+(\d+)", name)
    if not match:
        raise bad_request(f"Sistem koordinat '{name}' tidak dikenali; gunakan kode EPSG.", field="file")
    return int(match.group(1))


def _to_wgs84(features: list[dict], epsg: int) -> list[dict]:
    if epsg == SRID:
        return features
    try:
        transformer = Transformer.from_crs(epsg, SRID, always_xy=True)
    except Exception as exc:  # CRSError
        raise bad_request(f"Sistem koordinat EPSG:{epsg} tidak dikenali.", field="file") from exc

    def project(coords):
        x, y = transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([x, y])

    for feature in features:
        try:
            geom = shape(feature["geometry"]) if feature.get("geometry") else None
            if geom is not None:
                feature["geometry"] = mapping(shapely.transform(geom, project))
        except (ShapelyError, ValueError, TypeError, KeyError):
            feature["geometry"] = None  # ditolak sebagai GEOMETRI_TIDAK_VALID oleh pemanggil
    return features


def prepare_geometry(geometry: dict | None, target_type: str):
    """
    GeoJSON geometry -> objek shapely yang cocok dengan tipe kolom tujuan, atau None kalau tidak bisa dipakai.

    `target_type` memakai nama PostGIS (POINT, MULTIPOLYGON, ...). Tipe tunggal
    otomatis dibungkus jadi Multi* bila kolom tujuan Multi*, dan geometry yang
    tidak valid diperbaiki dengan make_valid (kolom seperti block_boundaries
    punya CHECK ST_IsValid). Dipakai langsung saat analisis (tanpa serialisasi WKB).
    """
    if not geometry:
        return None
    try:
        geom = shape(geometry)
        if geom.is_empty:
            return None
        if not geom.is_valid:
            geom = make_valid(geom)
            if geom.geom_type == "GeometryCollection":
                family = target_type.upper().removeprefix("MULTI")
                parts = []
                for part in geom.geoms:
                    if part.geom_type.upper() == family:
                        parts.append(part)
                    elif part.geom_type.upper() == f"MULTI{family}":
                        parts.extend(part.geoms)
                if not parts:
                    return None
                geom = parts[0] if len(parts) == 1 else _MULTI[parts[0].geom_type](parts)
        target = target_type.upper()
        if target.startswith("MULTI") and geom.geom_type in _MULTI:
            geom = _MULTI[geom.geom_type]([geom])
        if geom.geom_type.upper() != target:
            return None
        return geom
    except (ShapelyError, ValueError, TypeError, AttributeError, KeyError) as exc:
        logger.debug("Geometry tidak valid, dilewati: %s", exc)
        return None


def merge_polygons(geoms: list) -> MultiPolygon:
    """Satukan beberapa (Multi)Polygon jadi satu MultiPolygon; bagian yang tumpang tindih dilebur."""
    merged = geoms[0] if len(geoms) == 1 else unary_union(geoms)
    if merged.geom_type == "Polygon":
        return MultiPolygon([merged])
    if merged.geom_type == "GeometryCollection":  # sisa garis/titik dari peleburan dibuang
        return MultiPolygon([p for g in merged.geoms for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon"])
    return merged


def to_ewkb(geom) -> str:
    """Objek shapely -> hex EWKB (SRID 4326)."""
    return wkb.dumps(geom, hex=True, srid=SRID)


def geometry_to_ewkb(geometry: dict | None, target_type: str) -> str | None:
    """GeoJSON geometry -> hex EWKB (SRID 4326), atau None kalau tidak bisa dipakai (lihat prepare_geometry)."""
    geom = prepare_geometry(geometry, target_type)
    return None if geom is None else to_ewkb(geom)


class RawGeometry(str):
    """Geometri GeoJSON yang sudah berupa string JSON (hasil ST_AsGeoJSON); disisipkan apa adanya."""


def _dump(value: Any) -> str:
    return json.dumps(value, default=json_safe, separators=(",", ":"))


def feature_collection(features: list[dict]) -> Response:
    """Serialisasi FeatureCollection langsung (lebih cepat daripada lewat validasi response_model)."""
    parts = []
    for feature in features:
        geometry = feature.get("geometry")
        if isinstance(geometry, RawGeometry):
            parts.append(f'{{"type":"Feature","properties":{_dump(feature["properties"])},"geometry":{geometry}}}')
        else:
            parts.append(_dump(feature))
    body = f'{{"type":"FeatureCollection","features":[{",".join(parts)}]}}'
    return Response(content=body, media_type="application/json")


def make_feature(properties: dict[str, Any], geometry_json: str | None) -> dict | None:
    if not geometry_json:
        return None
    # Geometri tidak di-parse lalu di-serialisasi ulang; string dari PostGIS dipakai langsung.
    return {"type": "Feature", "properties": properties, "geometry": RawGeometry(geometry_json)}
