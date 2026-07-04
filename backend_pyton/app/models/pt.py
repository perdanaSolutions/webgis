from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class PT(Base):
    __tablename__ = "pts"  # Nama tabel di database PostgreSQL

    id = Column(Integer, primary_key=True, index=True)
    kode_pt = Column(String(50), unique=True, nullable=False, index=True)
    nama_pt = Column(String(150), nullable=False)