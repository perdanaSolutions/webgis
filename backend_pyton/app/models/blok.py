"""
app/models/blok.py — SQLAlchemy model untuk tabel bloks (Relasional Baru)
"""
from sqlalchemy import Column, Integer, Numeric, String, ForeignKey
from geoalchemy2 import Geometry
from app.core.database import Base

class Blok(Base):
    __tablename__ = "bloks"  # Diubah dari "tpa_sga_2026" menjadi "bloks"

    # Primary key utama tabel bloks
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key ke tabel afdelings (menghubungkan ke hirarki wilayah atas)
    afdeling_id = Column(Integer, ForeignKey("afdelings.id", ondelete="CASCADE"), nullable=False)

    # Identitas Blok sesuai field migrasi # 5
    kode_blok = Column(String(50), unique=True, nullable=False, index=True)
    nama_blok = Column(String(100), nullable=False)
    ownership = Column(String(50), default="Inti")
    
    # Detail Tanaman
    tahun_tanam = Column(Integer)  # Diubah dari 'tt'
    bulan_tanam = Column(String(20))  # Diubah dari 'blntanam'
    topografi = Column(String(50))
    jenis_tanah = Column(String(100))  # Diubah dari 'jenistanah'
    jenis_bibit = Column(String(100))  # Diubah dari 'jenis_bibit'
    status_tanaman = Column(String(20), default="TM")  # Diubah dari 'status'

    # Luas (Menggunakan Numeric agar akurat sesuai struktur database)
    luas_tanah = Column(Numeric(5, 2))  # Diubah dari 'ltanah'
    luas_tanam = Column(Numeric(5, 2))  # Diubah dari 'ltanam'

    # Kolom Geometri Spasial PostGIS
    geom = Column(Geometry("MULTIPOLYGON", srid=4326))  # Diubah dari 'geometry' menjadi 'geom'