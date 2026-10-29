"""rekap_tahunan pada GET /spatial/history?table=trx_produksi_tbs."""
import pytest
from sqlalchemy import text

from app.db.session import engine
from app.services.history_service import yearly_recap_rows


def _m(tahun, bulan, area, ffb, bgt, sns, bunches, trees):
    return {"tahun": tahun, "bulan": bulan, "area": area, "ffb": ffb, "ffb_bgt": bgt, "ffb_sns": sns,
            "bunches": bunches, "trees": trees}


def test_rumus_rekap_tahunan():
    rows = yearly_recap_rows([
        _m(2025, 2, 100, 20_000, 25_000, 10_000, 2_000, 1_000),
        _m(2025, 1, 100, 10_000, 10_000, 10_000, 1_000, 1_000),
        _m(2024, 12, 50, 5_000, None, None, 0, 0),
    ])
    assert [r["tahun"] for r in rows] == [2024, 2025]  # naik
    y = rows[1]
    assert y["jumlah_periode"] == 2 and y["luas"] == 100.0
    assert y["ton"] == 30.0 and y["ton_ha"] == 0.3
    assert y["ton_ha_budget"] == 0.35 and y["ton_ha_sensus"] == 0.2
    assert y["gap_budget_pct"] == round((0.3 - 0.35) / 0.35 * 100, 2) and y["kategori_budget"] == "GAP I"
    assert y["gap_sensus_pct"] == 50.0 and y["kategori_sensus"] == "OPTIMUM"
    assert y["bjr"] == 10.0  # 30.000 kg / 3.000 janjang
    assert y["jjg_ppk"] == 3.0 and y["kg_ppk"] == 30
    assert "periode" not in y and "bulan" not in y
    z = rows[0]  # tanpa target/pokok -> None, bukan error
    assert z["ton_ha_budget"] is None and z["kategori_budget"] is None and z["jjg_ppk"] is None and z["bjr"] == 0.0


def test_luas_pakai_bulan_terakhir_yang_ada_luas():
    rows = yearly_recap_rows([_m(2025, 1, 80, 1000, None, None, 10, 10), _m(2025, 2, None, 1000, None, None, 10, 10)])
    assert rows[0]["luas"] == 80.0


@pytest.fixture
def seeded(sample_block):
    """Produksi sintetis untuk blok sampel (2025 tanpa areal statement, 2026 Jan-Mar) di transaksi yang di-ROLLBACK."""
    from sqlalchemy.orm import Session

    from app.api import deps
    from app.main import app

    conn = engine.connect()
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    for year, months in ((2025, (11, 12)), (2026, (1, 2, 3))):
        for m in months:
            s.execute(text("""
                INSERT INTO trx.block_productions (block_id, period, ffb_actual_kg, ffb_budget_kg, ffb_census_kg, bunches_actual)
                VALUES (:b, make_date(:y, :m, 1), :f, :bg, :sn, :bu) ON CONFLICT (block_id, period) DO NOTHING
            """), {"b": sample_block["id"], "y": year, "m": m, "f": 10000 * m, "bg": 12000 * m, "sn": 9000 * m, "bu": 800 * m})

    def override():
        yield s
    app.dependency_overrides[deps.get_db] = override
    try:
        yield sample_block
    finally:
        app.dependency_overrides.pop(deps.get_db, None)
        s.close()
        trans.rollback()
        conn.close()


def test_endpoint_rekap_semua_tahun_dan_urutan_key(client, auth, seeded):
    params = {"table": "trx_produksi_tbs", "blok_id": seeded["id"], "tahun": 2026, "bulan": 1}
    body = client.get("/api/v1/spatial/history", headers=auth, params=params).json()
    keys = list(body)
    assert keys.index("rekap_tahunan") == keys.index("total_periode") - 1
    years = [r["tahun"] for r in body["rekap_tahunan"]]
    assert {2025, 2026} <= set(years) and years == sorted(years)  # filter tahun/bulan diabaikan
    monthly = client.get("/api/v1/spatial/history", headers=auth,
                         params={"table": "trx_produksi_tbs", "blok_id": seeded["id"], "tahun": 2026}).json()
    rec = next(r for r in body["rekap_tahunan"] if r["tahun"] == 2026)
    assert rec["jumlah_periode"] == monthly["total_periode"]
    assert rec["ton"] == pytest.approx(sum(r["ton"] for r in monthly["data_histori"]), abs=0.05)
    assert rec["luas"] == monthly["data_histori"][-1]["luas"]
    assert rec["bjr"] == pytest.approx(12.5, abs=0.01)  # 60.000 kg / 4.800 janjang


def test_endpoint_rekap_ikut_filter_wilayah(client, auth, seeded):
    sample_block = seeded
    body = client.get("/api/v1/spatial/history", headers=auth,
                      params={"table": "trx_produksi_tbs", "blok_id": sample_block["id"]}).json()
    assert [r["tahun"] for r in body["rekap_tahunan"]] == [2025, 2026]
    other = client.get("/api/v1/spatial/history", headers=auth,
                       params={"table": "trx_produksi_tbs", "kode_afd": "AFD-TIDAK-ADA"}).json()
    assert other["rekap_tahunan"] == []


def test_rekap_ikut_scope_hak_akses():
    from app.db.session import SessionLocal
    from app.services.block_filter import BlockFilter
    from app.services.history_service import yearly_recap
    from app.services.user_access import DataScope

    flt = BlockFilter()
    sql, p = DataScope().block_clause()  # tanpa grant -> tidak ada blok
    flt.extra_where.append(sql); flt.extra_params.update(p)
    blocks_sql, params = flt.block_ids_subquery()
    with SessionLocal() as db:
        assert yearly_recap(db, blocks_sql, params) == []
