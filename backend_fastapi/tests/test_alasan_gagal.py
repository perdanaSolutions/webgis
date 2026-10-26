"""Alasan gagal upload GeoJSON harus rinci & bisa ditindaklanjuti (tanpa database)."""
import pytest

from app.services.upload import part_response
from app.services.upload.report import duplicate_reason, geometry_problem, missing_block_attributes
from app.services.upload.resolvers import BlockIndex
from app.utils.geojson import prepare_geometry

BOWTIE = {"type": "Polygon", "coordinates": [[[110, 0], [111, 1], [111, 0], [110, 1], [110, 0]]]}
SQUARE = [[110, 0], [111, 0], [111, 1], [110, 1], [110, 0]]


@pytest.mark.parametrize("geometry, target, expected", [
    (None, "MULTIPOLYGON", ["Geometri kosong (null)", "poligon (Polygon/MultiPolygon)"]),
    ({"type": "Polygon", "coordinates": []}, "MULTIPOLYGON", ["tidak punya koordinat"]),
    ({"type": "Circle", "coordinates": [1, 2]}, "POINT", ["'Circle' tidak dikenal"]),
    ({"type": "Point", "coordinates": [110, 0]}, "MULTIPOLYGON", ["Tipe geometri Point tidak sesuai", "poligon"]),
    ({"type": "Polygon", "coordinates": [SQUARE]}, "POINT", ["Polygon tidak sesuai", "titik tunggal (Point)"]),
    ({"type": "MultiPoint", "coordinates": [[110, 0], [111, 0]]}, "POINT", ["berisi 2 bagian", "Multipart to Singleparts"]),
    ({"type": "Point", "coordinates": ["abc", 0]}, "POINT", ["bukan angka"]),
    ({"type": "Point", "coordinates": [110]}, "POINT", ["tidak lengkap"]),
    ({"type": "Point", "coordinates": [0.5, 110.2]}, "POINT", ["di luar rentang WGS84", "sumbu terbalik"]),
    ({"type": "Point", "coordinates": [500000.0, 9000000.0]}, "POINT", ["di luar rentang", "UTM"]),
    ({"type": "LineString", "coordinates": [[110, 0], [110, 0]]}, "MULTILINESTRING", ["1 titik unik", "minimal 2"]),
    ({"type": "Polygon", "coordinates": [[[110, 0], [111, 0], [111, 1], [110, 1]]]}, "MULTIPOLYGON",
     ["tidak tertutup", "(110.0000000, 0.0000000)", "(110.0000000, 1.0000000)"]),
    ({"type": "Polygon", "coordinates": [[[110, 0], [111, 0], [110, 0], [110, 0]]]}, "MULTIPOLYGON",
     ["2 titik unik", "Cincin luar"]),
    ({"type": "Polygon", "coordinates": [[[110, 0], [111, 0], [112, 0], [110, 0]]]}, "MULTIPOLYGON",
     ["Geometri tidak valid", "di sekitar koordinat", "hanya menghasilkan LineString"]),
    ({"type": "Polygon", "coordinates": [SQUARE, [[120, 5], [121, 5], [121, 6], [120, 5]]]}, "MULTIPOLYGON",
     ["lubang (hole/enclave) berada di luar", "(120.0000000, 5.0000000)", "Fix Geometries"]),
    ({"type": "GeometryCollection", "geometries": []}, "MULTIPOLYGON", ["GeometryCollection tidak didukung"]),
    ({"type": "_GAGAL_KONVERSI", "epsg": 32650}, "POINT", ["EPSG:32650"]),
    ({"type": "Polygon", "coordinates": [[1, 2]]}, "MULTIPOLYGON", ["tidak lengkap: 1"]),
    ({"type": "Polygon", "coordinates": [1]}, "MULTIPOLYGON", ["seharusnya berupa daftar"]),
])
def test_geometry_reason_is_specific(geometry, target, expected):
    reason = geometry_problem(geometry, target, "Blok Kebun")
    for part in expected:
        assert part in reason, reason


