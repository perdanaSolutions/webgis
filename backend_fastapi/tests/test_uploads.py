import io
import json
import uuid

import pandas as pd
import pytest
from sqlalchemy import text

from app.db.session import engine

BULAN, TAHUN = 1, 2031  # periode khusus test supaya tidak bentrok data asli


@pytest.fixture(scope="module")
def block_geometry(sample_block) -> dict:
    with engine.connect() as conn:
        geom = conn.execute(text("""
            SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b ORDER BY period DESC LIMIT 1
        """), {"b": sample_block["id"]}).scalar()
        centroid = conn.execute(text("""
            SELECT ST_X(c), ST_Y(c) FROM (SELECT ST_PointOnSurface(geom) c FROM spatial.block_boundaries
            WHERE block_id = :b ORDER BY period DESC LIMIT 1) s
        """), {"b": sample_block["id"]}).one()
    return {"polygon": json.loads(geom), "point": [centroid[0], centroid[1]]}


def _props(block: dict, **extra) -> dict:
    return {"PT": block["company_name"] or block["company"], "EstID": block["estate"],
            "Afdeling": block["division"], "Blok": block["code"], **extra}


def _fc(*features) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def _upload(client, auth, path, content, name="data.geojson"):
    return client.post(f"/api/v1/spatial{path}", headers=auth, params={"bulan": BULAN, "tahun": TAHUN},
                       files={"file": (name, content, "application/geo+json")})


def test_block_geometry_upload(client, auth, sample_block, block_geometry):
    content = _fc(
        {"type": "Feature", "properties": _props(sample_block, Area="BERAU", Kategori="Inti"),
         "geometry": block_geometry["polygon"]},
        {"type": "Feature", "properties": {"Blok": "X"}, "geometry": block_geometry["polygon"]},  # properti kurang
    )
    analyze = _upload(client, auth, "/blok-geometry/upload-analyze", content).json()
    assert analyze["total_data"] == 2 and analyze["data_tidak_valid"] == 1
    assert analyze["status_analisis"] == "SIAP_DENGAN_CATATAN" and analyze["jumlah_blok_akan_disimpan"] == 1
    assert analyze["rincian"]["data_tidak_valid"] == [
        {"no_preview": 2, "atribut_kosong": ["Estate (Est_ID/EstID/Est/Estate)", "Afdeling"]}]

    # Blok yang sama di dua fitur dilaporkan sebagai blok terpecah, dihitung sekali sebagai blok.
    feature = {"type": "Feature", "properties": _props(sample_block), "geometry": block_geometry["polygon"]}
    split = _upload(client, auth, "/blok-geometry/upload-analyze", _fc(feature, feature)).json()
    assert split["jumlah_blok_akan_disimpan"] == 1 and split["blok_terpecah"] == 1
    assert split["rincian"]["blok_terpecah"][0]["no_preview"] == [1, 2]
    assert any(w["kode"] == "BLOK_TERPECAH" for w in split["peringatan"])

    result = _upload(client, auth, "/blok-geometry/upload-execute", content).json()["data"]
    assert result["status_proses"] == "PARTIAL_SUCCESS"
    assert result["detail_status"]["sukses_geometri_polygon_blok"] == 1

    fc = client.get("/api/v1/spatial/geojson", headers=auth,
                    params={"kode_blok": sample_block["id"], "bulan": BULAN, "tahun": TAHUN}).json()
    assert fc["features"][0]["properties"]["tahun"] == TAHUN


