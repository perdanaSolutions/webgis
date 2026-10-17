"""
Kunci blok resmi UnitCode + Blok: afdeling di file boleh berbeda dari master selama estate + kode blok
menunjuk tepat satu blok. Blok kembar (kode sama di beberapa afdeling) tidak pernah ditebak.
"""
import io
import json

import openpyxl
import pytest
from sqlalchemy import text

from app.db.session import engine

BULAN, TAHUN = 2, 2031
PERIOD = "2031-02-01"


def _xlsx(header, rows) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    for row in [header, *rows]:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _fc(*features) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def _upload(client, auth, path, content):
    return client.post(f"/api/v1/spatial/blok-geometry/{path}", headers=auth, params={"bulan": BULAN, "tahun": TAHUN},
                       files={"file": ("blok.geojson", content, "application/geo+json")})


@pytest.fixture(scope="module")
def block_with_polygon(sample_block) -> dict:
    with engine.connect() as conn:
        polygon = json.loads(conn.execute(text(
            "SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b ORDER BY period DESC LIMIT 1"),
            {"b": sample_block["id"]}).scalar())
        division_id = conn.execute(text("SELECT division_id FROM master.blocks WHERE id = :b"),
                                   {"b": sample_block["id"]}).scalar()
        unique = conn.execute(text("""
            SELECT count(*) FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
            JOIN master.estates es ON es.id = dv.estate_id WHERE es.code = :e AND upper(bl.code) = upper(:c)
        """), {"e": sample_block["estate"], "c": sample_block["code"]}).scalar()
    if unique != 1:
        pytest.skip("Blok sampel kembar di estatenya.")
    return {**sample_block, "polygon": polygon, "division_id": division_id}


def test_import_with_other_division_uses_estate_and_block(client, auth, block_with_polygon):
    b = block_with_polygon
    content = _xlsx(["Year", "Month", "UnitCode", "DivisionCode", "KodeBlok", "TbsAktual"],
                    [[2099, 1, b["estate"], "AFD-LAIN", b["code"], 10.0]])
    report = client.post("/api/v1/pokok-produksi/import-produksi-tbs/analyze", headers=auth,
                         files={"file": ("p.xlsx", content, "application/octet-stream")}).json()
    assert report["baris_siap"] == 1 and report["baris_ditolak"]["total"] == 0
    assert report["rincian"]["peringatan_afdeling"]["jumlah"] == 1
    assert any(w["kode"] == "AFDELING_BERBEDA" for w in report["peringatan"])


def test_ambiguous_duplicate_block_is_not_guessed(client, auth):
    with engine.connect() as conn:
        dup = conn.execute(text("""
            SELECT es.code AS estate, bl.code AS block FROM master.blocks bl
            JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
            GROUP BY es.code, bl.code HAVING count(*) > 1 LIMIT 1
        """)).mappings().first()
    if dup is None:
        pytest.skip("Database test tidak punya blok kembar.")
    content = _xlsx(["Year", "Month", "UnitCode", "DivisionCode", "KodeBlok", "TbsAktual"],
                    [[2099, 1, dup["estate"], "AFD-LAIN", dup["block"], 10.0]])
    report = client.post("/api/v1/pokok-produksi/import-produksi-tbs/analyze", headers=auth,
                         files={"file": ("p.xlsx", content, "application/octet-stream")}).json()
    assert report["baris_siap"] == 0 and report["baris_ditolak"]["blok_tidak_ditemukan"] == 1


def test_geojson_upload_moves_block_to_file_division(client, auth, block_with_polygon):
    b = block_with_polygon
    feature = {"type": "Feature", "geometry": b["polygon"], "properties": {
        "PT": b["company_name"] or b["company"], "Est_ID": b["estate"], "Afdeling": "AFD-UJI-PINDAH", "Blok": b["code"]}}
    try:
        analyze = _upload(client, auth, "upload-analyze", _fc(feature)).json()
        assert analyze["blok_baru_di_master"] == 0
        assert analyze["rincian"]["blok_pindah_afdeling"] == [
            {"blok": f"{b['estate']}/AFD-UJI-PINDAH/{b['code']}", "afdeling_master": b["division"]}]
        assert any(w["kode"] == "BLOK_PINDAH_AFDELING" for w in analyze["peringatan"])

        result = _upload(client, auth, "upload-execute", _fc(feature)).json()["data"]["detail_status"]
        assert result["blok_pindah_afdeling"] == 1 and result["sukses_master_blok_baru"] == 0
        with engine.connect() as conn:
            division = conn.execute(text("""
                SELECT dv.code FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id WHERE bl.id = :b
            """), {"b": b["id"]}).scalar()
        assert division == "AFD-UJI-PINDAH"
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.blocks SET division_id = :d WHERE id = :b"),
                         {"d": b["division_id"], "b": b["id"]})
            conn.execute(text("DELETE FROM spatial.block_boundaries WHERE block_id = :b AND period = :p"),
                         {"b": b["id"], "p": PERIOD})
            conn.execute(text("""
                DELETE FROM master.divisions dv WHERE dv.code = 'AFD-UJI-PINDAH'
                  AND NOT EXISTS (SELECT 1 FROM master.blocks bl WHERE bl.division_id = dv.id)
            """))


def test_geojson_upload_skips_block_that_is_duplicated_in_master(client, auth):
    with engine.connect() as conn:
        dup = conn.execute(text("""
            SELECT es.code AS estate, bl.code AS block, min(co.name) AS company FROM master.blocks bl
            JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
            JOIN master.companies co ON co.id = es.company_id
            GROUP BY es.code, bl.code HAVING count(*) > 1 LIMIT 1
        """)).mappings().first()
        before = conn.execute(text("SELECT count(*) FROM master.blocks")).scalar()
    if dup is None:
        pytest.skip("Database test tidak punya blok kembar.")
    square = {"type": "Polygon", "coordinates": [[[117.0, 1.0], [117.001, 1.0], [117.001, 1.001], [117.0, 1.0]]]}
    feature = {"type": "Feature", "geometry": square, "properties": {
        "PT": dup["company"], "Est_ID": dup["estate"], "Afdeling": "AFD-KETIGA", "Blok": dup["block"]}}
    analyze = _upload(client, auth, "upload-analyze", _fc(feature)).json()
    assert analyze["jumlah_blok_akan_disimpan"] == 0 and analyze["blok_baru_di_master"] == 0
    assert analyze["rincian"]["blok_kembar_di_master"][0]["blok"].endswith(f"/AFD-KETIGA/{dup['block']}")
    assert any(w["kode"] == "BLOK_KEMBAR_DI_MASTER" for w in analyze["peringatan"])

    result = _upload(client, auth, "upload-execute", _fc(feature)).json()["data"]["detail_status"]
    assert result["sukses_master_blok_baru"] == 0 and result["sukses_geometri_polygon_blok"] == 0
    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM master.blocks")).scalar() == before
        conn.execute(text("""
            DELETE FROM master.divisions dv WHERE dv.code = 'AFD-KETIGA'
              AND NOT EXISTS (SELECT 1 FROM master.blocks bl WHERE bl.division_id = dv.id)
        """))
