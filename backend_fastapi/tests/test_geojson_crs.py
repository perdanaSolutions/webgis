import json

from app.services.upload.resolvers import geojson_block_keys
from app.utils.geojson import parse_features


def _collection(crs_name: str | None, coords: list) -> bytes:
    data = {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": coords}}]}
    if crs_name:
        data["crs"] = {"type": "name", "properties": {"name": crs_name}}
    return json.dumps(data).encode()


def test_parse_features_reprojects_utm_to_wgs84():
    # UTM 50N (Kaltim), 449717 mE / 9734650 mN -> sekitar 116.5E, 2.4S
    feature = parse_features(_collection("urn:ogc:def:crs:EPSG::32750", [449717.91, 9734650.92]))[0]
    lon, lat = feature["geometry"]["coordinates"]
    assert 116.4 < lon < 116.7 and -2.5 < lat < -2.3


def test_parse_features_without_crs_is_untouched():
    assert parse_features(_collection(None, [116.5, -2.4]))[0]["geometry"]["coordinates"] == [116.5, -2.4]


def test_block_keys_fall_back_to_joined_master_columns():
    props = {"Afdeling": None, "Blok": "R005", "Estate": "Tanjung Harapan 1 Estate", "Afdeling_2": "AFDI01"}
    estate_refs, division, block = geojson_block_keys(props)
    assert division == "AFDI01" and block == "R005" and "Tanjung Harapan 1 Estate" in estate_refs
    assert geojson_block_keys({"Blok": "R005"}) is None
