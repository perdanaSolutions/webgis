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


def test_block_list_filters_by_tahun_tanam(client, auth, sample_block):
    base = {"kode_est": sample_block["estate"], "kode_afd": sample_block["division"], "limit": 100}
    all_blocks = client.get("/api/v1/spatial/blok", headers=auth, params=base).json()["data"]
    years = {b["tahun_tanam"] for b in all_blocks if b.get("tahun_tanam")}
    assert years, "Sampel tidak punya blok dengan tahun tanam"

    year = sorted(years)[0]
    response = client.get("/api/v1/spatial/blok", headers=auth, params={**base, "tahun_tanam": year})
    assert response.status_code == 200, response.text
    filtered = response.json()["data"]
    assert filtered and all(b["tahun_tanam"] == year for b in filtered)
    assert len(filtered) == sum(1 for b in all_blocks if b["tahun_tanam"] == year)

    empty = client.get("/api/v1/spatial/blok", headers=auth, params={**base, "tahun_tanam": 1901}).json()
    assert empty["data"] == []


def test_block_list_tahun_tanam_with_periode(client, auth, sample_block):
    from sqlalchemy import text
    from app.db.session import engine

    with engine.connect() as conn:
        periods = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT period FROM trx.area_statements WHERE block_id = :b ORDER BY period"
        ), {"b": sample_block["id"]})]
    period = periods[-1]  # periode terakhir statement sampel; periode lebih awal bila ada
    base = {"kode_est": sample_block["estate"], "kode_afd": sample_block["division"], "limit": 100,
            "bulan": period.month, "tahun": period.year}

    all_blocks = client.get("/api/v1/spatial/blok", headers=auth, params=base).json()["data"]
    years = {b["tahun_tanam"] for b in all_blocks if b.get("tahun_tanam")}
    assert years
    year = sorted(years)[0]

    response = client.get("/api/v1/spatial/blok", headers=auth, params={**base, "tahun_tanam": year})
    assert response.status_code == 200, response.text
    filtered = response.json()["data"]
    assert filtered and all(b["tahun_tanam"] == year for b in filtered)
    assert len(filtered) == sum(1 for b in all_blocks if b["tahun_tanam"] == year)

    # bulan+tahun sebelum statement pertama: tidak ada snapshot, jadi tidak ada blok yang cocok
    early = client.get("/api/v1/spatial/blok", headers=auth,
                       params={**base, "bulan": 1, "tahun": 1900, "tahun_tanam": year}).json()
    assert early["data"] == []


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
    from sqlalchemy import text

    from app.db.session import engine

    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": sample_block["id"]}).json()
    info = detail["informasi_blok"]
    assert info["blok_id"] == sample_block["id"]
    assert info["hierarki"]["kode_est"] == sample_block["estate"]
    assert {"luas_tanam", "luas_tanah", "pokok", "sph", "tbs", "jjg", "bjr", "yield", "gap_act_bgt", "gap_act_sns"} <= info.keys()
    assert "produksi_tbs" not in detail and "rotasi_pusingan" not in detail

    missing = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": "999999999"})
    assert missing.status_code == 404

    # Bulan+tahun yang tidak ada tetap periode filter, angka nol, bukan transaksi terakhir.
    empty = client.get("/api/v1/spatial/blok/detail", headers=auth,
                       params={"blok_id": sample_block["id"], "bulan": 1, "tahun": 2099}).json()
    assert empty["mode"] == "PERIODE_BULAN_TAHUN"
    assert empty["periode"] == {"bulan": 1, "tahun": 2099, "label_periode": "Tahun 2099"}
    assert empty["informasi_blok"]["tbs"]["aktual"] == 0
    assert empty["informasi_blok"]["yield"]["aktual"] == 0
    assert empty["informasi_blok"]["gap_act_bgt"] == {"value": 0.0, "kategori": ""}
    assert empty["informasi_blok"]["gap_act_sns"] == {"value": 0.0, "kategori": ""}

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT p.period,
                   SUM(p.ffb_actual_kg) AS tbs_aktual, SUM(p.ffb_budget_kg) AS tbs_budget, SUM(p.ffb_census_kg) AS tbs_sensus,
                   SUM(p.bunches_actual) AS jjg_aktual, AVG(p.bjr_actual) AS bjr_aktual,
                   MAX(a.planted_area_ha) AS luas_tanam, MAX(a.land_area_ha) AS luas_tanah,
                   MAX(a.tree_count) AS pokok, MAX(a.sph) AS sph
            FROM trx.block_productions p
            LEFT JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
            WHERE p.block_id = :bid
            GROUP BY p.period
            ORDER BY p.period DESC LIMIT 1
        """), {"bid": sample_block["id"]}).mappings().one()

    # Periode sebelum transaksi pertama -> tidak ada data, bukan data terbaru.
    before = client.get("/api/v1/spatial/blok/detail", headers=auth,
                        params={"blok_id": sample_block["id"], "bulan": 1, "tahun": 1900})
    assert before.status_code == 200, before.text
    body = before.json()
    assert body["mode"] == "TIDAK_ADA_DATA"
    assert body["periode"]["tahun"] == 1900
    assert body["produksi_tbs"]["tbs"]["aktual"] == 0
    assert body["produksi_tbs"]["ringkasan_gap_budget"] is None
    assert body["rotasi_pusingan"]["total_kegiatan"] == 0

    exact = client.get("/api/v1/spatial/blok/detail", headers=auth, params={
        "blok_id": sample_block["id"],
        "bulan": row["period"].month,
        "tahun": row["period"].year,
    }).json()
    got = exact["informasi_blok"]
    assert exact["mode"] == "PERIODE_BULAN_TAHUN"
    assert exact["periode"]["bulan"] == row["period"].month
    assert exact["periode"]["tahun"] == row["period"].year
    assert exact["periode"]["label_periode"] == f"Tahun {row['period'].year}"

    def money(value):
        return round(float(value or 0), 2)

    luas = money(row["luas_tanam"]) if row["luas_tanam"] is not None else 0.0

    def yield_ha(kg):
        return round(float(kg or 0) / 1000 / luas, 2) if luas else 0.0

    def gap(actual, target):
        if not target:
            return 0.0
        value = round((actual - target) / target * 100, 2)
        return 0.0 if value == 0 else value

    y_act = yield_ha(row["tbs_aktual"])
    y_bgt = yield_ha(row["tbs_budget"])
    y_sns = yield_ha(row["tbs_sensus"])
    assert got["luas_tanam"] == luas
    assert got["tbs"]["aktual"] == money(row["tbs_aktual"])
    assert got["jjg"]["aktual"] == int(row["jjg_aktual"] or 0)
    assert got["bjr"]["aktual"] == money(row["bjr_aktual"])
    def kategori(value):
        if value < -40:
            return "GAP III"
        if -40 <= value <= -20:
            return "GAP II"
        if -20 < value < 0:
            return "GAP I"
        if value > 0:
            return "OPTIMUM"
        return ""

    assert got["yield"] == {"aktual": y_act, "budget": y_bgt, "sensus": y_sns}
    assert got["gap_act_bgt"] == {"value": gap(y_act, y_bgt), "kategori": kategori(gap(y_act, y_bgt))}
    assert got["gap_act_sns"] == {"value": gap(y_act, y_sns), "kategori": kategori(gap(y_act, y_sns))}


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
    assert areal["status"] == "success"
    assert set(areal["data"]) == {"group_tahun_tanam", "group_divisi"}

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


def test_sawit_list_filters_by_tahun_tanam(client, auth):
    from sqlalchemy import text
    from app.db.session import engine

    with engine.connect() as conn:
        period = conn.execute(text("SELECT max(period) FROM spatial.tree_censuses")).scalar()
        years = [r[0] for r in conn.execute(text("""
            SELECT DISTINCT a.planting_year FROM spatial.tree_censuses tc
            JOIN trx.area_statements a ON a.block_id = tc.block_id
            WHERE tc.period = :p AND a.planting_year IS NOT NULL ORDER BY 1
        """), {"p": period})]
    assert period and years, "Sampel tidak punya sensus sawit"
    base = {"bulan": period.month, "tahun": period.year}

    total = client.get("/api/v1/spatial/sawit/list", headers=auth, params=base).json()["total_records"]
    per_year = {}
    for year in years:
        response = client.get("/api/v1/spatial/sawit/list", headers=auth, params={**base, "tahun_tanam": year})
        assert response.status_code == 200, response.text
        per_year[year] = response.json()["total_records"]
    assert 0 < sum(per_year.values()) <= total
    assert max(per_year.values()) < total or len(years) == 1

    empty = client.get("/api/v1/spatial/sawit/list", headers=auth, params={**base, "tahun_tanam": 1901}).json()
    assert empty["total_records"] == 0


def test_history_areal_statement_groups(client, auth, sample_block):
    from sqlalchemy import text

    from app.db.session import engine

    url, est = "/api/v1/spatial/history", sample_block["estate"]
    with engine.connect() as conn:
        latest = conn.execute(text("""
            SELECT COALESCE(a.planting_year, 0) AS tt, dv.code AS afd, a.planted_area_ha AS luas
            FROM master.blocks bl
            JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
            JOIN trx.area_statements a ON a.block_id = bl.id
            WHERE upper(es.code) = upper(:est) AND a.period = (
                SELECT max(x.period) FROM trx.area_statements x JOIN master.blocks b ON b.id = x.block_id
                JOIN master.divisions d ON d.id = b.division_id JOIN master.estates e ON e.id = d.estate_id
                WHERE upper(e.code) = upper(:est))
        """), {"est": est}).mappings().all()
    assert latest
    expected_total = round(sum(float(r["luas"] or 0) for r in latest), 2)

    body = client.get(url, headers=auth, params={"table": "trx_areal_statement", "kode_est": est}).json()
    by_tt, by_afd = body["data"]["group_tahun_tanam"], body["data"]["group_divisi"]
    # snapshot periode terakhir, bukan jumlah semua periode bulanan
    assert by_tt["total_luas_tanam"] == by_afd["total_luas_tanam"] == expected_total
    assert by_tt["area_code"]
    assert [d["tahun_tanam"] for d in by_tt["details"]] == sorted({r["tt"] for r in latest})
    assert {d["division_code"] for d in by_afd["details"]} == {r["afd"] for r in latest}

    tt = by_tt["details"][0]["tahun_tanam"]
    if tt:  # tahun_tanam 0 belum bisa difilter lewat endpoint ini
        one = client.get(url, headers=auth, params={"table": "trx_areal_statement", "kode_est": est, "tahun_tanam": tt}).json()
        assert one["data"]["group_tahun_tanam"]["details"] == [by_tt["details"][0]]

    empty = client.get(url, headers=auth, params={"table": "trx_areal_statement", "kode_est": est, "tahun": 1990}).json()
    assert empty["data"]["group_divisi"] == {"area_code": None, "details": [], "total_luas_tanam": 0}


def test_history_gap_summary_follows_selected_period(client, auth, sample_block):
    """Ringkasan GAP mengikuti periode pilihan (gap_bulan/gap_tahun), bukan selalu produksi terbaru."""
    import pytest
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        periods = [r[0] for r in conn.execute(text(
            "SELECT DISTINCT period FROM trx.block_productions WHERE block_id = :b ORDER BY period"
        ), {"b": sample_block["id"]})]
    if len(periods) < 2:
        pytest.skip("Sampel butuh minimal dua periode produksi.")
    earliest, latest = periods[0], periods[-1]

    url = "/api/v1/spatial/history"
    base = {"table": "trx_produksi_tbs", "kode_est": sample_block["estate"], "kode_afd": sample_block["division"],
            "kode_blok": sample_block["code"]}

    default = client.get(url, headers=auth, params=base).json()
    assert default["ringkasan_gap_budget"]["periode"] == {"tahun": latest.year, "bulan": latest.month}

    picked = client.get(url, headers=auth, params={**base, "gap_bulan": earliest.month, "gap_tahun": earliest.year})
    assert picked.status_code == 200, picked.text
    for key in ("ringkasan_gap_budget", "ringkasan_gap_sensus"):
        assert picked.json()[key]["periode"] == {"tahun": earliest.year, "bulan": earliest.month}

    # Bulan tanpa produksi -> periode produksi terakhir sebelum bulan itu (bukan terbaru)
    after = client.get(url, headers=auth, params={**base, "gap_bulan": 12, "gap_tahun": earliest.year}).json()
    assert after["ringkasan_gap_budget"]["periode"]["tahun"] <= earliest.year

    # Sebelum produksi pertama: tidak ada ringkasan, bukan jatuh ke data terbaru
    before = client.get(url, headers=auth, params={**base, "gap_bulan": 1, "gap_tahun": 1900}).json()
    assert before["ringkasan_gap_budget"] is None and before["ringkasan_gap_sensus"] is None

    # Detail blok memakai periode yang sama
    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={
        "blok_id": sample_block["id"], "bulan": earliest.month, "tahun": earliest.year,
    }).json()
    assert detail["produksi_tbs"]["ringkasan_gap_budget"]["periode"] == {"tahun": earliest.year, "bulan": earliest.month}


def test_block_detail_without_areal_statement(client, auth, sample_block):
    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": sample_block["id"]}).json()
    assert "areal_statement" not in detail
    assert detail["informasi_blok"]["kode_blok"] == sample_block["code"]


def test_tahun_tanam_zero_means_not_planted(client, auth):
    """planting_year kosong di statement terbaru = belum ditanam, difilter dengan tahun_tanam=0."""
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT bl.id, bl.code, es.code AS estate
            FROM master.blocks bl
            JOIN master.divisions dv ON dv.id = bl.division_id JOIN master.estates es ON es.id = dv.estate_id
            JOIN LATERAL (SELECT planting_year FROM trx.area_statements a WHERE a.block_id = bl.id
                          ORDER BY a.period DESC LIMIT 1) st ON true
            WHERE st.planting_year IS NULL
        """)).mappings().all()
    if not rows:
        import pytest
        pytest.skip("Database test tidak punya blok belum ditanam.")
    est = rows[0]["estate"]
    expected = {r["code"] for r in rows if r["estate"] == est}

    blocks = client.get("/api/v1/spatial/blok", headers=auth,
                        params={"kode_est": est, "tahun_tanam": 0, "limit": 100})
    assert blocks.status_code == 200, blocks.text
    data = blocks.json()["data"]
    assert {b["kode_blok"] for b in data} == expected
    assert all(b["tahun_tanam"] is None for b in data)

    fc = client.get("/api/v1/spatial/geojson", headers=auth, params={"kode_est": est, "tahun_tanam": 0}).json()
    assert all(f["properties"]["tahun_tanam"] is None for f in fc["features"])

    years = client.get("/api/v1/spatial/history/tahun-tanam", headers=auth, params={"kode_est": est}).json()["data"]
    assert 0 in years

    areal = client.get("/api/v1/spatial/history", headers=auth,
                       params={"table": "trx_areal_statement", "kode_est": est, "tahun_tanam": 0})
    assert areal.status_code == 200, areal.text
    assert [d["tahun_tanam"] for d in areal.json()["data"]["group_tahun_tanam"]["details"]] in ([0], [])

    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": rows[0]["id"], "tahun_tanam": 0})
    assert detail.status_code == 200, detail.text
    assert detail.json()["informasi_blok"]["tahun_tanam"] is None
