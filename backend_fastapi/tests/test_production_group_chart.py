"""GET /api/v1/spatial/produksi/grafik-grup: Produksi TBS per Grup, Area, Estate (kartu Produksi TBS)."""
from datetime import date

import pytest
from sqlalchemy import text

from app.db.session import engine
from app.services.map_service import TrxWindow
from app.services.production_group_service import _pct, _previous_year

URL = "/api/v1/spatial/produksi/grafik-grup"
LEVELS = ("by_group", "by_area", "by_estate")


def _latest_period():
    with engine.connect() as conn:
        return conn.execute(text("SELECT max(period) FROM trx.block_productions")).scalar()


def test_requires_login(client):
    assert client.get(URL).status_code == 401


def test_pct_and_previous_year():
    assert _pct(90, 100) == -10.0
    assert _pct(5, 0) is None
    assert _pct(100, 100) == 0.0
    window = TrxWindow.of(date(2026, 10, 1), True)
    assert _previous_year(window) == (date(2025, 1, 1), date(2025, 10, 1))


def test_ytd_levels_add_up_to_total(client, auth):
    latest = _latest_period()
    if latest is None:
        pytest.skip("DB test belum punya produksi")
    response = client.get(URL, headers=auth, params={
        "bulan": latest.month, "tahun": latest.year, "year_to_date": "true",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["periode"] == {
        "periode_awal": f"1-{latest.year}", "periode_akhir": f"{latest.month}-{latest.year}", "year_to_date": True,
        "tahun_lalu_awal": f"1-{latest.year - 1}", "tahun_lalu_akhir": f"{latest.month}-{latest.year - 1}",
    }
    data = body["group_produksi_ton"]
    total = data["total"]
    assert total is not None
    for level in LEVELS:
        items = data[level]
        assert items, level
        # Tiap level adalah pembagian blok yang sama, jadi jumlahnya sama dengan total.
        assert abs(sum(item["aktual_ton"] for item in items) - total["aktual_ton"]) < 1
        assert abs(sum(item["budget_ton"] for item in items) - total["budget_ton"]) < 1
        values = [item["aktual_ton"] for item in items]
        assert values == sorted(values, reverse=True)
    assert total["nama"] == " + ".join(item["nama"] for item in data["by_group"])
    if total["budget_ton"]:
        expected = round((total["aktual_ton"] - total["budget_ton"]) / total["budget_ton"] * 100, 2)
        assert abs(total["var_budget_pct"] - expected) < 0.02
    if total["luas_tanam"]:
        assert abs(total["aktual_ton_ha"] - total["aktual_ton"] / total["luas_tanam"]) < 0.01


def test_area_filter_narrows_every_level(client, auth):
    latest = _latest_period()
    if latest is None:
        pytest.skip("DB test belum punya produksi")
    params = {"bulan": latest.month, "tahun": latest.year}
    everyone = client.get(URL, headers=auth, params=params).json()["group_produksi_ton"]
    area = everyone["by_area"][0]
    narrowed = client.get(URL, headers=auth, params={**params, "area_id": area["kode"]})
    assert narrowed.status_code == 200, narrowed.text
    data = narrowed.json()["group_produksi_ton"]
    assert [item["kode"] for item in data["by_area"]] == [area["kode"]]
    assert abs(data["total"]["aktual_ton"] - area["aktual_ton"]) < 0.01
    all_estates = {item["kode"] for item in everyone["by_estate"]}
    assert {item["kode"] for item in data["by_estate"]} <= all_estates
    assert len(data["by_group"]) == 1


def test_empty_scope_returns_empty_lists(client, auth):
    response = client.get(URL, headers=auth, params={"kode_est": "TIDAK-ADA-ESTATE"})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "periode": None,
        "group_produksi_ton": {"total": None, "by_group": [], "by_area": [], "by_estate": []},
    }
