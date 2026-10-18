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
    # periode batas (poligon) dipisah dari periode transaksi; bulan/tahun tetap = periode batas
    assert props["periode_batas"] == f'{props["bulan"]}-{props["tahun"]}'

    # FE mengirim kode_blok = kode blok (bukan id) juga harus bisa
    by_code = client.get("/api/v1/spatial/geojson", headers=auth,
                         params={"kode_est": sample_block["estate"], "kode_afd": sample_block["division"],
                                 "kode_blok": sample_block["code"]}).json()
    assert len(by_code["features"]) == 1


def _production_period(sample_block):
    """Periode terbaru sampel yang punya produksi dan areal statement sekaligus."""
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT p.period
            FROM trx.block_productions p
            JOIN trx.area_statements a ON a.block_id = p.block_id AND a.period = p.period
            WHERE p.block_id = :bid
            ORDER BY p.period DESC
            LIMIT 1
        """), {"bid": sample_block["id"]}).first()
    assert row is not None, "Sampel tidak punya produksi dan areal statement di periode yang sama."
    return row[0]


def _block_props(client, auth, sample_block, **params):
    response = client.get("/api/v1/spatial/geojson", headers=auth, params={
        "kode_est": sample_block["estate"], "kode_blok": str(sample_block["id"]), **params})
    assert response.status_code == 200, response.text
    return response.json()["features"][0]["properties"]


def test_blocks_geojson_month_matches_block_detail(client, auth, sample_block):
    """year_to_date=false + bulan: transaksi bulan itu saja; rumus yield/gap = detail blok."""
    period = _production_period(sample_block)
    props = _block_props(client, auth, sample_block, bulan=period.month, tahun=period.year)
    label = f"{period.month}-{period.year}"
    prod = props["produksi_tbs"]
    assert props["areal_statement"]["periode"] == label
    assert (prod["periode"], prod["periode_awal"], prod["periode_akhir"], prod["year_to_date"]) == (
        label, label, label, False)

    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={
        "blok_id": sample_block["id"], "bulan": period.month, "tahun": period.year,
    }).json()["informasi_blok"]
    assert props["areal_statement"]["luas_tanam"] == detail["luas_tanam"]
    assert prod["luas_tanam"] == detail["luas_tanam"]
    assert prod["tbs_aktual"] == detail["tbs"]["aktual"]
    assert prod["y_aktual"] == detail["yield"]["aktual"]
    assert prod["y_budget"] == detail["yield"]["budget"]
    assert prod["y_sensus"] == detail["yield"]["sensus"]
    assert prod["gap_budget_pct"] == detail["gap_act_bgt"]["value"]
    assert prod["gap_sensus_pct"] == detail["gap_act_sns"]["value"]
    assert (prod["kategori_budget"] or "") == detail["gap_act_bgt"]["kategori"]
    assert (prod["kategori_sensus"] or "") == detail["gap_act_sns"]["kategori"]


def test_blocks_geojson_year_to_date_sums_january_to_month(client, auth, sample_block):
    from sqlalchemy import text

    from app.db.session import engine

    period = _production_period(sample_block)
    with engine.connect() as conn:
        expected = conn.execute(text("""
            SELECT round(SUM(ffb_actual_kg)::numeric, 2) FROM trx.block_productions
            WHERE block_id = :b AND period BETWEEN make_date(:y, 1, 1) AND :p
        """), {"b": sample_block["id"], "y": period.year, "p": period}).scalar()
    prod = _block_props(client, auth, sample_block, bulan=period.month, tahun=period.year,
                        year_to_date="true")["produksi_tbs"]
    assert (prod["periode_awal"], prod["periode_akhir"], prod["year_to_date"]) == (
        f"1-{period.year}", f"{period.month}-{period.year}", True)
    assert prod["tbs_aktual"] == float(expected)


def test_blocks_geojson_without_month(client, auth, sample_block):
    """Tanpa bulan: false = bulan terakhir yang diupload di tahun itu; true = Januari s/d bulan berjalan."""
    from datetime import date

    from sqlalchemy import text

    from app.db.session import engine

    period = _production_period(sample_block)
    with engine.connect() as conn:
        latest = conn.execute(text("""
            SELECT max(period) FROM trx.block_productions WHERE block_id = :b AND extract(year FROM period) = :y
        """), {"b": sample_block["id"], "y": period.year}).scalar()
    prod = _block_props(client, auth, sample_block, tahun=period.year)["produksi_tbs"]
    assert prod["periode_awal"] == prod["periode_akhir"] == f"{latest.month}-{latest.year}"

    ytd = _block_props(client, auth, sample_block, tahun=period.year, year_to_date="true").get("produksi_tbs")
    if ytd:
        today = date.today()
        end_month = today.month if period.year == today.year else 12
        assert (ytd["periode_awal"], ytd["periode_akhir"]) == (f"1-{period.year}", f"{end_month}-{period.year}")


def test_blocks_geojson_comparison(client, auth, sample_block):
    period = _production_period(sample_block)
    same = {"bulan": period.month, "tahun": period.year}
    props = _block_props(client, auth, sample_block, **same,
                         bulan_comparison=period.month, tahun_comparison=period.year)
    # Pembanding = periode yang sama -> isinya identik dengan produksi_tbs.
    assert props["produksi_tbs_comparison"] == props["produksi_tbs"]

    without = _block_props(client, auth, sample_block, **same)
    assert "produksi_tbs_comparison" not in without

    response = client.get("/api/v1/spatial/geojson", headers=auth, params={**same, "bulan_comparison": 1})
    assert response.status_code == 400


def test_blocks_geojson_hides_unauthorized_transaction_keys(client, auth, sample_block, monkeypatch):
    from app.services import user_access
    monkeypatch.setattr(user_access, "hidden_feature_keys",
                        lambda db, user: ("areal_statement", "produksi_tbs", "produksi_tbs_comparison", "rotasi_terakhir"))
    fc = client.get("/api/v1/spatial/geojson", headers=auth,
                    params={"kode_est": sample_block["estate"], "kode_blok": str(sample_block["id"]),
                            "bulan_comparison": 1, "tahun_comparison": 2026}).json()
    props = fc["features"][0]["properties"]
    assert props["blok_id"] == sample_block["id"]
    assert not {"areal_statement", "produksi_tbs", "produksi_tbs_comparison", "rotasi_terakhir"} & props.keys()


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
    assert empty["periode"] == {"bulan": 1, "tahun": 2099, "label_periode": "Tahun 2099",
                                "year_to_date": False, "produksi_awal": "1-2099", "produksi_akhir": "1-2099"}
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

    # Periode sebelum transaksi pertama -> periode persis itu, tanpa data (bukan data terbaru).
    before = client.get("/api/v1/spatial/blok/detail", headers=auth,
                        params={"blok_id": sample_block["id"], "bulan": 1, "tahun": 1900})
    assert before.status_code == 200, before.text
    body = before.json()
    assert body["mode"] == "PERIODE_BULAN_TAHUN"
    assert body["periode"]["tahun"] == 1900
    assert body["informasi_blok"]["tbs"]["aktual"] == 0

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

    years = client.get("/api/v1/spatial/history/tahun-tanam", headers=auth, params={"kode_est": est}).json()["data"]
    assert 0 in years

    areal = client.get("/api/v1/spatial/history", headers=auth,
                       params={"table": "trx_areal_statement", "kode_est": est, "tahun_tanam": 0})
    assert areal.status_code == 200, areal.text
    assert [d["tahun_tanam"] for d in areal.json()["data"]["group_tahun_tanam"]["details"]] in ([0], [])

    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": rows[0]["id"], "tahun_tanam": 0})
    assert detail.status_code == 200, detail.text
    assert detail.json()["informasi_blok"]["tahun_tanam"] is None


def test_geojson_without_params_uses_latest_uploaded_month(client, auth, sample_block):
    """Tanpa bulan/tahun: produksi = bulan terakhir yang sudah diupload (blok yang difilter)."""
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        latest = conn.execute(text("SELECT max(period) FROM trx.block_productions WHERE block_id = :b"),
                              {"b": sample_block["id"]}).scalar()
    props = _block_props(client, auth, sample_block)
    assert props["periode_batas"] == f'{props["bulan"]}-{props["tahun"]}'
    if latest is None:
        assert "produksi_tbs" not in props
        return
    assert props["produksi_tbs"]["periode"] == f"{latest.month}-{latest.year}"


def test_latest_period_defaults_to_last_uploaded_production(client, auth, sample_block):
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        latest = {
            key: conn.execute(text(f"SELECT max(period) FROM {table} WHERE block_id IN "
                                   "(SELECT bl.id FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id "
                                   "JOIN master.estates es ON es.id = dv.estate_id WHERE es.code = :e)"),
                              {"e": sample_block["estate"]}).scalar()
            for key, table in (("produksi_tbs", "trx.block_productions"), ("areal_statement", "trx.area_statements"),
                               ("batas_blok", "spatial.block_boundaries"))
        }
    response = client.get("/api/v1/spatial/periode-terakhir", headers=auth, params={"kode_est": sample_block["estate"]})
    assert response.status_code == 200, response.text
    body = response.json()
    expected_source = next(key for key in ("produksi_tbs", "areal_statement", "batas_blok") if latest[key])
    expected = latest[expected_source]
    assert body["sumber"] == expected_source
    assert (body["bulan"], body["tahun"], body["periode"]) == (expected.month, expected.year,
                                                                f"{expected.month}-{expected.year}")
    for key, period in latest.items():
        assert body["per_data"][key] == ({"bulan": period.month, "tahun": period.year,
                                          "periode": f"{period.month}-{period.year}"} if period else None)

    empty = client.get("/api/v1/spatial/periode-terakhir", headers=auth, params={"kode_est": "TIDAK_ADA"}).json()
    assert empty["bulan"] is None and empty["sumber"] is None
    assert all(value is None for value in empty["per_data"].values())


def test_geojson_without_production_keeps_areal_statement_and_rotation_bound(client, auth, sample_block):
    """Tahun tanpa produksi: areal_statement tetap dari statement tahun itu; rotasi tidak melewati tahun itu."""
    from sqlalchemy import text

    from app.db.session import engine

    with engine.connect() as conn:
        year = conn.execute(text("""
            SELECT extract(year FROM a.period)::int FROM trx.area_statements a
            WHERE a.block_id = :b AND NOT EXISTS (
                SELECT 1 FROM trx.block_productions p JOIN master.blocks bl ON bl.id = p.block_id
                JOIN master.divisions dv ON dv.id = bl.division_id
                JOIN master.estates es ON es.id = dv.estate_id
                WHERE es.code = :e AND extract(year FROM p.period) = extract(year FROM a.period))
              AND EXISTS (SELECT 1 FROM spatial.block_boundaries bb WHERE bb.block_id = :b
                          AND bb.period <= make_date(extract(year FROM a.period)::int, 12, 1))
            ORDER BY a.period DESC LIMIT 1
        """), {"b": sample_block["id"], "e": sample_block["estate"]}).scalar()
        if year is None:
            import pytest
            pytest.skip("Sampel tidak punya tahun dengan areal statement tanpa produksi.")
        latest = conn.execute(text("""
            SELECT max(period) FROM trx.area_statements WHERE block_id = :b AND extract(year FROM period) = :y
        """), {"b": sample_block["id"], "y": year}).scalar()
    props = _block_props(client, auth, sample_block, tahun=year)
    assert "produksi_tbs" not in props
    assert props["areal_statement"]["periode"] == f"{latest.month}-{latest.year}"
    if "rotasi_terakhir" in props:
        assert props["rotasi_terakhir"]["tanggal"] <= f"{year}-12-01"


def test_latest_period_hides_transaction_tables_without_access(client, auth, sample_block, monkeypatch):
    from app.services import user_access

    monkeypatch.setattr(user_access, "transaction_keys", lambda db, user: {"trx.area_statements"})
    body = client.get("/api/v1/spatial/periode-terakhir", headers=auth,
                      params={"kode_est": sample_block["estate"]}).json()
    assert set(body["per_data"]) == {"areal_statement", "batas_blok"}
    assert body["sumber"] in (None, "areal_statement", "batas_blok")


def test_group_estate_count_follows_access(client, auth, sample_block, monkeypatch):
    from sqlalchemy import text

    from app.db.session import engine
    from app.services import user_access

    with engine.connect() as conn:
        estate_id = conn.execute(text("SELECT id FROM master.estates WHERE code = :e"),
                                 {"e": sample_block["estate"]}).scalar()
    monkeypatch.setattr(user_access, "hierarchy_clause",
                        lambda db, user, level: ("es.id = :only_estate", {"only_estate": estate_id}))
    groups = client.get("/api/v1/spatial/grup", headers=auth).json()["data"]
    assert len(groups) == 1 and groups[0]["jumlah_estate"] == 1


def test_block_detail_year_to_date_matches_geojson(client, auth, sample_block):
    """Detail blok dengan year_to_date = angka produksi_tbs GeoJSON dengan year_to_date (Januari s/d bulan)."""
    period = _production_period(sample_block)
    params = {"bulan": period.month, "tahun": period.year, "year_to_date": "true"}
    detail = client.get("/api/v1/spatial/blok/detail", headers=auth, params={"blok_id": sample_block["id"], **params}).json()
    prod = _block_props(client, auth, sample_block, **params)["produksi_tbs"]
    info, periode = detail["informasi_blok"], detail["periode"]
    assert (periode["year_to_date"], periode["produksi_awal"], periode["produksi_akhir"]) == (
        True, f"1-{period.year}", f"{period.month}-{period.year}")
    assert info["tbs"]["aktual"] == prod["tbs_aktual"]
    assert info["yield"]["aktual"] == prod["y_aktual"]
    assert (info["gap_act_bgt"]["kategori"] or None) == prod["kategori_budget"]

    month = client.get("/api/v1/spatial/blok/detail", headers=auth, params={
        "blok_id": sample_block["id"], "bulan": period.month, "tahun": period.year}).json()
    assert month["periode"]["produksi_awal"] == month["periode"]["produksi_akhir"] == f"{period.month}-{period.year}"


def test_year_to_date_bjr_is_total_tbs_over_total_bunches(client, auth, sample_block):
    """BJR beberapa bulan = total TBS / total janjang; satu bulan atau tanpa janjang = BJR hasil upload."""
    from sqlalchemy import text

    from app.db.session import engine

    rows = [("2098-01-01", 1000, 100, 99), ("2098-02-01", 3000, 100, 1)]
    with engine.begin() as conn:
        for period, tbs, jjg, bjr in rows:
            conn.execute(text("""
                INSERT INTO trx.block_productions (block_id, period, ffb_actual_kg, bunches_actual, bjr_actual,
                                                   ffb_census_kg, bjr_census)
                VALUES (:b, :p, :t, :j, :bjr, :t, 5)
            """), {"b": sample_block["id"], "p": period, "t": tbs, "j": jjg, "bjr": bjr})
    try:
        params = {"bulan": 2, "tahun": 2098}
        ytd = _block_props(client, auth, sample_block, **params, year_to_date="true")["produksi_tbs"]
        month = _block_props(client, auth, sample_block, **params)["produksi_tbs"]
        assert (ytd["tbs_aktual"], ytd["janjang_aktual"], ytd["bjr_aktual"]) == (4000, 200, 20)
        assert month["bjr_aktual"] == 1  # satu bulan: nilai upload apa adanya

        detail = client.get("/api/v1/spatial/blok/detail", headers=auth,
                            params={"blok_id": sample_block["id"], **params, "year_to_date": "true"}).json()
        bjr = detail["informasi_blok"]["bjr"]
        assert bjr["aktual"] == 20
        assert bjr["sensus"] == 5  # janjang sensus kosong: rata-rata BJR upload
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM trx.block_productions WHERE block_id = :b AND period >= '2098-01-01'"),
                         {"b": sample_block["id"]})


def test_area_statement_summary_matches_history_and_is_consistent(client, auth, sample_block):
    params = {"kode_est": sample_block["estate"]}
    summary = client.get("/api/v1/spatial/areal-statement/ringkasan", headers=auth, params=params)
    assert summary.status_code == 200, summary.text
    summary = summary.json()
    history = client.get("/api/v1/spatial/history", headers=auth,
                         params={"table": "trx_areal_statement", **params}).json()["data"]
    tanam = summary["tanam"]
    assert tanam["total_luas_tanam"] == history["group_tahun_tanam"]["total_luas_tanam"]
    assert [(r["tahun_tanam"], r["luas_tanam"]) for r in tanam["per_tahun_tanam"]] == [
        (r["tahun_tanam"], r["luas_tanam"]) for r in history["group_tahun_tanam"]["details"]]
    assert round(sum(r["luas_tanam"] for r in tanam["per_status"]), 2) == tanam["total_luas_tanam"]
    assert sum(r["jumlah_blok"] for r in tanam["per_status"]) == tanam["jumlah_blok"]

    populasi = summary["populasi"]
    assert [c["kode"] for c in populasi["kelas"]] == ["ATAS_136", "ANTARA_130_135", "BAWAH_130"]
    classified = sum(c["luas_tanam"] for c in populasi["kelas"]) + populasi["tanpa_sph"]["luas_tanam"]
    assert abs(classified - tanam["total_luas_tanam"]) < 0.05
    assert summary["tidak_tertanam_dalam_blok"]["luas"] >= 0 and summary["non_tanam"] is None

    old = client.get("/api/v1/spatial/areal-statement/ringkasan", headers=auth,
                     params={**params, "bulan": 1, "tahun": 1900}).json()
    assert old["periode"] is None and old["tanam"]["jumlah_blok"] == 0 and old["tanam"]["per_status"] == []


def test_population_class_boundaries():
    from app.services.area_statement_summary_service import _population_class

    assert [_population_class(v) for v in (140, 136, 135.9, 130, 129.99, None)] == [
        "ATAS_136", "ATAS_136", "ANTARA_130_135", "ANTARA_130_135", "BAWAH_130", None]
