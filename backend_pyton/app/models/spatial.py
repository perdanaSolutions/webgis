from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class Perusahaan(Base):
    __tablename__ = "perusahaan"

    pt_id = Column(Integer, primary_key=True, index=True)
    nama_pt = Column(String(150), nullable=False)
    kode_pt = Column(String(50), nullable=False, unique=True)
    bulan = Column(Integer, nullable=True)
    tahun = Column(Integer, nullable=True)

    estates = relationship("Estate", back_populates="perusahaan", cascade="all, delete-orphan")


class Estate(Base):
    __tablename__ = "estate"

    est_id = Column(String(50), primary_key=True)
    pt_id = Column(Integer, ForeignKey("perusahaan.pt_id", ondelete="CASCADE"), nullable=False)
    nama_estate = Column(String(100), nullable=False)
    kode_est = Column(String(50), nullable=False, unique=True)
    bulan = Column(Integer, nullable=True)
    tahun = Column(Integer, nullable=True)

    perusahaan = relationship("Perusahaan", back_populates="estates")
    afdelings = relationship("Afdeling", back_populates="estate", cascade="all, delete-orphan")


class Afdeling(Base):
    __tablename__ = "afdeling"

    afd_id = Column(String(100), primary_key=True)
    est_id = Column(String(50), ForeignKey("estate.est_id", ondelete="CASCADE"), nullable=False)
    kode_afd = Column(String(20), nullable=False)
    bulan = Column(Integer, nullable=True)
    tahun = Column(Integer, nullable=True)

    estate = relationship("Estate", back_populates="afdelings")
    bloks = relationship("Blok", back_populates="afdeling", cascade="all, delete-orphan")


class Blok(Base):
    __tablename__ = "blok"

    blok_id = Column(String(150), primary_key=True)
    afd_id = Column(String(100), ForeignKey("afdeling.afd_id", ondelete="CASCADE"), nullable=False)
    nama_blok = Column(String(100), nullable=False)
    kode_blok = Column(String(50), nullable=False, unique=True)
    tipe_blok = Column(String(50), nullable=True)
    jenis_topografi = Column(String(100), nullable=True)
    jenis_tanah = Column(String(100), nullable=True)
    jenis_bibit = Column(String(100), nullable=True)
    tahun_tanam = Column(Integer, nullable=True)
    status_tanam = Column(String(20), nullable=True)
    bulan = Column(Integer, nullable=True)
    tahun = Column(Integer, nullable=True)

    afdeling = relationship("Afdeling", back_populates="bloks")
    geo_blok = relationship("GeoBlok", back_populates="blok", uselist=False, cascade="all, delete-orphan")


class GeoBlok(Base):
    __tablename__ = "geo_blok"

    blok_id = Column(String(150), ForeignKey("blok.blok_id", ondelete="CASCADE"), primary_key=True)
    geom_polygon = Column(Geometry("MULTIPOLYGON", srid=4326))
    bulan = Column(Integer, nullable=True)
    tahun = Column(Integer, nullable=True)

    blok = relationship("Blok", back_populates="geo_blok")