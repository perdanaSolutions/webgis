"""
app/core/database.py — SQLAlchemy engine & session
"""
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Engine BERSAMA dengan app.db.session. Dulu modul ini membuat engine kedua (5+10 hardcode), sehingga satu
# proses bisa memegang hingga 30 koneksi Postgres — fatal saat API di-scale ke banyak pod.
from app.db.session import engine

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


# Dependency untuk FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
