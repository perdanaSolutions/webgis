from sqlalchemy import Column, Integer, String, ForeignKey
from app.core.database import Base

class Estate(Base):
    __tablename__ = "estates"
    id = Column(Integer, primary_key=True, index=True)
    area_id = Column(Integer, ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    kode_est = Column(String(50), unique=True, nullable=False)
    nama_estate = Column(String(100), nullable=False)