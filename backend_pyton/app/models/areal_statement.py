from sqlalchemy import Column, BigInteger, String, Integer, Numeric
from app.core.database import Base

class TrxArealStatement(Base):
    __tablename__ = "trx_areal_statement"

    # Primary Key
    id_areal_statement = Column(String(150), nullable=True)
    
    # Kolom sesuai struktur PostgreSQL di gambar
    blok_id = Column(String(150), nullable=True)
    tahun = Column(Integer, nullable=True)
    bulan = Column(Integer, nullable=True)
    luas_tanam = Column(Numeric(14, 2), nullable=True)
    luas_tanah = Column(Numeric(14, 2), nullable=True)
    total_pokok = Column(Integer, nullable=True)
    sph = Column(Numeric(10, 2), nullable=True)
    pct_tanah_datar = Column(Integer, nullable=True)
    pct_berbukit = Column(Integer, nullable=True)
    pct_gelombang = Column(Integer, nullable=True)
    pct_curam = Column(Integer, nullable=True)
    id = Column(BigInteger, nullable=True, primary_key=True, index=True, autoincrement=True)

    # Kolom Tambahan Baru
    area_code = Column(String(50), nullable=True)
    company_code = Column(String(50), nullable=True)
    estate = Column(String(100), nullable=True)
    unit_code = Column(String(50), nullable=True)
    estate_short_name = Column(String(50), nullable=True)
    devision_code = Column(String(50), nullable=True)
    kode_blok = Column(String(50), nullable=True)
    tipe_blok = Column(String(50), nullable=True)
    status_tanam = Column(String(50), nullable=True)
    bulan_tanam = Column(String(50), nullable=True)
    tahun_tanam = Column(Integer, nullable=True)
    jenis_bibit = Column(String(100), nullable=True)
    jenis_topografi = Column(String(100), nullable=True)
    jenis_tanah = Column(String(100), nullable=True)