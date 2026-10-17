"""
Struktur v2: grup melekat ke PT, area saat ini melekat ke estate.
Daftar & filter peta (grup, PT -> area), upload GeoJSON blok (sumber resmi grup PT & area estate +
penggabungan blok terpecah), dan peringatan Group/AreaCode di import areal statement.
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
    """sample_block + grup PT & area estatenya, beserta grup/area lain sebagai pembanding."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT co.id AS company_id, co.group_id, gr.code AS grup,
                   (SELECT code FROM master.groups WHERE id IS DISTINCT FROM co.group_id ORDER BY code LIMIT 1) AS other,
                   es.id AS estate_id, es.area_id, ar.code AS area,
                   (SELECT code FROM master.areas WHERE id IS DISTINCT FROM es.area_id ORDER BY code LIMIT 1) AS other_area
            FROM master.estates es JOIN master.companies co ON co.id = es.company_id
            LEFT JOIN master.groups gr ON gr.id = co.group_id
            LEFT JOIN master.areas ar ON ar.id = es.area_id
            WHERE es.code = :e
        """), {"e": sample_block["estate"]}).mappings().one()
        polygon = json.loads(conn.execute(text(
            "SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b ORDER BY period DESC LIMIT 1"),
            {"b": sample_block["id"]}).scalar())
    if row["grup"] is None or row["area"] is None:
        pytest.skip("Database test belum menjalankan migrasi 010 (grup PT & area estate).")
    return {**sample_block, **row, "polygon": polygon}


def _get(client, auth, path, **params):
    response = client.get(f"/api/v1/spatial{path}", headers=auth, params={"limit": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_group_list_and_hierarchy_filters(client, auth, grouped_block):
    b = grouped_block
    groups = {g["kode_grup"]: g for g in _get(client, auth, "/grup")}
    assert {"TPA", "SGA"} <= groups.keys() and groups[b["grup"]]["jumlah_estate"] >= 1

    companies = _get(client, auth, "/pt", kode_grup=b["grup"])
    assert b["company"] in {p["kode_pt"] for p in companies} and all(p["kode_grup"] == b["grup"] for p in companies)
    assert b["company"] not in {p["kode_pt"] for p in _get(client, auth, "/pt", kode_grup=b["other"])}

    # Grup -> PT -> Area -> Estate
    areas = {a["kode_area"] for a in _get(client, auth, "/area", kode_pt=b["company"])}
    assert b["area"] in areas
    with engine.connect() as conn:
        expected = set(conn.execute(text(
            "SELECT DISTINCT ar.code FROM master.estates es JOIN master.areas ar ON ar.id = es.area_id "
            "WHERE es.company_id = :c"), {"c": b["company_id"]}).scalars())
    assert areas == expected

    estates = _get(client, auth, "/estate", kode_pt=b["company"], area_id=b["area"])
    assert b["estate"] in {e["kode_est"] for e in estates}
    assert all(e["kode_area"] == b["area"] and e["kode_grup"] == b["grup"] for e in estates)
    assert b["estate"] not in {e["kode_est"] for e in _get(client, auth, "/estate", area_id=b["other_area"])}

    assert b["division"] in {d["kode_afd"] for d in _get(client, auth, "/afdeling", kode_grup=b["grup"], kode_est=b["estate"])}
    assert _get(client, auth, "/afdeling", kode_grup=b["other"], kode_est=b["estate"]) == []

    blocks = _get(client, auth, "/blok", kode_grup=b["grup"], kode_blok=b["id"])
    assert b["id"] in {x["id"] for x in blocks} and all(x["kode_grup"] == b["grup"] for x in blocks)


def test_geojson_filter_and_property(client, auth, grouped_block):
    b = grouped_block
    params = {"kode_blok": b["id"]}
    fc = client.get("/api/v1/spatial/geojson", headers=auth,
                    params={**params, "kode_grup": b["grup"], "area_id": b["area"]}).json()
    props = fc["features"][0]["properties"]
    assert (props["kode_grup"], props["kode_area"]) == (b["grup"], b["area"])
    for other in ({"kode_grup": b["other"]}, {"area_id": b["other_area"]}):
        assert client.get("/api/v1/spatial/geojson", headers=auth, params={**params, **other}).json()["features"] == []


def _fc(*features) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def _feature(block: dict, polygon: dict, **props) -> dict:
    return {"type": "Feature", "geometry": polygon, "properties": {
        "PT": block["company_name"] or block["company"], "Company_Code": block["company"],
        "Est_ID": block["estate"], "Afdeling": block["division"], "Blok": block["code"], **props}}


def _shifted(polygon: dict, dx: float) -> dict:
    """Salinan poligon yang digeser (potongan kedua blok terpecah, tidak bersinggungan)."""
    def move(coords):
        return [move(c) for c in coords] if isinstance(coords[0], list) else [coords[0] + dx, coords[1]]
    return {"type": polygon["type"], "coordinates": move(polygon["coordinates"])}


def _upload(client, auth, path, content):
    return client.post(f"/api/v1/spatial/blok-geometry/{path}", headers=auth, params={"bulan": BULAN, "tahun": TAHUN},
                       files={"file": ("blok.geojson", content, "application/geo+json")})


def test_block_upload_merges_split_block_and_updates_group_and_area(client, auth, grouped_block):
    b, other, other_area = grouped_block, grouped_block["other"], grouped_block["other_area"]
    content = _fc(_feature(b, b["polygon"], Group=other, Area=other_area, Ownership="Inti"),
                  _feature(b, _shifted(b["polygon"], 0.5), Group=other, Area=other_area))
    try:
        analyze = _upload(client, auth, "upload-analyze", content).json()
        assert analyze["blok_terpecah"] == 1 and analyze["jumlah_blok_akan_disimpan"] == 1
        codes = {w["kode"]: w for w in analyze["peringatan"]}
        assert codes["BLOK_TERPECAH"]["level"] == "INFO" and {"GRUP_BERUBAH", "AREA_BERUBAH"} <= codes.keys()
        assert analyze["rincian"]["grup_pt"] == [{"pemilik": b["company"], "file": other,
                                                  "master": b["grup"], "status": "BERUBAH"}]
        assert analyze["rincian"]["area_estate"] == [{"pemilik": b["estate"], "file": other_area,
                                                      "master": b["area"], "status": "BERUBAH"}]

        result = _upload(client, auth, "upload-execute", content).json()["data"]["detail_status"]
        assert result["sukses_geometri_polygon_blok"] == 2 and result["blok_unik_tersimpan"] == 1
        assert result["blok_terpecah_digabung"] == 1
        assert result["grup_pt_diganti"] == [f"{b['company']}: {b['grup']} -> {other}"]
        assert result["area_estate_diganti"] == [f"{b['estate']}: {b['area']} -> {other_area}"]
        with engine.connect() as conn:
            parts, area_ratio = conn.execute(text("""
                SELECT ST_NumGeometries(n.geom), ST_Area(n.geom) / ST_Area(o.geom)
                FROM spatial.block_boundaries n,
                     (SELECT geom FROM spatial.block_boundaries WHERE block_id = :b AND period <> :p
                      ORDER BY period DESC LIMIT 1) o
                WHERE n.block_id = :b AND n.period = :p
            """), {"b": b["id"], "p": PERIOD}).one()
            group, area = conn.execute(text("""
                SELECT gr.code, ar.code FROM master.estates es JOIN master.companies co ON co.id = es.company_id
                JOIN master.groups gr ON gr.id = co.group_id JOIN master.areas ar ON ar.id = es.area_id
                WHERE es.id = :e"""), {"e": b["estate_id"]}).one()
        assert parts >= 2 and area_ratio == pytest.approx(2, rel=0.01)  # kedua potongan tersimpan
        assert (group, area) == (other, other_area)
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.companies SET group_id = :g WHERE id = :c"),
                         {"g": b["group_id"], "c": b["company_id"]})
            conn.execute(text("UPDATE master.estates SET area_id = :a WHERE id = :e"),
                         {"a": b["area_id"], "e": b["estate_id"]})
            conn.execute(text("DELETE FROM spatial.block_boundaries WHERE block_id = :b AND period = :p"),
                         {"b": b["id"], "p": PERIOD})


def test_block_upload_conflicting_values_leave_master_unchanged(client, auth, grouped_block):
    b = grouped_block
    content = _fc(_feature(b, b["polygon"], Group=b["grup"], Area=b["area"]),
                  _feature(b, b["polygon"], Group=b["other"], Area=b["other_area"]))
    analyze = _upload(client, auth, "upload-analyze", content).json()
    assert analyze["rincian"]["grup_pt"][0]["status"] == "BERTENTANGAN_DI_FILE"
    assert analyze["rincian"]["area_estate"][0]["status"] == "BERTENTANGAN_DI_FILE"
    assert {"GRUP_BERTENTANGAN", "AREA_BERTENTANGAN"} <= {w["kode"] for w in analyze["peringatan"]}


def _xlsx(header, rows) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    for row in [header, *rows]:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_area_statement_group_and_area_mismatch_are_only_warnings(client, auth, grouped_block):
    b = grouped_block
    header = ["Year", "Month", "Group", "AreaCode", "UnitCode", "DivisionCode", "KodeBlok", "StatusTanam"]
    content = _xlsx(header, [[2099, 1, b["other"], b["other_area"], b["estate"], b["division"], b["code"], "TM"],
                             [2099, 2, b["grup"], b["area"], b["estate"], b["division"], b["code"], "TM"]])
    response = client.post("/api/v1/areal-statement/import-excel/analyze", headers=auth,
                           files={"file": ("tes.xlsx", content, "application/octet-stream")})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["baris_siap"] == 2  # baris tetap diimpor
    assert "Group" in report["rincian"]["kolom_dibaca"]
    assert report["rincian"]["peringatan_grup"]["jumlah"] == 1
    assert report["rincian"]["peringatan_area"]["jumlah"] == 1
    assert {"GRUP_BERBEDA", "AREA_BERBEDA"} <= {w["kode"] for w in report["peringatan"]}


def test_block_detail_area_is_current_estate_area_with_period_history(client, auth, grouped_block):
    b = grouped_block
    with engine.connect() as conn:
        period, period_area = conn.execute(text("""
            SELECT a.period, ar.code FROM trx.area_statements a LEFT JOIN master.areas ar ON ar.id = a.area_id
            WHERE a.block_id = :b ORDER BY a.period DESC LIMIT 1"""), {"b": b["id"]}).one()
    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={
        "blok_id": b["id"], "bulan": period.month, "tahun": period.year}).json()
    hierarki = detail["informasi_blok"]["hierarki"]
    assert (hierarki["kode_area"], hierarki["kode_grup"]) == (b["area"], b["grup"])
    assert hierarki["kode_area_periode"] == period_area


def test_rotation_area_column_is_not_compared_with_estate_area(client, auth, grouped_block):
    """Rotasi tidak menyimpan area: kolom Area di file rotasi tidak boleh memicu AREA_BERBEDA."""
    b = grouped_block
    content = _xlsx(["Periode", "Bulan", "Area", "Estate", "Afdeling", "Blok", "Luas", "Pokok", "Rotasi", "Pusingan"],
                    [[2099, 1, b["other_area"], b["estate"], b["division"], b["code"], 10, 100, 3, 4]])
    report = client.post("/api/v1/trx-rotasi-pusingan/import-rotasi-pusingan/analyze", headers=auth,
                         files={"file": ("rot.xlsx", content, "application/octet-stream")}).json()
    assert report["baris_siap"] == 1
    assert report["rincian"]["peringatan_area"]["jumlah"] == 0
    assert "AREA_BERBEDA" not in {w["kode"] for w in report["peringatan"]}


def test_block_upload_matches_area_and_company_by_code_or_name(client, auth, grouped_block):
    """Area ditulis beda (spasi/huruf) = area master yang sama; PT ditulis lewat kode atau nama = satu PT."""
    b = grouped_block
    written = " ".join(b["area"].lower())  # mis. 'BERAU' -> 'b e r a u'
    by_code = _feature(b, b["polygon"], Group=b["grup"], Area=written)
    by_name = _feature(b, _shifted(b["polygon"], 0.5), Group=b["other"])
    by_name["properties"].pop("Company_Code")  # fitur kedua hanya membawa nama PT
    analyze = _upload(client, auth, "upload-analyze", _fc(by_code, by_name)).json()
    assert analyze["rincian"]["area_estate"] == [{"pemilik": b["estate"], "file": b["area"],
                                                  "master": b["area"], "status": "SAMA"}]
    assert "AREA_BARU" not in {w["kode"] for w in analyze["peringatan"]}
    grup = analyze["rincian"]["grup_pt"]
    assert len(grup) == 1 and grup[0]["status"] == "BERTENTANGAN_DI_FILE"


def test_block_upload_sets_company_short_name_from_geojson(client, auth, grouped_block):
    """short_name_pt mengisi/mengganti master.companies.short_name; nilai yang bentrok di file tidak ditulis."""
    b = grouped_block
    same = _fc(_feature(b, b["polygon"], Group=b["grup"], Area=b["area"], short_name_pt="TBP"))
    replaced = _fc(_feature(b, b["polygon"], Group=b["grup"], Area=b["area"], short_name_pt="TBX"))
    conflict = _fc(_feature(b, b["polygon"], Group=b["grup"], Area=b["area"], short_name_pt="AAA"),
                   _feature(b, _shifted(b["polygon"], 0.5), Group=b["grup"], Area=b["area"], short_name_pt="BBB"))
    with engine.begin() as conn:
        previous = conn.execute(text("SELECT short_name FROM master.companies WHERE id = :c"),
                                {"c": b["company_id"]}).scalar()
        conn.execute(text("UPDATE master.companies SET short_name = NULL WHERE id = :c"), {"c": b["company_id"]})
    try:
        analyze = _upload(client, auth, "upload-analyze", same).json()
        assert analyze["rincian"]["nama_pendek_pt"] == [{"pemilik": b["company"], "file": "TBP",
                                                         "master": None, "status": "DIISI"}]
        assert "NAMA_PENDEK_DIISI" in {w["kode"] for w in analyze["peringatan"]}
        assert "Nama pendek" in analyze["kesimpulan"]

        result = _upload(client, auth, "upload-execute", same).json()["data"]["detail_status"]
        assert result["nama_pendek_pt_diisi"] == 1 and result["nama_pendek_pt_diganti"] == []
        with engine.connect() as conn:
            assert conn.execute(text("SELECT short_name FROM master.companies WHERE id = :c"),
                                {"c": b["company_id"]}).scalar() == "TBP"
        assert _get(client, auth, "/pt", kode_pt=b["company"])[0]["short_name_pt"] == "TBP"

        same_spelling = _upload(client, auth, "upload-analyze", _fc(
            _feature(b, b["polygon"], Group=b["grup"], Area=b["area"], short_name_pt="tbp"))).json()
        assert same_spelling["rincian"]["nama_pendek_pt"][0]["status"] == "SAMA"

        changed = _upload(client, auth, "upload-analyze", replaced).json()
        assert changed["rincian"]["nama_pendek_pt"] == [{"pemilik": b["company"], "file": "TBX",
                                                         "master": "TBP", "status": "BERUBAH"}]
        assert "NAMA_PENDEK_BERUBAH" in {w["kode"] for w in changed["peringatan"]}
        executed = _upload(client, auth, "upload-execute", replaced).json()["data"]["detail_status"]
        assert executed["nama_pendek_pt_diganti"] == [f"{b['company']}: TBP -> TBX"]

        clash = _upload(client, auth, "upload-analyze", conflict).json()
        assert clash["rincian"]["nama_pendek_pt"][0]["status"] == "BERTENTANGAN_DI_FILE"
        assert "NAMA_PENDEK_BERTENTANGAN" in {w["kode"] for w in clash["peringatan"]}
        _upload(client, auth, "upload-execute", conflict)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT short_name FROM master.companies WHERE id = :c"),
                                {"c": b["company_id"]}).scalar() == "TBX"
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.companies SET short_name = :s WHERE id = :c"),
                         {"s": previous, "c": b["company_id"]})
            conn.execute(text("DELETE FROM spatial.block_boundaries WHERE block_id = :b AND period = :p"),
                         {"b": b["id"], "p": PERIOD})


def test_area_statement_import_fills_empty_estate_area_only(client, auth, grouped_block):
    b = grouped_block
    header = ["Year", "Month", "AreaCode", "UnitCode", "DivisionCode", "KodeBlok", "StatusTanam"]
    content = _xlsx(header, [[2099, 1, b["area"], b["estate"], b["division"], b["code"], "TM"]])
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.estates SET area_id = NULL WHERE id = :e"), {"e": b["estate_id"]})
        response = client.post("/api/v1/areal-statement/import-excel", headers=auth,
                               files={"file": ("as.xlsx", content, "application/octet-stream")})
        assert response.status_code == 200, response.text
        with engine.connect() as conn:
            assert conn.execute(text("SELECT area_id FROM master.estates WHERE id = :e"),
                                {"e": b["estate_id"]}).scalar() == b["area_id"]
        # Area yang sudah ada tidak diganti oleh AreaCode lain di file.
        other = _xlsx(header, [[2099, 2, b["other_area"], b["estate"], b["division"], b["code"], "TM"]])
        client.post("/api/v1/areal-statement/import-excel", headers=auth,
                    files={"file": ("as.xlsx", other, "application/octet-stream")})
        with engine.connect() as conn:
            assert conn.execute(text("SELECT area_id FROM master.estates WHERE id = :e"),
                                {"e": b["estate_id"]}).scalar() == b["area_id"]
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.estates SET area_id = :a WHERE id = :e"),
                         {"a": b["area_id"], "e": b["estate_id"]})
            conn.execute(text("DELETE FROM trx.area_statements WHERE block_id = :b AND extract(year FROM period) = 2099"),
                         {"b": b["id"]})


def test_manual_master_correction_of_company_group_and_estate_area(client, auth, grouped_block):
    b = grouped_block
    try:
        changed = client.put(f"/api/v1/spatial/pt/{b['company']}/grup", headers=auth, json={"kode_grup": b["other"].lower()})
        assert changed.status_code == 200, changed.text
        assert changed.json() | {"nama_pt": None} == {"kode_pt": b["company"], "nama_pt": None, "kode_grup": b["other"],
                                                       "grup_sebelum": b["grup"], "diubah": True}
        moved = client.put(f"/api/v1/spatial/estate/{b['estate']}/area", headers=auth, json={"kode_area": b["other_area"]})
        assert moved.status_code == 200 and moved.json()["area_sebelum"] == b["area"]
        assert {e["kode_est"] for e in _get(client, auth, "/estate", area_id=b["other_area"])} >= {b["estate"]}

        same = client.put(f"/api/v1/spatial/estate/{b['estate']}/area", headers=auth, json={"kode_area": b["other_area"]})
        assert same.json()["diubah"] is False
        assert client.put(f"/api/v1/spatial/pt/{b['company']}/grup", headers=auth,
                          json={"kode_grup": "TIDAK-ADA"}).status_code == 400
        assert client.put("/api/v1/spatial/estate/TIDAK-ADA/area", headers=auth,
                          json={"kode_area": b["area"]}).status_code == 404
        with engine.connect() as conn:
            logged = conn.execute(text("""
                SELECT count(*) FROM audit.user_activities
                WHERE action IN ('UPDATE_COMPANY_GROUP', 'UPDATE_ESTATE_AREA') AND record_id IN (:c, :e)
            """), {"c": str(b["company_id"]), "e": str(b["estate_id"])}).scalar()
        assert logged >= 2
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE master.companies SET group_id = :g WHERE id = :c"),
                         {"g": b["group_id"], "c": b["company_id"]})
            conn.execute(text("UPDATE master.estates SET area_id = :a WHERE id = :e"),
                         {"a": b["area_id"], "e": b["estate_id"]})


def test_role_group_scope_covers_group_companies_only(client, auth, grouped_block):
    from types import SimpleNamespace
    from uuid import UUID

    from app.db.session import SessionLocal
    from app.services import user_access

    b = grouped_block
    role = client.post("/api/v1/roles/", headers=auth, json={"nama": f"Grup uji {b['grup']} {b['id']}", "deskripsi": "test"})
    assert role.status_code == 201, role.text
    role = role.json()
    try:
        missing = client.post(f"/api/v1/akses-data/data/role/{role['id']}/grup", headers=auth, json={"kode_grup": ["TIDAK-ADA"]})
        assert missing.status_code == 400
        added = client.post(f"/api/v1/akses-data/data/role/{role['id']}/grup", headers=auth,
                            json={"kode_grup": [b["grup"].lower()]})
        assert added.status_code == 201 and added.json()["inserted"] == 1
        again = client.post(f"/api/v1/akses-data/data/role/{role['id']}/grup", headers=auth, json={"kode_grup": [b["grup"]]})
        assert again.json()["inserted"] == 0  # idempoten

        with engine.connect() as conn:
            members = set(conn.execute(text("SELECT id FROM master.companies WHERE group_id = :g"),
                                       {"g": b["group_id"]}).scalars())
        db = SessionLocal()
        try:
            user = SimpleNamespace(roles=[SimpleNamespace(id=UUID(role["id"]), nama=role["nama"])])
            scope = user_access.resolve_scope(db, user)
            assert set(scope.companies) == members and b["company_id"] in members
            assert b["area"] in scope.visible_areas and not scope.area_codes
            codes = user_access.merged_access(db, user)["akses_data"]
            assert b["company"] in {c["kode_pt"] for c in codes}
            assert {c["kode_grup"] for c in codes} == {b["grup"]}
        finally:
            db.close()

        detail = client.get(f"/api/v1/roles/{role['id']}", headers=auth).json()
        assert [(s["level"], s["kode_grup"]) for s in detail["akses_data"]] == [("group", b["grup"])]
        tree = client.get(f"/api/v1/akses-data/data/role/{role['id']}/grup", headers=auth).json()
        assert tree == detail["akses_wilayah_grup"]
        assert len(tree) == 1 and tree[0]["kode_grup"] == b["grup"] and tree[0]["penuh"] is True
        assert tree[0]["perusahaan"] == []  # seluruh grup: PT tidak dirinci

        scope_id = detail["akses_data"][0]["id"]
        assert client.delete(f"/api/v1/akses-data/data/{scope_id}", headers=auth).status_code == 200
        assert client.get(f"/api/v1/roles/{role['id']}", headers=auth).json()["akses_data"] == []
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM auth.roles WHERE id = :id"), {"id": role["id"]})


def test_group_tree_nests_narrow_scopes_under_group_company_area(client, auth, grouped_block):
    b = grouped_block
    role = client.post("/api/v1/roles/", headers=auth, json={"nama": f"Estate uji {b['id']}", "deskripsi": "test"}).json()
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO auth.role_data_scopes (role_id, estate_id) VALUES (:r, :e)"),
                         {"r": role["id"], "e": b["estate_id"]})
        tree = client.get(f"/api/v1/akses-data/data/role/{role['id']}/grup", headers=auth).json()
        assert tree[0]["kode_grup"] == b["grup"] and tree[0]["penuh"] is False
        company = tree[0]["perusahaan"][0]
        assert company["id_perusahaan"] == str(b["company_id"]) and company["penuh"] is False
        area = company["area"][0]
        assert area["kode_area"] == b["area"] and area["penuh"] is False
        assert area["estate"][0]["kode_est"] == b["estate"] and area["estate"][0]["penuh"] is True
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM auth.roles WHERE id = :id"), {"id": role["id"]})
