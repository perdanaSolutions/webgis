"""
Pastikan role 'superadmin' dan akun superadmin ada (idempoten).

    python -m scripts.seed_superadmin              # buat akun jika belum ada
    python -m scripts.seed_superadmin --reset-password

Kredensial diambil dari .env: SEED_ADMIN_USERNAME, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.auth import Role, User  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-password", action="store_true", help="Timpa password akun superadmin yang sudah ada")
    args = parser.parse_args()

    if not settings.SEED_ADMIN_PASSWORD:
        sys.exit("SEED_ADMIN_PASSWORD di .env masih kosong.")

    with SessionLocal() as db:
        role = db.scalar(select(Role).where(Role.name == settings.SUPERADMIN_ROLE))
        if role is None:
            role = Role(name=settings.SUPERADMIN_ROLE, description="Akses penuh sistem")
            db.add(role)
            db.flush()
            print(f"Role '{role.name}' dibuat.")

        username = settings.SEED_ADMIN_USERNAME.lower()
        user = db.scalar(select(User).where(func.lower(User.username) == username))
        if user is None:
            new_user = User(
                full_name="Super Administrator", username=username,
                email=settings.SEED_ADMIN_EMAIL.lower(), hashed_password=get_password_hash(settings.SEED_ADMIN_PASSWORD),
            )
            new_user.roles = [role]
            db.add(new_user)
            print(f"User '{username}' dibuat.")
        elif args.reset_password:
            user.hashed_password = get_password_hash(settings.SEED_ADMIN_PASSWORD)
            user.is_active = True
            print(f"Password user '{username}' direset.")
        else:
            print(f"User '{username}' sudah ada (pakai --reset-password untuk mengganti password).")
        db.commit()


if __name__ == "__main__":
    main()
