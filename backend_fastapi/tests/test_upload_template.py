"""Template standar format GeoJSON harus lolos validasi analisis (tanpa database)."""
import json

import pytest

from app.services.block_upload_service import _read_feature
from app.services.layers.catalog_service import INVALID, _cast
from app.services.layers.specs import LAYER_SPECS
from app.services.upload import template as upload_template
from app.services.upload.resolvers import geojson_block_keys
from app.utils.geojson import parse_features, prepare_geometry
from app.utils.parsing import to_float, to_int

CODES = ["blok", "sawit", *LAYER_SPECS]


def _features(tpl):
    return parse_features(tpl.geojson_bytes())


@pytest.mark.parametrize("code", CODES)
def test_template_passes_validation(code):
    tpl = upload_template.builtin_template(code)
    features = _features(tpl)
    assert len(features) == 2
    for f in features:
        props, geom = f["properties"], f["geometry"]
        assert prepare_geometry(geom, tpl.geometry_type) is not None
        if code == "blok":
            item = _read_feature(props, geom)
            assert item is not None and item.geom is not None
            continue
        assert geojson_block_keys(props) is not None
        if code == "sawit":
            assert to_int(props.get("OBJECTID")) is not None and props.get("Kategori")
            assert (to_float(props.get("Diameter")) or 0) >= 0 and (to_float(props.get("Jarak")) or 0) >= 0
        else:
            for col in LAYER_SPECS[code].columns:
                assert col.props[0] in props, f"{code}: kolom {col.props[0]} tidak ada di template"
                if col.non_negative:
                    assert to_float(props[col.props[0]]) >= 0
                if col.kind == "int":
                    assert to_int(props[col.props[0]]) is not None


def test_objectid_unique_where_required():
    for code in ("sawit", *[c for c, s in LAYER_SPECS.items() if s.unique_objectid]):
        ids = [f["properties"].get("OBJECTID") for f in _features(upload_template.builtin_template(code))]
        assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("code", CODES)
def test_guide_lists_every_field(code):
    tpl = upload_template.builtin_template(code)
    guide = tpl.guide()
    assert "EPSG:4326" in guide
    for f in tpl.fields:
        assert f"| {f.name} | {'Wajib' if f.required else 'Opsional'} |" in guide


def test_generic_template_values_match_column_types():
    layer = {"kode": "drainase", "nama": "Drainase", "geometry_type": "POINT", "relasi_blok": True}
    columns = [{"property": p, "column": p.lower(), "data_type": t} for p, t in (
        ("OBJECTID", "integer"), ("Kedalaman", "double precision"), ("Aktif", "boolean"),
        ("Tanggal", "date"), ("Keterangan", "text"))]
    tpl = upload_template.generic_template(layer, columns)
    for f in _features(tpl):
        assert geojson_block_keys(f["properties"]) is not None
        assert prepare_geometry(f["geometry"], "POINT") is not None
        for col in columns:
            assert _cast(f["properties"][col["property"]], col["data_type"]) not in (None, INVALID)
    assert json.loads(tpl.geojson_bytes())["crs"]["properties"]["name"].endswith("CRS84")


def test_unknown_code_is_not_builtin():
    assert upload_template.builtin_template("tidak-ada") is None