# Kasus yang memang DITOLAK prepare_geometry (kasus lain di atas diperbaiki otomatis, atau ditolak
# per file oleh parse_features, mis. koordinat di luar rentang lon/lat).
REJECTED = [
    None,
    {"type": "Polygon", "coordinates": []},
    {"type": "Point", "coordinates": [110, 0]},
    {"type": "Point", "coordinates": ["abc", 0]},
    {"type": "Polygon", "coordinates": [[[110, 0], [111, 0], [110, 0], [110, 0]]]},
    {"type": "Polygon", "coordinates": [[[110, 0], [111, 0], [112, 0], [110, 0]]]},
    {"type": "GeometryCollection", "geometries": []},
]


@pytest.mark.parametrize("geometry", REJECTED)
def test_rejected_geometry_never_gets_generic_reason(geometry):
    assert prepare_geometry(geometry, "MULTIPOLYGON") is None
    reason = geometry_problem(geometry, "MULTIPOLYGON", "Blok Kebun")
    assert "atau koordinatnya tidak valid" not in reason and len(reason) > 40


def test_self_intersection_is_repaired_not_rejected():
    # bowtie diperbaiki make_valid -> tetap diterima untuk layer poligon (perilaku lama dipertahankan)
    assert prepare_geometry(BOWTIE, "MULTIPOLYGON") is not None


def test_collapsed_invalid_polygon_reports_location():
    # poligon "jarum": runtuh jadi garis setelah make_valid -> ditolak, alasan menyebut lokasi & hasil make_valid
    spike = {"type": "Polygon", "coordinates": [[[110, 0], [111, 0], [110.5, 0], [110, 0]]]}
    assert prepare_geometry(spike, "MULTIPOLYGON") is None
    reason = geometry_problem(spike, "MULTIPOLYGON")
    assert "luasnya nol" in reason or "Geometri tidak valid" in reason


def test_missing_block_attributes_lists_values_and_misnamed_columns():
    reason = missing_block_attributes({"EstID": "KLE", "Afdeling": " ", "BLOK": "B12"})
    assert "Afdeling (Afdeling/Afdeling_2)" in reason and "Blok (Blok)" in reason
    assert "EstID='KLE'" in reason and "Afdeling=(kosong)" in reason
    assert "kolom 'BLOK' berisi 'B12'" in reason and "persis 'Blok'" in reason


def _index() -> BlockIndex:
    index = BlockIndex()
    index.estate_ids = {"KLE": 1}
    index.divisions = {(1, "A"), (1, "B"), (1, "C")}
    index.add(1, "A", "B12", 10)
    index.add(1, "B", "B13", 11)
    index.add(1, "C", "B13", 12)  # blok kembar
    return index


@pytest.mark.parametrize("keys, expected", [
    ((("XYZ", None, None), "A", "B12"), "estate 'XYZ' tidak dikenal"),
    ((("KLE", None, None), "Z", "B12"), "afdeling 'Z' tidak ada di estate KLE (afdeling yang terdaftar: A, B, C)"),
    ((("KLE", None, None), "A", "B99"), "blok 'B99' tidak ada di afdeling A estate KLE (contoh blok terdaftar di afdeling ini: B12)"),
    ((("KLE", None, None), "Z", "B13"), "tercatat di beberapa afdeling master (B, C)"),
])
def test_missing_block_reason_names_failing_level(keys, expected):
    reason = _index().missing_block_reason(keys)
    assert expected in reason, reason
    assert "posisi juga gagal" in reason


def test_duplicate_reason_number_shifted_to_global_preview_no():
    reason = duplicate_reason(7, 4)  # dipakai data #5 lokal
    rows = part_response.table_preview(5, [{"no_preview": 2, "kode": "OBJECTID_GANDA", "alasan": reason}], offset=1000)
    assert rows[1]["no_preview"] == 1002
    assert "data #1005" in rows[1]["alasan_gagal"] and "OBJECTID 7" in rows[1]["alasan_gagal"]
    group = part_response.group_failures([{"no_preview": 2, "kode": "OBJECTID_GANDA", "alasan": reason}], 1000)
    assert "data #1005" in group[0]["data"][0]["alasan"]
