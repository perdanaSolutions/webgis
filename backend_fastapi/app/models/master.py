"""Hierarki kebun: company -> estate -> division (afdeling) -> block. Area terhubung lewat trx.area_statements."""
from sqlalchemy import BigInteger, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

SCHEMA = "master"


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150))


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str | None] = mapped_column(String(150))


class Estate(Base):
    __tablename__ = "estates"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.companies.id"))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str | None] = mapped_column(String(20))

    company: Mapped[Company] = relationship(lazy="joined")


class Division(Base):
    __tablename__ = "divisions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    estate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.estates.id"))
    code: Mapped[str] = mapped_column(String(20))

    estate: Mapped[Estate] = relationship(lazy="joined")


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    division_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("master.divisions.id"))
    code: Mapped[str] = mapped_column(String(20))
    block_type_id: Mapped[int | None] = mapped_column(SmallInteger)
