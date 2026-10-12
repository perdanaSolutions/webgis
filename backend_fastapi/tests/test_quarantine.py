"""Baris/fitur upload yang tidak lolos validasi masuk ke karantina (quarantine.rows)."""
import json
import uuid

import pytest
from sqlalchemy import text

from app.db.session import engine

BULAN, TAHUN = 2, 2031  # periode khusus test (beda dari test_uploads supaya tidak saling hapus)
URL = "/api/v1/karantina/"


@pytest.fixture
def clean_period():
    def wipe():
        with engine.begin() as conn:
            for table in ("trx.block_productions", "trx.harvest_rotations", "trx.area_statements"):
                conn.execute(text(f"DELETE FROM {table} WHERE period = make_date(:t, :m, 1)"), {"t": TAHUN, "m": BULAN})
            for table in ("spatial.bridges", "spatial.block_boundaries"):
                if conn.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar():
                    conn.execute(text(f"DELETE FROM {table} WHERE period = make_date(:t, :m, 1)"), {"t": TAHUN, "m": BULAN})
    wipe()
    yield
    wipe()


def _rows(client, auth, batch_id: str, **params) -> list[dict]:
    body = client.get(URL, headers=auth, params={"upload_batch_id": batch_id, "limit": 100, **params}).json()
    return sorted(body["data"], key=lambda r: int(r["no_baris"]))


def test_trx_json_rejected_rows_are_quarantined(client, auth, sample_block, clean_period):
    base = {"UnitCode": sample_block["estate"], "DivisionCode": sample_block["division"],
            "KodeBlok": sample_block["code"], "Bulan": BULAN, "Tahun": TAHUN}
    response = client.post("/api/v1/pokok-produksi/import-json", headers=auth, json={"sumber": "uji-karantina", "data": [
        {**base, "TbsAktual": 1000, "JanjangAktual": 50},          # 1 lolos
        {**base, "KodeBlok": "TIDAK-ADA", "TbsAktual": 1},          # 2 blok tidak ada
        {**base, "Bulan": None, "Tahun": None, "TbsAktual": 1},     # 3 periode tidak valid
        {**base, "KodeBlok": "", "TbsAktual": 1},                   # 4 kode blok kosong
        {**base, "TbsAktual": -5},                                  # 5 nilai negatif
    ]})
    assert response.status_code == 200, response.text
    details = response.json()["details"]
    assert details["success_count"] == 1 and details["karantina_count"] == 4

    rows = _rows(client, auth, details["batch_id"])
    assert [(r["no_baris"], r["kode_alasan"]) for r in rows] == [
        ("2", "BLOK_TIDAK_DITEMUKAN"), ("3", "NILAI_TIDAK_VALID"), ("4", "KODE_BLOK_KOSONG"), ("5", "NILAI_TIDAK_VALID")]
    assert rows[0]["tabel_tujuan"] == "trx.block_productions"
    assert rows[0]["data"]["KodeBlok"] == "TIDAK-ADA"  # baris asli tersimpan utuh
    assert rows[0]["nama_file"] == "uji-karantina" and rows[0]["jenis_sumber"] == "JSON_API"
    assert "TbsAktual tidak boleh negatif" in rows[3]["alasan"]

    only_missing = _rows(client, auth, details["batch_id"], reason_code="blok_tidak_ditemukan")
    assert [r["no_baris"] for r in only_missing] == ["2"]


def test_trx_conflicting_duplicates_are_quarantined(client, auth, sample_block, clean_period):
    base = {"UnitCode": sample_block["estate"], "DivisionCode": sample_block["division"],
            "KodeBlok": sample_block["code"], "Bulan": BULAN, "Tahun": TAHUN}
    details = client.post("/api/v1/pokok-produksi/import-json", headers=auth, json={"data": [
        {**base, "TbsAktual": 1000, "JanjangAktual": 50},
        {**base, "TbsAktual": 2000, "JanjangAktual": 90},  # baris lengkap kedua yang berbeda -> konflik
    ]}).json()["details"]
    assert details["success_count"] == 0 and details["karantina_count"] == 2
    rows = _rows(client, auth, details["batch_id"])
    assert {r["kode_alasan"] for r in rows} == {"DUPLIKAT_BERTENTANGAN"}
    assert [r["data"]["TbsAktual"] for r in rows] == [1000, 2000]