@pytest.mark.parametrize("layer,geometry_key,props", [
    ("slope", "polygon", {"OBJECTID": 900001, "Kategori": "A", "Kelerengan": "0-8%"}),
    ("landuse", "polygon", {"OBJECTID": 900002, "Landuse": "Kebun", "Class": "Sawit", "Ownership": "Inti"}),
    ("jembatan", "point", {"OBJECTID": 900003, "Kategori": "Kayu"}),
    ("tph", "point", {"Kategori": "Estimasi"}),
])
def test_layer_upload_roundtrip(client, auth, sample_block, block_geometry, layer, geometry_key, props):
    geometry = ({"type": "Polygon", "coordinates": block_geometry["polygon"]["coordinates"][0]}
                if geometry_key == "polygon" else {"type": "Point", "coordinates": block_geometry["point"]})
    content = _fc({"type": "Feature", "properties": _props(sample_block, **props), "geometry": geometry})

    analyze = _upload(client, auth, f"/{layer}/upload-analyze", content).json()["data"]
    assert analyze[f"{layer}_siap_diunggah"] == 1

    for _ in range(2):  # upload ulang harus mengganti, bukan menggandakan
        detail = _upload(client, auth, f"/{layer}/upload-execute", content).json()["detail"]
        assert detail["status_proses"] == "SUCCESS", detail

    listing = client.get(f"/api/v1/spatial/{layer}/list", headers=auth,
                         params={"bulan": BULAN, "tahun": TAHUN, "blok_id": sample_block["id"]}).json()
    assert listing["total_records"] == 1

    geojson_path = "/api/v1/spatial/tph/geojson" if layer == "tph" else f"/api/v1/spatial/{layer}/geojson"
    fc = client.get(geojson_path, headers=auth, params={"bulan": BULAN, "tahun": TAHUN}).json()
    assert len(fc["features"]) == 1

    cleanup = client.delete(f"/api/v1/spatial/{layer}/cleanup-period", headers=auth, params={"bulan": BULAN, "tahun": TAHUN})
    assert cleanup.json()["data_terhapus"] == 1


def test_layer_analyze_reports_rejected_features(client, auth, sample_block, block_geometry):
    point = {"type": "Point", "coordinates": block_geometry["point"]}
    content = _fc(
        {"type": "Feature", "properties": _props(sample_block, OBJECTID=900010, Kategori="Kayu"), "geometry": point},
        {"type": "Feature", "properties": {"OBJECTID": 900011, "Blok": "X"}, "geometry": point},           # atribut kurang
        {"type": "Feature", "properties": _props(sample_block, OBJECTID=900012), "geometry": None},        # tanpa geometri
        {"type": "Feature", "properties": _props(sample_block, OBJECTID=900010, Kategori="Beton"), "geometry": point},
    )
    analyze = _upload(client, auth, "/jembatan/upload-analyze", content).json()["data"]
    assert analyze["status_analisis"] == "SIAP_DENGAN_CATATAN"
    assert analyze["jembatan_siap_diunggah"] == 1
    rejected = {r["no_preview"]: r["kode"] for r in analyze["rincian"]["data_ditolak"]}
    assert rejected == {1: "OBJECTID_GANDA", 2: "ATRIBUT_BLOK_KOSONG", 3: "GEOMETRI_TIDAK_VALID"}
    assert {w["kode"] for w in analyze["peringatan"]} >= {"OBJECTID_GANDA", "ATRIBUT_BLOK_KOSONG", "GEOMETRI_TIDAK_VALID"}
    assert "3 data ditolak" in analyze["kesimpulan"]


def test_wrong_block_label_is_matched_by_geometry(client, auth, sample_block, block_geometry):
    # Label afdeling salah (kasus nyata di Sawit/TPH_Sample: AFDI03 padahal lokasinya AFDI04)
    props = _props(sample_block, OBJECTID=900005, Kategori="Kayu")
    props["Afdeling"] = "AFD-SALAH"
    content = _fc({"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": block_geometry["point"]}})

    analyze = _upload(client, auth, "/jembatan/upload-analyze", content).json()["data"]
    assert analyze["jembatan_siap_diunggah"] == 1 and analyze["dicocokkan_spasial"] == 1
    correction = analyze["koreksi_label_blok"][0]
    assert correction["label_file"].endswith("/AFD-SALAH/" + sample_block["code"])
    assert correction["blok_master"] == f"{sample_block['estate']}/{sample_block['division']}/{sample_block['code']}"

    detail = _upload(client, auth, "/jembatan/upload-execute", content).json()["detail"]
    assert detail["status_proses"] == "SUCCESS"
    row = client.get("/api/v1/spatial/jembatan/list", headers=auth, params={"bulan": BULAN, "tahun": TAHUN}).json()["data"][0]
    assert row["blok_id"] == sample_block["id"]
    client.delete("/api/v1/spatial/jembatan/cleanup-period", headers=auth, params={"bulan": BULAN, "tahun": TAHUN})


