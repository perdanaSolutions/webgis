import uuid

from sqlalchemy import text

from app.db.session import engine


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_requires_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["errors"][0]["field"] == "auth"


def test_me_and_check_token(client, auth):
    me = client.get("/api/v1/auth/me", headers=auth).json()
    assert "superadmin" in me["roles"]
    assert {"akses_menu", "akses_data", "akses_transaksi", "nama_lengkap"} <= me.keys()
    token = client.get("/api/v1/auth/check-token", headers=auth).json()
    assert token["is_expired"] is False


def test_login_wrong_password_uses_standard_error(client):
    response = client.post("/api/v1/auth/login", json={"email": "tidak-ada@example.com", "password": "salah"})
    assert response.status_code == 401
    assert response.json()["errors"][0]["type"] == "invalid_credentials"


def test_validation_error_format(client, auth):
    response = client.post("/api/v1/users/", headers=auth, json={"username": "x"})
    assert response.status_code == 422
    assert {"type", "field", "msg", "input"} <= response.json()["errors"][0].keys()


def test_user_lifecycle(client, auth):
    roles = client.get("/api/v1/roles/", headers=auth).json()
    viewer = next(r for r in roles if r["nama"] != "superadmin")
    suffix = uuid.uuid4().hex[:8]
    payload = {"username": f"tester_{suffix}", "email": f"tester_{suffix}@example.com", "nama_lengkap": "Tester",
               "role_ids": [viewer["id"]], "password": "rahasia123"}

    created = client.post("/api/v1/users/", headers=auth, json=payload)
    assert created.status_code == 201, created.text
    user = created.json()
    assert any(r["nama"] == viewer["nama"] for r in user["roles"])

    duplicate = client.post("/api/v1/users/", headers=auth, json=payload)
    assert duplicate.status_code == 409

    listing = client.get("/api/v1/users/", headers=auth, params={"search": suffix}).json()
    assert listing["total_data"] == 1

    # user baru tanpa riwayat aktivitas boleh dihapus
    assert client.delete(f"/api/v1/users/{user['id']}", headers=auth).status_code == 200

    # user yang sudah login punya log audit append-only -> tidak bisa dihapus, hanya dinonaktifkan
    payload.update(username=f"tester2_{suffix}", email=f"tester2_{suffix}@example.com")
    user2 = client.post("/api/v1/users/", headers=auth, json=payload).json()
    login = client.post("/api/v1/auth/login", json={"email": payload["username"], "password": "rahasia123"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["username"] == payload["username"]

    assert client.delete(f"/api/v1/users/{user2['id']}", headers=auth).status_code == 409
    updated = client.put(f"/api/v1/users/{user2['id']}", headers=auth, json={"is_active": False}).json()
    assert updated["is_active"] is False
    inactive_login = client.post("/api/v1/auth/login", json={"email": payload["username"], "password": "rahasia123"})
    assert inactive_login.status_code == 403


def test_audit_actor_is_recorded(client, auth, superadmin_id):
    suffix = uuid.uuid4().hex[:8]
    response = client.post("/api/v1/menus/", headers=auth, json={"title": f"Audit {suffix}", "icon": "mdi-test"})
    assert response.status_code == 201
    menu_id = response.json()["id"]
    with engine.connect() as conn:
        actor = conn.execute(text("""
            SELECT actor_user_id FROM audit.change_logs
            WHERE table_name = 'menus' AND operation = 'INSERT' AND new_data->>'id' = :id
        """), {"id": menu_id}).scalar()
    assert str(actor) == superadmin_id
    client.delete(f"/api/v1/menus/{menu_id}", headers=auth)


def test_activity_logs(client, auth):
    logs = client.get("/api/v1/logs/", headers=auth, params={"status_filter": "success", "limit": 5}).json()
    assert logs["limit"] == 5
    assert all(item["status"] == "SUCCESS" for item in logs["data"])
