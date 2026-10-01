"""
Test integrasi terhadap database SALINAN, bukan gis_db_v3 asli (test menulis data).

Siapkan sekali:
    CREATE DATABASE gis_db_v3_test TEMPLATE gis_db_v3;
Lalu jalankan:  pytest -q      (nama DB bisa diganti lewat env TEST_DB_NAME)
"""
import os

os.environ["DB_NAME"] = os.environ.get("TEST_DB_NAME", "gis_db_v3_test")
# Jangan menyentuh Redis sungguhan saat tes, kecuali TEST_REDIS=1.
if os.environ.get("TEST_REDIS") != "1":
    os.environ["REDIS_MAP_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionstart(session):
    if not settings.DB_NAME.endswith("_test"):
        pytest.exit(f"Menolak menjalankan test ke database '{settings.DB_NAME}' (harus berakhiran _test).")


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def superadmin_id() -> str:
    with engine.connect() as conn:
        user_id = conn.execute(text("""
            SELECT u.id FROM auth.users u
            JOIN auth.user_roles ur ON ur.user_id = u.id
            JOIN auth.roles r ON r.id = ur.role_id
            WHERE r.name = :role AND u.is_active ORDER BY u.created_at LIMIT 1
        """), {"role": settings.SUPERADMIN_ROLE}).scalar()
    if user_id is None:
        pytest.skip("Tidak ada user superadmin aktif di database test.")
    return str(user_id)


@pytest.fixture(scope="session")
def auth(superadmin_id) -> dict:
    return {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}


@pytest.fixture(scope="session")
def sample_block() -> dict:
    """Blok yang punya batas, area statement, dan produksi (dipakai banyak test)."""
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT bl.id, bl.code, dv.code AS division, es.code AS estate, co.code AS company, co.name AS company_name
            FROM master.blocks bl
            JOIN master.divisions dv ON dv.id = bl.division_id
            JOIN master.estates es ON es.id = dv.estate_id
            JOIN master.companies co ON co.id = es.company_id
            WHERE EXISTS (SELECT 1 FROM spatial.block_boundaries b WHERE b.block_id = bl.id)
              AND EXISTS (SELECT 1 FROM trx.area_statements a WHERE a.block_id = bl.id)
              AND EXISTS (SELECT 1 FROM trx.block_productions p WHERE p.block_id = bl.id)
            ORDER BY bl.id LIMIT 1
        """)).mappings().first()
        if row is None:
            row = conn.execute(text("""
                SELECT bl.id, bl.code, dv.code AS division, es.code AS estate, co.code AS company, co.name AS company_name
                FROM master.blocks bl JOIN master.divisions dv ON dv.id = bl.division_id
                JOIN master.estates es ON es.id = dv.estate_id JOIN master.companies co ON co.id = es.company_id
                WHERE EXISTS (SELECT 1 FROM spatial.block_boundaries b WHERE b.block_id = bl.id)
                ORDER BY bl.id LIMIT 1
            """)).mappings().first()
    assert row is not None, "Database test tidak punya blok dengan batas."
    return dict(row)
