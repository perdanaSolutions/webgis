import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# 1. Daftarkan path agar python bisa mendeteksi folder 'app' di atas folder alembic
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 2. Impor settings dan database Base utama kita
from app.core.config import settings
from app.core.database import Base

# 3. IMPOR SEMUA MODEL RELASIONAL BARU AGAR TERDETEKSI OLEH ALEMBIC
# Pastikan kamu sudah membuat file model ini di dalam folder app/models/
from app.models.area import Area
from app.models.estate import Estate
from app.models.afdeling import Afdeling
from app.models.blok import Blok
from app.models.pt import PT
# from app.models.auth import Role, Permission, RolePermission
from app.models.auth import Role, Permission, RolePermission, User, UserActivityLog

# 4. Hubungkan database URL dari Config internal FastAPI kita
config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 5. Target metadata untuk fitur pelacakan otomatis (Autogenerate)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()