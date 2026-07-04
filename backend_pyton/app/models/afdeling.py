from sqlalchemy import Column, Integer, String, ForeignKey
from app.core.database import Base

class Afdeling(Base):
    __tablename__ = "afdelings"
    id = Column(Integer, primary_key=True, index=True)
    estate_id = Column(Integer, ForeignKey("estates.id", ondelete="CASCADE"), nullable=False)
    kode_afd = Column(String(20), nullable=False)  # Sesuai isi DB: AFDI01, dst.