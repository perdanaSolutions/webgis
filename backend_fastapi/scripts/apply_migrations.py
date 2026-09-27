"""
Jalankan file SQL di folder migrations/ secara berurutan (nama file = urutan).

    python -m scripts.apply_migrations

Setiap file wajib idempoten (IF NOT EXISTS, dsb.) karena skrip ini tidak
menyimpan riwayat migrasi -- aman dijalankan berulang kali.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import engine  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def main() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print("Tidak ada file migrasi.")
        return
    with engine.begin() as conn:
        for path in files:
            print(f"-> {path.name}")
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
    print(f"Selesai: {len(files)} file migrasi dijalankan.")


if __name__ == "__main__":
    main()
