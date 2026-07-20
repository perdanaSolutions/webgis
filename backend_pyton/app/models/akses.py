from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base 

class LogAksesMenu(Base):
    __tablename__ = "log_akses_menu"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(String, nullable=False)
    menu_id = Column(String, nullable=False)
    created_date = Column(DateTime, server_default=func.now())
    update_date = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LogAksesData(Base):
    __tablename__ = "log_akses_data"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(String, nullable=False)
    kode_pt = Column(String, nullable=True)
    kode_est = Column(String, nullable=True)
    kode_area = Column(String, nullable=True)
    kode_afd = Column(String, nullable=True)
    created_date = Column(DateTime, server_default=func.now())
    update_date = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LogAksesTransaksi(Base):
    __tablename__ = "log_akses_transaksi"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(String, nullable=False)
    nama_table_transaksi = Column(String, nullable=False)
    created_date = Column(DateTime, server_default=func.now())
    update_date = Column(DateTime, server_default=func.now(), onupdate=func.now())
