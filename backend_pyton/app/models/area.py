from sqlalchemy import Column, Integer, String, ForeignKey
from app.core.database import Base

class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, index=True)
    nama_area = Column(String(100), unique=True, nullable=False)

    # TAMBAHKAN KOLOM RELASI BARU DI SINI:
    # Menggunakan nullable=True terlebih dahulu agar data Area lama yang sudah ada di DB tidak error saat migrasi berjalan
    pt_id = Column(Integer, ForeignKey("pts.id", ondelete="SET NULL"), nullable=True)