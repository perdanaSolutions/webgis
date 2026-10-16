"""
Grup estate (TPA/SGA): daftar & filter peta, upload GeoJSON blok (sumber resmi grup + penggabungan
blok terpecah), dan peringatan Group di import areal statement.
"""
import io
import json

import openpyxl
import pytest
from sqlalchemy import text

from app.db.session import engine

BULAN, TAHUN = 1, 2031  # periode khusus test (sama dengan test_uploads)
PERIOD = "2031-01-01"


@pytest.fixture(scope="module")
def grouped_block(sample_block) -> dict:
    """sample_block + grup estatenya dan grup lain sebagai pembanding."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT es.id AS estate_id, es.group_id, gr.code AS grup,
                   (SELECT code FROM master.groups WHERE id IS DISTINCT FROM es.group_id ORDER BY code LIMIT 1) AS other
            FROM master.estates es LEFT JOIN master.groups gr ON gr.id = es.group_id
            WHERE es.code = :e
        """), {"e": sample_block["estate"]}).mappings().one()
        polygon = json.loads(conn.execute(text(
            "SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b ORDER BY period DESC LIMIT 1"),
            {"b": sample_block["id"]}).scalar())
    if row["grup"] is None or row["other"] is None:
        pytest.skip("Database test belum menjalankan migrasi 008 (grup).")
    return {**sample_block, **row, "polygon": polygon}


