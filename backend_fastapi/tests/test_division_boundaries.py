"""Batas afdeling (spatial.division_boundaries): service, hook upload blok, endpoint, dan hak akses."""
import json
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine
from app.services import block_upload_service
from app.services import division_boundary_service as svc
from app.services.block_filter import BlockFilter
from app.services.user_access import DataScope

pytestmark = pytest.mark.skipif(
    not engine.connect().execute(text("SELECT to_regclass('spatial.division_boundaries') IS NOT NULL")).scalar(),
    reason="Migrasi 021 belum dijalankan di database test.")


@pytest.fixture
def tx():
    """Sesi di dalam transaksi yang selalu di-ROLLBACK."""
    conn = engine.connect()
    trans = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conn.close()


@pytest.fixture(scope="module")
def division(sample_block) -> dict:
    with engine.connect() as conn:
        return dict(conn.execute(text("""
            SELECT bl.division_id, max(bb.period) AS period, count(DISTINCT bl.id) AS n
            FROM master.blocks bl JOIN spatial.block_boundaries bb ON bb.block_id = bl.id
            WHERE bl.id = :b GROUP BY 1
        """), {"b": sample_block["id"]}).mappings().one())


def test_refresh_menghitung_union_bersih(tx, division):
    report = svc.refresh_divisions(tx, [division["division_id"]], bump_version=False)
    assert report.gagal == 0 and report.dihitung >= 1
    row = tx.execute(text("""
        SELECT n_blok, luas_ha, ST_IsValid(geom) v, ST_IsValid(geom_display) vd, ST_NPoints(geom_display) <= ST_NPoints(geom) s,
               (SELECT count(*) FROM master.blocks WHERE division_id = :d) AS total_blok
        FROM spatial.division_boundaries WHERE division_id = :d AND period = :p AND source = 'derived'
    """), {"d": division["division_id"], "p": division["period"]}).mappings().one()
    assert row["v"] and row["vd"] and row["s"]
    assert 1 <= row["n_blok"] <= row["total_blok"] and row["luas_ha"] > 0
    # Idempoten: hitung ulang = upsert, bukan baris ganda.
    svc.refresh_divisions(tx, [division["division_id"]], bump_version=False)
    assert tx.execute(text("SELECT count(*) FROM spatial.division_boundaries WHERE division_id = :d AND period = :p"),
                      {"d": division["division_id"], "p": division["period"]}).scalar() == 1


def test_fallback_saat_topology_exception(tx, division, monkeypatch):
    real = svc._compute_sql
    monkeypatch.setattr(svc, "_compute_sql", lambda mode: "SELECT ST_GeomFromText('BROKEN')" if mode == "makevalid" else real(mode))
    report = svc.refresh_divisions(tx, [division["division_id"]], periods=[division["period"]], bump_version=False)
    assert report.gagal == 0 and report.fallback == {"buffer0": 1}


def test_semua_mode_gagal_dilaporkan_detail(tx, division, monkeypatch):
    monkeypatch.setattr(svc, "_compute_sql", lambda mode: "SELECT ST_GeomFromText('BROKEN')")
    report = svc.refresh_divisions(tx, [division["division_id"]], periods=[division["period"]], bump_version=False)
    assert report.gagal == 1
    err = report.errors[0]["error"]
    assert "makevalid:" in err and "buffer0:" in err and "grid:" in err


def test_hook_gagal_tidak_membatalkan_upload(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("GEOS TopologyException: side location conflict")
    monkeypatch.setattr(svc, "refresh_divisions", boom)
    out = svc.refresh_after_block_change(engine, block_ids=[1], period=date(2031, 1, 1))
    assert out["status"] == "gagal" and "side location conflict" in out["alasan"]
    assert "Data batas blok tetap tersimpan" in out["alasan"]


def test_upload_blok_tetap_sukses_saat_hook_gagal(client, auth, sample_block, monkeypatch):
    monkeypatch.setattr(svc, "refresh_divisions", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("uji gagal")))
    with engine.connect() as conn:
        geom = conn.execute(text("SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b "
                                 "ORDER BY period DESC LIMIT 1"), {"b": sample_block["id"]}).scalar()
    props = {"PT": sample_block["company_name"] or sample_block["company"], "EstID": sample_block["estate"],
             "Afdeling": sample_block["division"], "Blok": sample_block["code"]}
    content = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props, "geometry": json.loads(geom)}]}).encode()
    res = client.post("/api/v1/spatial/blok-geometry/upload-execute", headers=auth, params={"bulan": 2, "tahun": 2031},
                      files={"file": ("a.geojson", content, "application/geo+json")}).json()["data"]
    assert res["detail_status"]["sukses_geometri_polygon_blok"] == 1
    assert res["batas_afdeling"]["status"] == "gagal" and "uji gagal" in res["batas_afdeling"]["alasan"]
    with engine.connect() as conn:  # data blok tetap ter-commit
        assert conn.execute(text("SELECT count(*) FROM spatial.block_boundaries WHERE block_id = :b AND period = '2031-02-01'"),
                            {"b": sample_block["id"]}).scalar() == 1
    client.delete("/api/v1/spatial/cleanup-period", headers=auth, params={"bulan": 2, "tahun": 2031})


