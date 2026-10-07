import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.security import create_access_token
from app.db.session import engine

URL = "/api/v1/pengumuman/"


def _iso(delta_days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=delta_days)).isoformat()


def test_announcement_crud(client, auth):
    created = client.post(URL, headers=auth, json={"judul": "  Libur Nasional ", "isi": "Kantor tutup."})
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["judul"] == "Libur Nasional"
    assert item["status"] == "aktif"
    assert item["dibuat_oleh"]
    item_id = item["id"]

    try:
        assert client.get(f"{URL}{item_id}", headers=auth).json()["isi"] == "Kantor tutup."

        listing = client.get(URL, headers=auth, params={"search": "libur nasional"}).json()
        assert any(row["id"] == item_id for row in listing["data"])

        updated = client.put(f"{URL}{item_id}", headers=auth, json={"judul": "Libur Cuti", "tanggal_mulai": _iso(2)})
        assert updated.status_code == 200, updated.text
        assert updated.json()["judul"] == "Libur Cuti"
        assert updated.json()["isi"] == "Kantor tutup."  # tidak dikirim, tidak berubah
        assert updated.json()["status"] == "terjadwal"

        scheduled = client.get(URL, headers=auth, params={"status": "terjadwal", "limit": 100}).json()
        assert any(row["id"] == item_id for row in scheduled["data"])

        off = client.put(f"{URL}{item_id}", headers=auth, json={"is_active": False, "tanggal_mulai": None})
        assert off.json()["status"] == "nonaktif"

        assert client.put(f"{URL}{item_id}", headers=auth, json={}).status_code == 400
        assert client.put(f"{URL}{item_id}", headers=auth, json={"judul": None}).status_code == 400
        assert client.put(f"{URL}{item_id}", headers=auth, json={"tanggal_berakhir": _iso(-30)}).status_code == 200
        assert client.get(f"{URL}{item_id}", headers=auth).json()["status"] == "nonaktif"
    finally:
        deleted = client.delete(f"{URL}{item_id}", headers=auth)
    assert deleted.status_code == 200
    assert client.get(f"{URL}{item_id}", headers=auth).status_code == 404


def test_announcement_validation(client, auth):
    assert client.post(URL, headers=auth, json={"judul": "", "isi": "x"}).status_code == 422
    bad_period = client.post(URL, headers=auth, json={
        "judul": "x", "isi": "y", "tanggal_mulai": _iso(5), "tanggal_berakhir": _iso(1)})
    assert bad_period.status_code == 422
    assert client.get(URL, headers=auth, params={"status": "ngawur"}).status_code == 400
    assert client.post(URL, json={"judul": "x", "isi": "y"}).status_code == 401


def test_announcement_permissions(client, auth):
    suffix = uuid.uuid4().hex[:6]
    role = client.post("/api/v1/roles/", headers=auth, json={"nama": f"viewer{suffix}"}).json()
    user = client.post("/api/v1/users/", headers=auth, json={
        "username": f"viewer{suffix}", "email": f"viewer{suffix}@example.com", "nama_lengkap": "Viewer",
        "password": "Passw0rd!123", "role_ids": [role["id"]]}).json()
    viewer = {"Authorization": f"Bearer {create_access_token(user['id'])}"}

    shown = client.post(URL, headers=auth, json={"judul": f"Tayang {suffix}", "isi": "a"}).json()
    hidden = client.post(URL, headers=auth, json={"judul": f"Draft {suffix}", "isi": "b", "is_active": False}).json()
    future = client.post(URL, headers=auth, json={"judul": f"Nanti {suffix}", "isi": "c", "tanggal_mulai": _iso(3)}).json()
    try:
        assert client.post(URL, headers=viewer, json={"judul": "x", "isi": "y"}).status_code == 403
        assert client.put(f"{URL}{shown['id']}", headers=viewer, json={"judul": "x"}).status_code == 403
        assert client.delete(f"{URL}{shown['id']}", headers=viewer).status_code == 403

        ids = {row["id"] for row in client.get(URL, headers=viewer, params={"search": suffix}).json()["data"]}
        assert ids == {shown["id"]}
        # filter status diabaikan untuk user biasa: tetap hanya yang tayang
        ids = {row["id"] for row in client.get(URL, headers=viewer, params={"search": suffix, "status": "nonaktif"}).json()["data"]}
        assert ids == {shown["id"]}
        assert client.get(f"{URL}{shown['id']}", headers=viewer).status_code == 200
        assert client.get(f"{URL}{hidden['id']}", headers=viewer).status_code == 404
        assert client.get(f"{URL}{future['id']}", headers=viewer).status_code == 404

        all_ids = {row["id"] for row in client.get(URL, headers=auth, params={"search": suffix}).json()["data"]}
        assert all_ids == {shown["id"], hidden["id"], future["id"]}
    finally:
        for item in (shown, hidden, future):
            client.delete(f"{URL}{item['id']}", headers=auth)
        client.delete(f"/api/v1/users/{user['id']}", headers=auth)
        with engine.begin() as conn:  # router roles aktif tidak punya DELETE
            conn.execute(text("DELETE FROM auth.roles WHERE id = CAST(:id AS uuid)"), {"id": role["id"]})
