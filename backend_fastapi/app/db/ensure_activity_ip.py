"""Pasang aturan database: insert audit.user_activities tanpa IP ditolak."""
from sqlalchemy.engine import Engine

# Sama dengan sql/audit_require_activity_ip.sql. Disimpan di sini karena
# image Docker hanya menyalin folder backend_fastapi.
# Advisory lock per transaksi: banyak replica start bersamaan tidak saling DROP/CREATE trigger (deadlock).
# Level transaksi (bukan sesi) supaya aman lewat PgBouncer mode transaction.
REQUIRE_ACTIVITY_IP_SQL = """
SELECT pg_advisory_xact_lock(7420001);

CREATE OR REPLACE FUNCTION audit.require_activity_ip()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.ip_address IS NULL THEN
        RAISE EXCEPTION 'audit.user_activities.ip_address wajib diisi';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_activities_require_ip ON audit.user_activities;

CREATE TRIGGER user_activities_require_ip
    BEFORE INSERT ON audit.user_activities
    FOR EACH ROW
    EXECUTE FUNCTION audit.require_activity_ip();
"""


def ensure_activity_ip_required(engine: Engine) -> None:
    # Script punya beberapa perintah dan tubuh fungsi dengan titik koma,
    # jadi dijalankan lewat protokol query sederhana, bukan prepared statement.
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(REQUIRE_ACTIVITY_IP_SQL)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
