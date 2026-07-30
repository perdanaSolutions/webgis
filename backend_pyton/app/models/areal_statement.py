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