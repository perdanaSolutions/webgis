"""
Engine & session SQLAlchemy.

Trigger audit di gis_db_v3 (`audit.log_row_change`) membaca user pelaku dari
setting `app.user_id`. Session menyimpan id user di `session.info`, lalu
setiap transaksi baru mengisi setting itu secara LOKAL (`set_config(..., true)`)
sehingga nilainya ikut hilang saat transaksi selesai dan tidak bocor ke
request lain yang memakai koneksi yang sama dari pool.
"""
from collections.abc import Generator
from uuid import UUID

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    connect_args={"application_name": settings.APP_NAME_IN_DB},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

_AUDIT_KEY = "audit_user_id"
_SET_ACTOR_SQL = "SELECT set_config('app.user_id', %(uid)s, true)"


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "after_begin")
def _apply_audit_actor(session: Session, transaction, connection) -> None:
    user_id = session.info.get(_AUDIT_KEY)
    if user_id:
        connection.exec_driver_sql(_SET_ACTOR_SQL, {"uid": user_id})


def set_audit_actor(db: Session, user_id: UUID | str | None) -> None:
    """Tandai sesi ini milik `user_id` supaya perubahan data tercatat atas namanya."""
    db.info[_AUDIT_KEY] = str(user_id) if user_id else None
    if user_id and db.in_transaction():
        db.connection().exec_driver_sql(_SET_ACTOR_SQL, {"uid": str(user_id)})


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