def test_upload_blok_mengisi_batas_afdeling(client, auth, sample_block):
    with engine.connect() as conn:
        geom = conn.execute(text("SELECT ST_AsGeoJSON(geom) FROM spatial.block_boundaries WHERE block_id = :b "
                                 "ORDER BY period DESC LIMIT 1"), {"b": sample_block["id"]}).scalar()
    props = {"PT": sample_block["company_name"] or sample_block["company"], "EstID": sample_block["estate"],
             "Afdeling": sample_block["division"], "Blok": sample_block["code"]}
    content = json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props, "geometry": json.loads(geom)}]}).encode()
    res = client.post("/api/v1/spatial/blok-geometry/upload-execute", headers=auth, params={"bulan": 3, "tahun": 2031},
                      files={"file": ("a.geojson", content, "application/geo+json")}).json()["data"]
    assert res["batas_afdeling"]["status"] == "sukses", res["batas_afdeling"]
    fc = client.get("/api/v1/spatial/afdeling/geojson", headers=auth,
                    params={"kode_est": sample_block["estate"], "kode_afd": sample_block["division"],
                            "bulan": 3, "tahun": 2031}).json()
    assert len(fc["features"]) == 1
    p = fc["features"][0]["properties"]
    assert p["kode_afd"] == sample_block["division"] and p["periode_batas"] == "3-2031" and p["n_blok"] >= 1
    assert p["estate_short_name"] and p["luas_ha"] > 0
    # Hapus periode -> baris derived periode itu ikut dibuang (tidak basi).
    out = client.delete("/api/v1/spatial/cleanup-period", headers=auth, params={"bulan": 3, "tahun": 2031}).json()
    assert out["batas_afdeling"]["baris_basi_dihapus"] >= 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM spatial.division_boundaries WHERE period = '2031-03-01'")).scalar() == 0


def test_endpoint_validasi(client, auth):
    r = client.get("/api/v1/spatial/afdeling/geojson", headers=auth, params={"bulan": 1})
    assert r.status_code == 400 and "tahun" in r.text


def test_endpoint_ikut_scope_user(tx, division):
    svc.refresh_divisions(tx, [division["division_id"]], bump_version=False)
    flt = BlockFilter()
    sql, p = DataScope(divisions=[division["division_id"]]).block_clause()
    flt.extra_where.append(sql); flt.extra_params.update(p)
    fc = svc.afdeling_geojson(tx, flt, None, None)
    assert {f["properties"]["division_id"] for f in fc["features"]} == {str(division["division_id"])}
    flt = BlockFilter()
    sql, p = DataScope().block_clause()  # tanpa grant -> kosong
    flt.extra_where.append(sql); flt.extra_params.update(p)
    assert svc.afdeling_geojson(tx, flt, None, None)["features"] == []


def test_semantik_periode_terbaru_sd_periode(tx, division):
    svc.refresh_divisions(tx, [division["division_id"]], bump_version=False)
    flt = BlockFilter(kode_afd=str(division["division_id"]))
    before = svc.afdeling_geojson(tx, flt, division["period"].month, division["period"].year - 50)
    assert before["features"] == []  # belum ada batas sebelum upload pertama
    later = svc.afdeling_geojson(tx, flt, 12, 2100)
    assert later["features"][0]["properties"]["periode_batas"]


def test_backfill_dry_run_tidak_menyimpan(capsys):
    from scripts import backfill_division_boundaries as bf
    with engine.connect() as conn:
        before = conn.execute(text("SELECT count(*) FROM spatial.division_boundaries")).scalar()
        est = conn.execute(text("SELECT es.code FROM master.estates es JOIN master.divisions dv ON dv.estate_id = es.id "
                                "JOIN master.blocks bl ON bl.division_id = dv.id JOIN spatial.block_boundaries bb "
                                "ON bb.block_id = bl.id LIMIT 1")).scalar()
    assert bf.main(["--estate", est, "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"].startswith("dry-run") and out["afdeling_periode_dihitung"] >= 1
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM spatial.division_boundaries")).scalar() == before
