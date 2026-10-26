import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.session import Base
from app.models.auth import User


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = {"schema": "master"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # FK ke auth.users ada di database (migrasi 004)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    author: Mapped[User | None] = relationship(
        User, primaryjoin=lambda: foreign(Announcement.created_by) == User.id, viewonly=True, lazy="joined"
    )


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    __table_args__ = (
        UniqueConstraint("user_id", "announcement_id", name="uq_announcement_reads_user_announcement"),
        {"schema": "master"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    announcement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
