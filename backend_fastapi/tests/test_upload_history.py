import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import engine
from app.services.upload.batch import finish_batch, start_batch

URL = "/api/v1/upload-history/"


def _batch(user_id, filename: str, status: str, layer: str = "jalan") -> str:
    with Session(engine) as db:
        batch_id = start_batch(db, source_type="GEOJSON_UPLOAD", target_table="spatial.roads", source_name=filename,
                               user_id=user_id, period=date(2026, 3, 1), metadata={"layer": layer})
        finish_batch(db, batch_id, status, 7, "gagal" if status == "FAILED" else None, {"detail_statistik": {"ok": 7}})
    return str(batch_id)


def _cleanup(*batch_ids):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM audit.upload_batches WHERE id = ANY(CAST(:ids AS uuid[]))"),
                     {"ids": list(batch_ids)})


def test_upload_history_list_and_detail(client, auth, superadmin_id):
    suffix = uuid.uuid4().hex[:8]
    ok = _batch(uuid.UUID(superadmin_id), f"jalan_{suffix}.geojson", "SUCCESS")
    failed = _batch(uuid.UUID(superadmin_id), f"jalan_{suffix}_rusak.geojson", "FAILED")
    try:
        listing = client.get(URL, headers=auth, params={"search": suffix})
        assert listing.status_code == 200, listing.text
        rows = listing.json()["data"]
        assert [row["id"] for row in rows] == [failed, ok]  # terbaru di atas
        row = rows[1]
        assert row["nama_file"] == f"jalan_{suffix}.geojson"
        assert row["diupload_oleh"]["id"] == superadmin_id
        assert row["layer"] == "jalan"
        assert row["jumlah_data"] == 7
        assert row["periode"] == "2026-03-01"
        assert row["durasi_detik"] is not None
        assert "metadata" not in row

        params = {"search": suffix, "status": "failed", "layer": "jalan", "bulan": 3, "tahun": 2026,
                  "uploaded_by": superadmin_id, "tanggal_dari": date.today().isoformat()}
        assert [r["id"] for r in client.get(URL, headers=auth, params=params).json()["data"]] == [failed]
        assert client.get(URL, headers=auth, params={"search": suffix, "layer": "sawit"}).json()["data"] == []
        assert client.get(URL, headers=auth, params={"search": suffix, "bulan": 4}).json()["data"] == []

        detail = client.get(f"{URL}{ok}", headers=auth)
        assert detail.status_code == 200, detail.text
        assert detail.json()["metadata"]["detail_statistik"] == {"ok": 7}
        assert client.get(f"{URL}{uuid.uuid4()}", headers=auth).status_code == 404
    finally:
        _cleanup(ok, failed)


def test_upload_history_validation(client, auth):
    assert client.get(URL, headers=auth, params={"status": "ngawur"}).status_code == 400
    assert client.get(URL, headers=auth, params={"tanggal_dari": "2026-05-02", "tanggal_sampai": "2026-05-01"}).status_code == 400
    assert client.get(URL).status_code == 401


def test_upload_history_own_only_for_non_manager(client, auth, superadmin_id):
    suffix = uuid.uuid4().hex[:6]
    role = client.post("/api/v1/roles/", headers=auth, json={"nama": f"viewer{suffix}"}).json()
    user = client.post("/api/v1/users/", headers=auth, json={
        "username": f"viewer{suffix}", "email": f"viewer{suffix}@example.com", "nama_lengkap": "Viewer",
        "password": "Passw0rd!123", "role_ids": [role["id"]]}).json()
    viewer = {"Authorization": f"Bearer {create_access_token(user['id'])}"}

    mine = _batch(uuid.UUID(user["id"]), f"milik_{suffix}.geojson", "SUCCESS")
    others = _batch(uuid.UUID(superadmin_id), f"admin_{suffix}.geojson", "SUCCESS")
    try:
        # filter uploaded_by diabaikan untuk non-pengelola: tetap hanya miliknya
        params = {"search": suffix, "uploaded_by": superadmin_id}
        assert [r["id"] for r in client.get(URL, headers=viewer, params=params).json()["data"]] == [mine]
        assert client.get(f"{URL}{mine}", headers=viewer).status_code == 200
        assert client.get(f"{URL}{others}", headers=viewer).status_code == 404

        all_ids = {r["id"] for r in client.get(URL, headers=auth, params={"search": suffix}).json()["data"]}
        assert all_ids == {mine, others}
    finally:
        _cleanup(mine, others)
        client.delete(f"/api/v1/users/{user['id']}", headers=auth)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM auth.roles WHERE id = CAST(:id AS uuid)"), {"id": role["id"]})
