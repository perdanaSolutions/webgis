"""GET /api/v1/dashboard/laporan: empat tema, dipotong hak transaksi dan wilayah."""
import uuid

from sqlalchemy import text

from app.core.security import create_access_token
from app.db.session import engine


def test_dashboard_report_requires_login(client):
    assert client.get("/api/v1/dashboard/laporan").status_code == 401


def test_superadmin_report_covers_every_theme(client, auth):
    response = client.get("/api/v1/dashboard/laporan", headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cakupan"] == "semua"
    for key in ("produksi_tbs", "yield", "status_tanam", "rotasi"):
        assert body[key]["akses"] is True
        assert body[key]["tema"] == key
    if body["produksi_tbs"]["periode"]:
        row = body["produksi_tbs"]["periode"][-1]
        assert {"tahun", "bulan", "ton"} <= row.keys()
        assert body["produksi_tbs"]["total_ton"] == row["ton"]
    if body["status_tanam"]["per_status"]:
        assert abs(sum(item["persen"] for item in body["status_tanam"]["per_status"]) - 100) < 0.2


def test_limited_role_only_receives_granted_themes(client, auth, sample_block):
    suffix = uuid.uuid4().hex[:8]
    role = client.post("/api/v1/roles/", headers=auth, json={
        "nama": f"Laporan {suffix}",
        "deskripsi": "hanya produksi",
        "akses_transaksi": ["trx.block_productions"],
    })
    assert role.status_code == 201, role.text
    role = role.json()
    user = None
    try:
        with engine.begin() as conn:
            estate_id = conn.execute(
                text("SELECT id FROM master.estates WHERE upper(code) = upper(:code)"),
                {"code": sample_block["estate"]},
            ).scalar()
            assert estate_id is not None
            conn.execute(
                text("INSERT INTO auth.role_data_scopes (role_id, estate_id) VALUES (:role_id, :estate_id)"),
                {"role_id": role["id"], "estate_id": estate_id},
            )
        created = client.post("/api/v1/users/", headers=auth, json={
            "username": f"laporan-{suffix}",
            "email": f"laporan-{suffix}@example.com",
            "nama_lengkap": "Laporan Terbatas",
            "password": "RahasiaBanget123",
            "role_ids": [role["id"]],
        })
        assert created.status_code == 201, created.text
        user = created.json()

        limited = client.get(
            "/api/v1/dashboard/laporan",
            headers={"Authorization": f"Bearer {create_access_token(user['id'])}"},
        )
        assert limited.status_code == 200, limited.text
        body = limited.json()
        assert body["cakupan"] == "terbatas"
        assert body["produksi_tbs"]["akses"] is True
        assert body["yield"]["akses"] is True
        assert body["status_tanam"] == {"tema": "status_tanam", "akses": False}
        assert body["rotasi"] == {"tema": "rotasi", "akses": False}

        everyone = client.get("/api/v1/dashboard/laporan", headers=auth).json()
        limited_ton = body["produksi_tbs"]["total_ton"]
        all_ton = everyone["produksi_tbs"]["total_ton"]
        if limited_ton is not None and all_ton is not None:
            assert limited_ton <= all_ton + 0.01
    finally:
        with engine.begin() as conn:
            if user is not None:
                conn.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": user["id"]})
            conn.execute(text("DELETE FROM auth.roles WHERE id = :id"), {"id": role["id"]})
