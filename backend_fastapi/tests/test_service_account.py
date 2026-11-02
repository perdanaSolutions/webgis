"""
Akun layanan (sistem lain): Bearer token berumur panjang yang hanya berlaku untuk import-json produksi TBS.

Endpoint import dipanggil dengan unit_code yang tidak ada, jadi ditolak 400 sebelum menulis data apa pun:
400 = lolos autentikasi, 401/403 = ditolak di pintu.

CATATAN: import-json produksi TBS kini tanpa autentikasi, jadi test pencabutan/kedaluwarsa/nonaktif token
layanan dihapus (tidak ada endpoint lagi yang memakai token layanan). Lihat catatan di app/api/deps.py.
"""
import uuid
from datetime import datetime, timezone

import pytest
from jwt import decode
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

IMPORT_URL = "/api/v1/pokok-produksi/import-json"
PARAMS = {"year": 2099, "month": 1, "unit_code": "ZZZ9"}
BODY = {"data": [{"KodeBlok": "A001"}]}


@pytest.fixture()
def service_user(client, auth):
    """Buat akun layanan lewat API; dihapus lagi di akhir test."""
    suffix = uuid.uuid4().hex[:8]
    response = client.post("/api/v1/users/", headers=auth, json={
        "username": f"svc-{suffix}", "email": f"svc-{suffix}@example.com", "nama_lengkap": "Tes Layanan",
        "is_service_account": True, "masa_berlaku_token_hari": 30,
    })
    assert response.status_code == 201, response.text
    data = response.json()
    yield data
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": data["id"]})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_service_account_returns_token_once_with_expiry(client, auth, service_user):
    assert service_user["is_service_account"] is True
    assert service_user["access_token"]
    claims = decode(service_user["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    days = (datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(timezone.utc)).days
    assert 28 <= days <= 30
    assert claims["scope"] == ["produksi_tbs:import"]

    # Tidak ditampilkan lagi saat user dibaca ulang.
    again = client.get(f"/api/v1/users/{service_user['id']}", headers=auth).json()
    assert not again.get("access_token")


def test_service_token_works_on_import_json_only(client, service_user):
    headers = _bearer(service_user["access_token"])
    ok = client.post(IMPORT_URL, params=PARAMS, json=BODY, headers=headers)
    assert ok.status_code == 400  # lolos autentikasi; ditolak karena unit_code tidak ada
    assert "ZZZ9" in ok.text

    # Endpoint lain, termasuk import Excel produksi, menolak token layanan.
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403
    excel = client.post("/api/v1/pokok-produksi/import-produksi-tbs", headers=headers,
                        files={"file": ("x.xlsx", b"x")})
    assert excel.status_code == 403


def test_service_account_cannot_login(client, auth):
    suffix = uuid.uuid4().hex[:8]
    created = client.post("/api/v1/users/", headers=auth, json={
        "username": f"svc-{suffix}", "email": f"svc-{suffix}@example.com", "nama_lengkap": "Tes Layanan",
        "is_service_account": True, "password": "RahasiaBanget123"}).json()
    try:
        login = client.post("/api/v1/auth/login", json={"email": f"svc-{suffix}", "password": "RahasiaBanget123"})
        assert login.status_code == 401
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": created["id"]})


def test_token_lifetime_is_limited_by_setting(client, auth):
    suffix = uuid.uuid4().hex[:8]
    response = client.post("/api/v1/users/", headers=auth, json={
        "username": f"svc-{suffix}", "email": f"svc-{suffix}@example.com", "nama_lengkap": "Tes",
        "is_service_account": True, "masa_berlaku_token_hari": settings.SERVICE_TOKEN_MAX_DAYS + 1})
    assert response.status_code == 422


def test_regular_token_still_works_and_service_flag_is_superadmin_only(client, auth):
    assert client.post(IMPORT_URL, params=PARAMS, json=BODY, headers=auth).status_code == 400
    # import-json produksi TBS kini tanpa autentikasi: tanpa token pun lolos sampai validasi.
    no_token = client.post(IMPORT_URL, params=PARAMS, json=BODY)
    assert no_token.status_code == 400