def test_geojson_rejected_features_are_quarantined(client, auth, sample_block, clean_period):
    with engine.connect() as conn:
        x, y = conn.execute(text("""
            SELECT ST_X(c), ST_Y(c) FROM (SELECT ST_PointOnSurface(geom) c FROM spatial.block_boundaries
            WHERE block_id = :b ORDER BY period DESC LIMIT 1) s
        """), {"b": sample_block["id"]}).one()
    point = {"type": "Point", "coordinates": [x, y]}
    props = {"EstID": sample_block["estate"], "Afdeling": sample_block["division"], "Blok": sample_block["code"]}
    content = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {**props, "OBJECTID": 910001, "Kategori": "Kayu"}, "geometry": point},
        {"type": "Feature", "properties": {"OBJECTID": 910002, "Blok": "X"}, "geometry": point},
        {"type": "Feature", "properties": {**props, "OBJECTID": 910003}, "geometry": None},
    ]}).encode()
    detail = client.post("/api/v1/spatial/jembatan/upload-execute", headers=auth, params={"bulan": BULAN, "tahun": TAHUN},
                         files={"file": ("q.geojson", content, "application/geo+json")}).json()["detail"]
    assert detail["detail_status"]["karantina_count"] == 2

    rows = _rows(client, auth, detail["batch_id"])
    assert [(r["no_baris"], r["kode_alasan"]) for r in rows] == [("2", "ATRIBUT_BLOK_KOSONG"), ("3", "GEOMETRI_TIDAK_VALID")]
    assert rows[0]["data"] == {"OBJECTID": 910002, "Blok": "X"}  # daftar: properti saja

    full = client.get(f"{URL}{rows[0]['id']}", headers=auth).json()
    assert full["data"]["type"] == "Feature" and full["data"]["geometry"] == point  # detail: fitur utuh


def test_block_upload_rejected_features_are_quarantined(client, auth, sample_block, clean_period):
    with engine.connect() as conn:
        polygon = json.loads(conn.execute(text(
            "SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b ORDER BY period DESC LIMIT 1"
        ), {"b": sample_block["id"]}).scalar())
    content = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"Blok": "X"}, "geometry": polygon},
    ]}).encode()
    result = client.post("/api/v1/spatial/blok-geometry/upload-execute", headers=auth,
                         params={"bulan": BULAN, "tahun": TAHUN},
                         files={"file": ("b.geojson", content, "application/geo+json")}).json()["data"]
    assert result["detail_status"]["karantina_count"] == 1
    rows = _rows(client, auth, result["batch_id"])
    assert rows[0]["kode_alasan"] == "ATRIBUT_BLOK_KOSONG" and rows[0]["tabel_tujuan"] == "spatial.block_boundaries"


def test_quarantine_hidden_from_other_users(client, auth, sample_block, clean_period, monkeypatch):
    details = client.post("/api/v1/pokok-produksi/import-json", headers=auth, json={"data": [
        {"UnitCode": sample_block["estate"], "KodeBlok": "TIDAK-ADA", "Bulan": BULAN, "Tahun": TAHUN}]}).json()["details"]
    row_id = _rows(client, auth, details["batch_id"])[0]["id"]

    from app.api.v1.endpoints import quarantine as endpoint
    monkeypatch.setattr(endpoint, "_own_only", lambda db, user: uuid.uuid4())  # user lain tanpa hak kelola
    assert _rows(client, auth, details["batch_id"]) == []
    assert client.get(f"{URL}{row_id}", headers=auth).status_code == 404
    assert client.get(URL).status_code == 401