def test_road_upload_linestring_is_promoted_to_multi(client, auth, sample_block, block_geometry):
    x, y = block_geometry["point"]
    content = _fc({"type": "Feature", "properties": _props(sample_block, OBJECTID=900004, Lebar=4.5),
                   "geometry": {"type": "LineString", "coordinates": [[x, y], [x + 0.0005, y + 0.0005]]}})
    detail = _upload(client, auth, "/jalan/upload-execute", content).json()["detail"]
    assert detail["status_proses"] == "SUCCESS"
    row = client.get("/api/v1/spatial/jalan/list", headers=auth, params={"bulan": BULAN, "tahun": TAHUN}).json()["data"][0]
    assert row["lebar"] == 4.5 and row["geometry"]["type"] == "MultiLineString"


def test_sawit_upload(client, auth, sample_block, block_geometry):
    x, y = block_geometry["point"]
    features = [
        {"type": "Feature", "properties": _props(sample_block, OBJECTID=990000001 + i, Diameter=0.5, Jarak=9, Kategori="Normal"),
         "geometry": {"type": "Point", "coordinates": [x + i * 1e-5, y]}}
        for i in range(3)
    ]
    detail = _upload(client, auth, "/sawit/upload-execute", _fc(*features)).json()["detail"]
    assert detail["detail_status"]["sukses_terunggah"] == 3
    fc = client.get("/api/v1/spatial/sawit/geojson", headers=auth, params={"bulan": BULAN, "tahun": TAHUN}).json()
    assert {f["properties"]["objectid"] for f in fc["features"]} == {990000001, 990000002, 990000003}


