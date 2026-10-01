def test_hierarchy_lists(client, auth, sample_block):
    areas = client.get("/api/v1/spatial/area", headers=auth, params={"limit": 100}).json()
    assert areas["total_data"] >= 1 and {"area_id", "kode_area", "nama"} <= areas["data"][0].keys()

    pts = client.get("/api/v1/spatial/pt", headers=auth, params={"kode_pt": sample_block["company"]}).json()
    assert pts["data"][0]["kode_pt"] == sample_block["company"]

    by_area = client.get("/api/v1/spatial/pt", headers=auth, params={"area_id": areas["data"][0]["area_id"]}).json()
    assert all(p["area_id"] == areas["data"][0]["area_id"] for p in by_area["data"])

    estates = client.get("/api/v1/spatial/estate", headers=auth, params={"kode_pt": sample_block["company"]}).json()
    assert sample_block["estate"] in {e["kode_est"] for e in estates["data"]}

    divisions = client.get("/api/v1/spatial/afdeling", headers=auth, params={"kode_est": sample_block["estate"]}).json()
    assert sample_block["division"] in {d["kode_afd"] for d in divisions["data"]}


def test_block_list_accepts_empty_params(client, auth, sample_block):
    # FE mengirim filter kosong seperti ini
    response = client.get(f"/api/v1/spatial/blok?kode_pt=&kode_est={sample_block['estate']}"
                          f"&kode_afd={sample_block['division']}&tahun=&limit=100", headers=auth)
    assert response.status_code == 200, response.text
    blocks = response.json()["data"]
    block = next(b for b in blocks if b["id"] == sample_block["id"])
    assert block["kode_blok"] == sample_block["code"]


def test_blocks_geojson(client, auth, sample_block):
    fc = client.get("/api/v1/spatial/geojson", headers=auth,
                    params={"kode_est": sample_block["estate"], "kode_blok": str(sample_block["id"])}).json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["blok_id"] == sample_block["id"]
    assert fc["features"][0]["geometry"]["type"] == "MultiPolygon"

    # FE mengirim kode_blok = kode blok (bukan id) juga harus bisa
    by_code = client.get("/api/v1/spatial/geojson", headers=auth,
                         params={"kode_est": sample_block["estate"], "kode_afd": sample_block["division"],
                                 "kode_blok": sample_block["code"]}).json()
    assert len(by_code["features"]) == 1


def test_blocks_geojson_hides_unauthorized_transaction_keys(client, auth, sample_block, monkeypatch):
    from app.services import user_access
    monkeypatch.setattr(user_access, "hidden_feature_keys",
                        lambda db, user: ("areal_statement", "produksi_tbs", "rotasi_terakhir"))
    fc = client.get("/api/v1/spatial/geojson", headers=auth,
                    params={"kode_est": sample_block["estate"], "kode_blok": str(sample_block["id"])}).json()
    props = fc["features"][0]["properties"]
    assert props["blok_id"] == sample_block["id"]
    assert not {"areal_statement", "produksi_tbs", "rotasi_terakhir"} & props.keys()


def test_block_detail(client, auth, sample_block):
    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": sample_block["id"]}).json()
    assert detail["informasi_blok"]["blok_id"] == sample_block["id"]
    assert detail["informasi_blok"]["hierarki"]["kode_est"] == sample_block["estate"]
    assert {"tbs", "janjang", "bjr", "kpi_per_pokok"} <= detail["produksi_tbs"].keys()

    missing = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": "999999999"})
    assert missing.status_code == 404

    # Bulan+tahun yang tidak ada -> data transaksi terakhir, bukan angka nol tahun kosong.
    fallback = client.get("/api/v1/spatial/blok/detail", headers=auth,
                          params={"blok_id": sample_block["id"], "bulan": 1, "tahun": 2099}).json()
    assert fallback["mode"] == "LATEST_TAHUN_TANAM"
    assert fallback["periode"]["tahun"] and fallback["periode"]["tahun"] != 2099

    exact = client.get("/api/v1/spatial/blok/detail", headers=auth, params={
        "blok_id": sample_block["id"],
        "bulan": fallback["periode"]["bulan"],
        "tahun": fallback["periode"]["tahun"],
    }).json()
    assert exact["mode"] == "SPESIFIK_TAHUN_TANAM"
    assert exact["periode"]["bulan"] == fallback["periode"]["bulan"]
    assert exact["periode"]["tahun"] == fallback["periode"]["tahun"]


def test_history_tables(client, auth, sample_block):
    tables = client.get("/api/v1/spatial/history/tables", headers=auth).json()
    assert [t["table"] for t in tables] == ["trx_produksi_tbs", "trx_areal_statement", "trx_rotasi_pusingan"]

    yearly = client.get("/api/v1/spatial/history", headers=auth,
                        params={"table": "trx_produksi_tbs", "kode_est": sample_block["estate"]}).json()
    assert yearly["mode_akumulasi"] == "TAHUNAN" and yearly["data_histori"]

    monthly = client.get("/api/v1/spatial/history", headers=auth,
                         params={"table": "trx_produksi_tbs", "tahun": 2025, "kode_est": sample_block["estate"]}).json()
    assert monthly["mode_akumulasi"] == "BULANAN"
    assert all(row["tahun"] == 2025 for row in monthly["data_histori"])

    areal = client.get("/api/v1/spatial/history", headers=auth, params={"table": "trx_areal_statement"}).json()
    assert areal["status"] == "success" and "grand_total" in areal

    rotation = client.get("/api/v1/spatial/history", headers=auth, params={"table": "trx_rotasi_pusingan"}).json()
    assert rotation["mode_akumulasi"] == "TAHUNAN"

    invalid = client.get("/api/v1/spatial/history", headers=auth, params={"table": "auth.users"})
    assert invalid.status_code == 400


def test_catalog(client, auth):
    catalog = client.get("/api/v1/spatial/geo/catalog", headers=auth).json()
    codes = {c["kode"]: c for c in catalog}
    assert {"blok", "tph", "sawit", "slope", "landuse", "jalan", "jembatan"} <= codes.keys()
    # setiap endpoint katalog harus benar-benar ada di API (FE memanggil /spatial + endpoint)
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    for item in catalog:
        for key in ("upload_analyze", "upload_execute", "geojson"):
            path = "/api/v1/spatial" + item["endpoints"][key]
            path = path.replace(f"/geo/{item['kode']}/", "/geo/{kode}/")
            assert path in paths, f"{item['kode']}.{key} -> {path} tidak ada"
