"""
Audit per baris tidak menyimpan isi kolom geometri (migrasi 015).

Semua perubahan dijalankan di dalam satu transaksi yang selalu di-rollback, jadi database test tidak berubah.
"""
import pytest
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture()
def conn():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()


def _last_log(conn, table: str, operation: str) -> dict:
    row = conn.execute(text("""
        SELECT old_data, new_data, changed_cols FROM audit.change_logs
        WHERE table_name = :t AND operation = :op ORDER BY id DESC LIMIT 1
    """), {"t": table, "op": operation}).mappings().one()
    return dict(row)


@pytest.fixture()
def boundary(conn):
    """Satu batas blok baru di periode 2099-01-01 (turunan dari batas yang sudah ada)."""
    inserted = conn.execute(text("""
        INSERT INTO spatial.block_boundaries (block_id, period, geom)
        SELECT block_id, DATE '2099-01-01', geom FROM spatial.block_boundaries LIMIT 1
        RETURNING block_id
    """)).scalar()
    if inserted is None:
        pytest.skip("Tidak ada batas blok di database test.")
    return inserted


def test_insert_omits_geometry(conn, boundary):
    log = _last_log(conn, "block_boundaries", "INSERT")
    assert log["old_data"] is None and log["changed_cols"] is None
    assert "geom" not in log["new_data"]
    assert log["new_data"]["block_id"] == boundary
    assert log["new_data"]["period"] == "2099-01-01"


def test_update_geometry_only_is_flagged(conn, boundary):
    conn.execute(text("""
        UPDATE spatial.block_boundaries SET geom = ST_Multi(ST_Translate(geom, 0.0001, 0))
        WHERE block_id = :b AND period = DATE '2099-01-01'
    """), {"b": boundary})
    log = _last_log(conn, "block_boundaries", "UPDATE")
    assert log["changed_cols"] == ["geom"]
    assert "geom" not in log["old_data"] and "geom" not in log["new_data"]


def test_update_attribute_is_flagged_without_geometry(conn, boundary):
    batch = conn.execute(text("SELECT id FROM audit.upload_batches LIMIT 1")).scalar()
    if batch is None:
        pytest.skip("Tidak ada upload batch di database test.")
    conn.execute(text("""
        UPDATE spatial.block_boundaries SET upload_batch_id = :u
        WHERE block_id = :b AND period = DATE '2099-01-01'
    """), {"u": batch, "b": boundary})
    log = _last_log(conn, "block_boundaries", "UPDATE")
    assert log["changed_cols"] == ["upload_batch_id"]


def test_update_without_change_is_not_logged(conn, boundary):
    before = conn.execute(text("SELECT count(*) FROM audit.change_logs WHERE table_name = 'block_boundaries'")).scalar()
    conn.execute(text("UPDATE spatial.block_boundaries SET geom = geom WHERE block_id = :b AND period = DATE '2099-01-01'"),
                 {"b": boundary})
    after = conn.execute(text("SELECT count(*) FROM audit.change_logs WHERE table_name = 'block_boundaries'")).scalar()
    assert after == before


def test_delete_omits_geometry(conn, boundary):
    conn.execute(text("DELETE FROM spatial.block_boundaries WHERE block_id = :b AND period = DATE '2099-01-01'"),
                 {"b": boundary})
    log = _last_log(conn, "block_boundaries", "DELETE")
    assert log["new_data"] is None
    assert "geom" not in log["old_data"] and log["old_data"]["block_id"] == boundary


def test_table_without_geometry_is_unchanged(conn):
    conn.execute(text("INSERT INTO master.areas (code, name) VALUES ('ZZAUDIT', 'Audit uji')"))
    log = _last_log(conn, "areas", "INSERT")
    full_row = conn.execute(text("SELECT to_jsonb(a) FROM master.areas a WHERE code = 'ZZAUDIT'")).scalar()
    assert log["new_data"] == full_row


def test_wide_geometry_table_keeps_every_attribute(conn):
    """jsonb_build_object dibatasi 100 argumen; tabel lebar harus tetap tercatat lengkap."""
    columns = ", ".join(f"c{i} integer" for i in range(120))
    conn.execute(text(f"CREATE TABLE public.audit_wide_test (id integer PRIMARY KEY, {columns}, geom geometry(Point, 4326))"))
    conn.execute(text("""
        CREATE TRIGGER audit_row AFTER INSERT OR DELETE ON public.audit_wide_test
        FOR EACH ROW EXECUTE FUNCTION audit.log_row_change()
    """))
    conn.execute(text("""
        CREATE TRIGGER audit_row_update AFTER UPDATE ON public.audit_wide_test
        FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION audit.log_row_change()
    """))
    values = ", ".join(str(i) for i in range(120))
    conn.execute(text(f"INSERT INTO public.audit_wide_test VALUES (1, {values}, ST_SetSRID(ST_MakePoint(1, 2), 4326))"))
    log = _last_log(conn, "audit_wide_test", "INSERT")
    assert len(log["new_data"]) == 121 and "geom" not in log["new_data"]
    assert log["new_data"]["c0"] == 0 and log["new_data"]["c119"] == 119