def test_generic_layer_lifecycle(client, auth, sample_block, block_geometry, monkeypatch):
    code = f"uji_{uuid.uuid4().hex[:6]}"
    sample = _fc({"type": "Feature", "properties": _props(sample_block, Nama="Sumur 1", Kedalaman=12.5),
                  "geometry": {"type": "Point", "coordinates": block_geometry["point"]}})
    proposal = client.post("/api/v1/spatial/geo/jenis/analyze-sample", headers=auth,
                           files={"file": ("s.geojson", sample, "application/json")}).json()
    assert proposal["geometry_type"] == "POINT"

    created = client.post("/api/v1/spatial/geo/jenis", headers=auth, json={
        "kode": code, "nama": "Uji", "geometry_type": "POINT", "relasi_blok": True, "kolom": proposal["kolom"]})
    assert created.status_code == 200, created.text

    result = _upload(client, auth, f"/geo/{code}/upload-execute", sample).json()["data"]
    assert result["status_proses"] == "SUCCESS"
    rows = client.get(f"/api/v1/spatial/geo/{code}", headers=auth).json()
    assert rows["total_data"] == 1 and rows["data"][0]["kedalaman"] == 12.5
    assert rows["data"][0]["kode_est"] == sample_block["estate"]

    # Nilai atribut yang tidak cocok tipe kolom -> disimpan kosong & dilaporkan, upload tetap jalan.
    bad = _fc({"type": "Feature", "properties": _props(sample_block, Nama="Sumur 2", Kedalaman="dalam"),
               "geometry": {"type": "Point", "coordinates": block_geometry["point"]}})
    analyze = _upload(client, auth, f"/geo/{code}/upload-analyze", bad).json()
    assert analyze["siap_diunggah"] == 1 and analyze["nilai_atribut_invalid"] == 1
    result = _upload(client, auth, f"/geo/{code}/upload-execute", bad).json()["data"]
    assert result["status_proses"] == "SUCCESS" and result["detail_status"]["nilai_atribut_invalid"] == 1

    params = {"bulan": BULAN, "tahun": TAHUN}
    fc = client.get(f"/api/v1/spatial/geo/{code}/geojson", headers=auth, params=params).json()
    props = fc["features"][0]["properties"]
    assert props["kedalaman"] is None
    assert (props["kode_est"], props["kode_afd"], props["kode_blok"]) == (
        sample_block["estate"], sample_block["division"], sample_block["code"])

    # Filter hierarki seperti layer bawaan (+ alias lama blok_id).
    for extra, expected in (({"kode_est": sample_block["estate"]}, 1), ({"kode_est": "TIDAK-ADA"}, 0),
                            ({"blok_id": str(sample_block["id"])}, 1)):
        fc = client.get(f"/api/v1/spatial/geo/{code}/geojson", headers=auth, params={**params, **extra}).json()
        assert len(fc["features"]) == expected, extra

    # Scope wilayah user diterapkan.
    from app.services import user_access
    with engine.connect() as conn:
        estate_id = conn.execute(text("SELECT dv.estate_id FROM master.blocks bl JOIN master.divisions dv "
                                      "ON dv.id = bl.division_id WHERE bl.id = :b"), {"b": sample_block["id"]}).scalar()
    for estates, expected in (([estate_id], 1), ([-1], 0)):
        monkeypatch.setattr(user_access, "resolve_scope", lambda db, user, e=estates: user_access.DataScope(estates=e))
        fc = client.get(f"/api/v1/spatial/geo/{code}/geojson", headers=auth, params=params).json()
        listing = client.get(f"/api/v1/spatial/geo/{code}", headers=auth, params=params).json()
        assert len(fc["features"]) == listing["total_data"] == expected, estates
    monkeypatch.undo()
    client.delete(f"/api/v1/spatial/geo/{code}/cleanup-period", headers=auth, params=params)

    legacy = client.post("/api/v1/spatial/geo/blok/upload-analyze", headers=auth,
                         params={"bulan": BULAN, "tahun": TAHUN}, files={"file": ("a", sample, "application/json")})
    assert legacy.status_code == 400  # endpoint generik menolak jenis LEGACY


@pytest.fixture
def clean_trx_period():
    """cleanup-period hanya menghapus data spasial; data transaksi periode uji dibersihkan di sini agar tes idempoten."""
    def wipe():
        with engine.begin() as conn:
            for table in ("trx.block_productions", "trx.harvest_rotations", "trx.area_statements"):
                conn.execute(text(f"DELETE FROM {table} WHERE period = make_date(:t, :m, 1)"), {"t": TAHUN, "m": BULAN})
    wipe()
    yield
    wipe()


