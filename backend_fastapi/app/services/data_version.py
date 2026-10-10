"""
Penghitung berapa kali data benar-benar disimpan ke database.

`geojson` naik saat unggah atau hapus GeoJSON (batas blok, TPH, sawit, slope,
landuse, jalan, jembatan, dan layer dinamis) berhasil di-commit.
`history` naik saat impor transaksi (areal statement, produksi, rotasi) berhasil
di-commit.

Redis memasukkan kedua angka ini ke kunci cache. Angka berubah -> kunci lama
tidak dipakai -> permintaan berikutnya membaca database.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

GEOJSON = "geojson"
HISTORY = "history"
DOMAINS = (GEOJSON, HISTORY)

_ENSURE_SQL = """
CREATE TABLE IF NOT EXISTS audit.data_store_versions (
    domain text PRIMARY KEY,
    version bigint NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO audit.data_store_versions (domain, version)
VALUES ('geojson', 0), ('history', 0)
ON CONFLICT (domain) DO NOTHING;
"""

_ready = False


def ensure_data_store_versions(engine: Engine) -> None:
    """Buat tabel penghitung. DDL di transaksi sendiri supaya tidak ikut rollback unggahan."""
    global _ready
    if _ready:
        return
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(_ENSURE_SQL)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    _ready = True


def bump(db: Session, domain: str) -> int:
    """Naikkan penghitung di transaksi pemanggil. Panggil sebelum commit data."""
    if domain not in DOMAINS:
        raise ValueError(f"domain versi tidak dikenal: {domain}")
    from app.core.database import engine

    ensure_data_store_versions(engine)
    version = db.execute(
        text("""
            INSERT INTO audit.data_store_versions (domain, version)
            VALUES (:domain, 1)
            ON CONFLICT (domain) DO UPDATE
            SET version = audit.data_store_versions.version + 1,
                updated_at = now()
            RETURNING version
        """),
        {"domain": domain},
    ).scalar_one()
    return int(version)


def read_store_versions() -> tuple[int, int]:
    """`(versi geojson, versi histori)`. `(0, 0)` bila tabel belum ada."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        rows = db.execute(
            text("SELECT domain, version FROM audit.data_store_versions WHERE domain IN ('geojson', 'history')")
        ).all()
    except Exception:
        return (0, 0)
    finally:
        db.close()
    found = {domain: int(version) for domain, version in rows}
    return (found.get(GEOJSON, 0), found.get(HISTORY, 0))
