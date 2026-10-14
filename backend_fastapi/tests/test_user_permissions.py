"""Tulis data user (buat/ubah/hapus) hanya untuk yang punya permission user:write."""
import uuid

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import engine


def _role_id(name):
    with engine.connect() as conn:
        return conn.execute(text("SELECT id FROM auth.roles WHERE name = :n"), {"n": name}).scalar()


@pytest.fixture()
def make_user(client, auth):
    created = []

    def make(role_name):
        role_id = _role_id(role_name)
        if role_id is None:
            pytest.skip(f"Role '{role_name}' tidak ada di database test.")
        suffix = uuid.uuid4().hex[:8]
        response = client.post("/api/v1/users/", headers=auth, json={
            "username": f"t-{suffix}", "email": f"t-{suffix}@example.com", "nama_lengkap": "Tes Izin",
            "password": "RahasiaBanget123", "role_ids": [str(role_id)]})
        assert response.status_code == 201, response.text
        user = response.json()
        created.append(user["id"])
        return user, {"Authorization": f"Bearer {create_access_token(user['id'])}"}

    yield make
    with engine.begin() as conn:
        for user_id in created:
            conn.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})


def _payload():
    suffix = uuid.uuid4().hex[:8]
    return {"username": f"x-{suffix}", "email": f"x-{suffix}@example.com", "nama_lengkap": "Tes",
            "password": "RahasiaBanget123", "role_ids": [str(_role_id("viewer"))]}


def test_user_without_permission_cannot_write_users(client, make_user):
    viewer, headers = make_user("viewer")
    assert client.post("/api/v1/users/", headers=headers, json=_payload()).status_code == 403
    assert client.put(f"/api/v1/users/{viewer['id']}", headers=headers, json={"nama_lengkap": "Ubah"}).status_code == 403
    assert client.delete(f"/api/v1/users/{viewer['id']}", headers=headers).status_code == 403
    assert client.post(f"/api/v1/users/{viewer['id']}/service-token", headers=headers, json={}).status_code == 403


def test_user_with_permission_can_write_users(client, make_user):
    _, headers = make_user("admin")
    response = client.post("/api/v1/users/", headers=headers, json=_payload())
    assert response.status_code == 201, response.text
    created_id = response.json()["id"]
    assert client.delete(f"/api/v1/users/{created_id}", headers=headers).status_code == 200


def test_admin_cannot_create_service_account(client, make_user):
    _, headers = make_user("admin")
    payload = {**_payload(), "is_service_account": True}
    payload.pop("password")
    assert client.post("/api/v1/users/", headers=headers, json=payload).status_code == 403


def test_list_users_requires_user_read(client, make_user):
    _, viewer_headers = make_user("viewer")
    assert client.get("/api/v1/users/", headers=viewer_headers).status_code == 403
    _, admin_headers = make_user("admin")
    assert client.get("/api/v1/users/", headers=admin_headers).status_code == 200


def test_admin_cannot_grant_or_touch_superadmin(client, make_user):
    superadmin, _ = make_user(settings.SUPERADMIN_ROLE)
    viewer, _ = make_user("viewer")
    _, admin = make_user("admin")
    superadmin_role = str(_role_id(settings.SUPERADMIN_ROLE))

    # Tidak boleh membuat user superadmin, mengangkat user lain, atau mengubah/menghapus superadmin.
    body = {**_payload(), "role_ids": [superadmin_role]}
    assert client.post("/api/v1/users/", headers=admin, json=body).status_code == 403
    assert client.put(f"/api/v1/users/{viewer['id']}", headers=admin, json={"role_ids": [superadmin_role]}).status_code == 403
    assert client.put(f"/api/v1/users/{superadmin['id']}", headers=admin, json={"password": "PasswordBaru123"}).status_code == 403
    assert client.delete(f"/api/v1/users/{superadmin['id']}", headers=admin).status_code == 403

    # Admin tetap boleh mengubah user biasa.
    assert client.put(f"/api/v1/users/{viewer['id']}", headers=admin, json={"nama_lengkap": "Diubah"}).status_code == 200


def test_superadmin_can_grant_superadmin(client, auth):
    body = {**_payload(), "role_ids": [str(_role_id(settings.SUPERADMIN_ROLE))]}
    response = client.post("/api/v1/users/", headers=auth, json=body)
    assert response.status_code == 201, response.text
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": response.json()["id"]})