def test_excel_imports(client, auth, sample_block, clean_trx_period):
    base = {"UnitCode": sample_block["estate"], "DivisionCode": sample_block["division"],
            "KodeBlok": sample_block["code"], "Month": BULAN, "Year": TAHUN}

    def xlsx(rows) -> bytes:
        buffer = io.BytesIO()
        pd.DataFrame(rows).to_excel(buffer, index=False)
        return buffer.getvalue()

    areal = [{**base, "AreaCode": "BERAU", "StatusTanam": "TM", "TahunTanam": 2010, "BulanTanam": "Mar",
              "JenisBibit": "Socfindo, Lonsum", "JenisTanah": "PASIR", "JenisTopografi": "DATAR",
              "LuasTanam": 25.5, "LuasTanah": 26, "TotalPokok": 3500, "SPH": 137, "TanahDatar": 60, "Berbukit": 40},
             {**base, "KodeBlok": "TIDAK-ADA"}]
    response = client.post("/api/v1/areal-statement/import-excel", headers=auth,
                           files={"file": ("areal.xlsx", xlsx(areal), "application/vnd.ms-excel")}).json()
    assert response["details"]["success_count"] == 1 and response["details"]["missing_blok_count"] == 1

    with engine.connect() as conn:
        seeds = conn.execute(text("""
            SELECT sv.name FROM trx.area_statements a
            JOIN trx.area_statement_seed_varieties x ON x.area_statement_id = a.id
            JOIN ref.seed_varieties sv ON sv.id = x.seed_variety_id
            WHERE a.block_id = :b AND a.period = make_date(:t, :m, 1) ORDER BY 1
        """), {"b": sample_block["id"], "t": TAHUN, "m": BULAN}).scalars().all()
        soil = conn.execute(text("""
            SELECT so.name FROM trx.area_statements a JOIN ref.soil_types so ON so.id = a.soil_type_id
            WHERE a.block_id = :b AND a.period = make_date(:t, :m, 1)
        """), {"b": sample_block["id"], "t": TAHUN, "m": BULAN}).scalar()
    assert seeds == ["Lonsum", "Socfindo"]
    assert soil == "Tanah Pasir"  # alias PASIR -> Tanah Pasir dari ref.value_aliases

    production = [{**base, "TbsAktual": 12000, "TbsBudget": 10000, "JanjangAktual": 600, "BjrAktual": 20}]
    first = client.post("/api/v1/pokok-produksi/import-produksi-tbs", headers=auth,
                        files={"file": ("p.xlsx", xlsx(production), "application/vnd.ms-excel")}).json()["details"]
    again = client.post("/api/v1/pokok-produksi/import-produksi-tbs", headers=auth,
                        files={"file": ("p.xlsx", xlsx(production), "application/vnd.ms-excel")}).json()["details"]
    assert first["data_baru"] == 1
    assert again["data_tidak_berubah"] == 1 and again["data_diperbarui"] == 0  # impor ulang tidak menulis ulang

    rotation = [{"Blok": sample_block["code"], "Estate": sample_block["estate"], "Afdeling": sample_block["division"],
                 "Bulan": BULAN, "Tahun": TAHUN, "Rotasi": 3, "Pusingan": 9, "Status Pusingan": "(Blanks)",
                 "Luas": 25, "Pokok": 3400}]
    response = client.post("/api/v1/trx-rotasi-pusingan/import-rotasi-pusingan", headers=auth,
                           files={"file": ("r.xlsx", xlsx(rotation), "application/vnd.ms-excel")}).json()
    assert response["details"]["success_count"] == 1
    assert response["details"]["nilai_referensi_baru"] == {}  # '(Blanks)' = kosong, bukan status baru

    detail = client.get("/api/v1/spatial/blok/detail", headers=auth,
                        params={"blok_id": sample_block["id"], "bulan": BULAN, "tahun": TAHUN}).json()
    assert detail["produksi_tbs"]["tbs"]["aktual"] == 12000
    assert detail["produksi_tbs"]["kategori_budget"] == "OPTIMUM"  # aktual 12000 >= budget 10000 (gap > 0%)
    assert "areal_statement" not in detail
    assert detail["rotasi_pusingan"]["total_kegiatan"] == 1

    bad = client.post("/api/v1/areal-statement/import-excel", headers=auth,
                      files={"file": ("x.csv", b"a,b", "text/csv")})
    assert bad.status_code == 400


def test_cleanup_period(client, auth):
    result = client.delete("/api/v1/spatial/cleanup-period", headers=auth, params={"bulan": BULAN, "tahun": TAHUN}).json()
    assert result["status"] == "success"
    assert result["detail_terhapus"]["geometri_polygon_blok"] >= 1
