"""
Isi / hitung ulang batas afdeling (spatial.division_boundaries, source='derived') dari batas blok.

    python -m scripts.backfill_division_boundaries --all                  # semua afdeling, semua periode
    python -m scripts.backfill_division_boundaries --period 2026-01       # afdeling yang punya upload blok periode itu
    python -m scripts.backfill_division_boundaries --estate KSE           # satu estate (kode / short name / id)
    python -m scripts.backfill_division_boundaries --all --dry-run        # hitung + laporan, lalu ROLLBACK

--period dan --estate boleh digabung. Tanpa --dry-run hasil di-commit dan cache peta dibatalkan
(penghitung audit.data_store_versions 'geojson' naik). Membutuhkan migrasi 021.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.services import division_boundary_service as svc  # noqa: E402


def parse_period(value: str) -> date:
    try:
        year, month = (int(x) for x in value.split("-"))
        return date(year, month, 1)
    except Exception as exc:
        raise argparse.ArgumentTypeError(f"Format periode harus YYYY-MM, bukan '{value}'") from exc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="Semua afdeling")
    ap.add_argument("--period", type=parse_period, help="Periode YYYY-MM (hanya periode itu)")
    ap.add_argument("--estate", help="Kode / short name / id estate")
    ap.add_argument("--dry-run", action="store_true", help="Hitung tanpa menyimpan (ROLLBACK)")
    args = ap.parse_args(argv)
    if not (args.all or args.period or args.estate):
        ap.error("Pilih minimal satu: --all, --period, atau --estate")

    db = SessionLocal()
    try:
        if not svc.table_exists(db):
            print("Tabel spatial.division_boundaries belum ada. Jalankan: python -m scripts.apply_migrations", file=sys.stderr)
            return 2
        divisions = svc.divisions_for(db, estate=args.estate, period=args.period, all_divisions=args.all)
        if not divisions:
            print("Tidak ada afdeling yang cocok dengan filter.", file=sys.stderr)
            return 1
        report = svc.refresh_divisions(db, divisions, periods=[args.period] if args.period else None,
                                       bump_version=not args.dry_run)
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(json.dumps({"mode": "dry-run (rollback)" if args.dry_run else "commit", "afdeling": len(divisions),
                          **report.as_dict()}, ensure_ascii=False, indent=2))
        return 1 if report.gagal else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
