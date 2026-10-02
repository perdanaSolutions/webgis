import json
import logging
from typing import Any

import orjson
from fastapi import Response
from shapely import wkb
from shapely.errors import ShapelyError
from shapely.geometry import MultiLineString, MultiPoint, MultiPolygon, shape
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
    if data.get("type") == "FeatureCollection":
        return [f for f in data.get("features") or [] if isinstance(f, dict)]
    return [data]


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