def _get(client, auth, path, **params):
    response = client.get(f"/api/v1/spatial{path}", headers=auth, params={"limit": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_group_list_and_hierarchy_filters(client, auth, grouped_block):
    groups = {g["kode_grup"]: g for g in _get(client, auth, "/grup")}
    assert {"TPA", "SGA"} <= groups.keys() and groups[grouped_block["grup"]]["jumlah_estate"] >= 1

    grup, other = grouped_block["grup"], grouped_block["other"]
    estates = _get(client, auth, "/estate", kode_grup=grup)
    assert estates and all(e["kode_grup"] == grup for e in estates)
    assert grouped_block["estate"] in {e["kode_est"] for e in estates}
    assert grouped_block["estate"] not in {e["kode_est"] for e in _get(client, auth, "/estate", kode_grup=other)}

    assert grouped_block["company"] in {p["kode_pt"] for p in _get(client, auth, "/pt", kode_grup=grup)}
    assert grouped_block["division"] in {
        d["kode_afd"] for d in _get(client, auth, "/afdeling", kode_grup=grup, kode_est=grouped_block["estate"])}
    assert _get(client, auth, "/afdeling", kode_grup=other, kode_est=grouped_block["estate"]) == []

    blocks = _get(client, auth, "/blok", kode_grup=grup, kode_blok=grouped_block["id"])
    assert grouped_block["id"] in {b["id"] for b in blocks} and all(b["kode_grup"] == grup for b in blocks)


def test_geojson_filter_and_property(client, auth, grouped_block):
    params = {"kode_blok": grouped_block["id"]}
    fc = client.get("/api/v1/spatial/geojson", headers=auth, params={**params, "kode_grup": grouped_block["grup"]}).json()
    assert fc["features"][0]["properties"]["kode_grup"] == grouped_block["grup"]
    other = client.get("/api/v1/spatial/geojson", headers=auth,
                       params={**params, "kode_grup": grouped_block["other"]}).json()
    assert other["features"] == []


def _fc(*features) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def _feature(block: dict, polygon: dict, **props) -> dict:
    return {"type": "Feature", "geometry": polygon, "properties": {
        "PT": block["company_name"] or block["company"], "Est_ID": block["estate"],
        "Afdeling": block["division"], "Blok": block["code"], **props}}


def _shifted(polygon: dict, dx: float) -> dict:
    """Salinan poligon yang digeser (potongan kedua blok terpecah, tidak bersinggungan)."""
    def move(coords):
        return [move(c) for c in coords] if isinstance(coords[0], list) else [coords[0] + dx, coords[1]]
    return {"type": polygon["type"], "coordinates": move(polygon["coordinates"])}


def _upload(client, auth, path, content):
    return client.post(f"/api/v1/spatial/blok-geometry/{path}", headers=auth, params={"bulan": BULAN, "tahun": TAHUN},
                       files={"file": ("blok.geojson", content, "application/geo+json")})


def test_block_upload_merges_split_block_and_updates_group(client, auth, grouped_block):
    b, other = grouped_block, grouped_block["other"]
    content = _fc(_feature(b, b["polygon"], Group=other, Ownership="Inti"),
                  _feature(b, _shifted(b["polygon"], 0.5), Group=other))
    try:
        analyze = _upload(client, auth, "upload-analyze", content).json()
        assert analyze["blok_terpecah"] == 1 and analyze["jumlah_blok_akan_disimpan"] == 1
        codes = {w["kode"]: w for w in analyze["peringatan"]}
        assert codes["BLOK_TERPECAH"]["level"] == "INFO" and "GRUP_BERUBAH" in codes
        assert analyze["rincian"]["grup_estate"] == [{"estate": b["estate"], "grup_file": other,
                                                      "grup_master": b["grup"], "status": "BERUBAH"}]

        result = _upload(client, auth, "upload-execute", content).json()["data"]["detail_status"]
        assert result["sukses_geometri_polygon_blok"] == 2 and result["blok_unik_tersimpan"] == 1
        assert result["blok_terpecah_digabung"] == 1
        assert result["grup_estate_diganti"] == [f"{b['estate']}: {b['grup']} -> {other}"]
        with engine.connect() as conn:
            parts, area_ratio = conn.execute(text("""
                SELECT ST_NumGeometries(n.geom), ST_Area(n.geom) / ST_Area(o.geom)
                FROM spatial.block_boundaries n,
                     (SELECT geom FROM spatial.block_boundaries WHERE block_id = :b AND period <> :p
                      ORDER BY period DESC LIMIT 1) o
                WHERE n.block_id = :b AND n.period = :p
            """), {"b": b["id"], "p": PERIOD}).one()
            group = conn.execute(text("SELECT gr.code FROM master.estates es JOIN master.groups gr ON gr.id = es.group_id "
                                      "WHERE es.id = :e"), {"e": b["estate_id"]}).scalar()
        assert parts >= 2 and area_ratio == pytest.approx(2, rel=0.01)  # kedua potongan tersimpan
        assert group == other
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.estates SET group_id = :g WHERE id = :e"),
                         {"g": b["group_id"], "e": b["estate_id"]})
            conn.execute(text("DELETE FROM spatial.block_boundaries WHERE block_id = :b AND period = :p"),
                         {"b": b["id"], "p": PERIOD})


def test_block_upload_conflicting_groups_leave_estate_unchanged(client, auth, grouped_block):
    b = grouped_block
    content = _fc(_feature(b, b["polygon"], Group=b["grup"]), _feature(b, b["polygon"], Group=b["other"]))
    analyze = _upload(client, auth, "upload-analyze", content).json()
    assert analyze["rincian"]["grup_estate"][0]["status"] == "BERTENTANGAN_DI_FILE"
    assert any(w["kode"] == "GRUP_BERTENTANGAN" for w in analyze["peringatan"])


def _xlsx(header, rows) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    for row in [header, *rows]:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_area_statement_group_mismatch_is_only_a_warning(client, auth, grouped_block):
    b = grouped_block
    header = ["Year", "Month", "Group", "AreaCode", "UnitCode", "DivisionCode", "KodeBlok", "StatusTanam"]
    content = _xlsx(header, [[2099, 1, b["other"], "TES_AREA_GRUP", b["estate"], b["division"], b["code"], "TM"],
                             [2099, 2, b["grup"], "TES_AREA_GRUP", b["estate"], b["division"], b["code"], "TM"]])
    response = client.post("/api/v1/areal-statement/import-excel/analyze", headers=auth,
                           files={"file": ("tes.xlsx", content, "application/octet-stream")})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["baris_siap"] == 2  # baris tetap diimpor
    assert "Group" in report["rincian"]["kolom_dibaca"]
    assert report["rincian"]["peringatan_grup"]["jumlah"] == 1
    assert any(w["kode"] == "GRUP_BERBEDA" for w in report["peringatan"])
