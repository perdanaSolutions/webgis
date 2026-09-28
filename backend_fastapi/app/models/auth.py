from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text, BigInteger, Boolean, Table, Identity
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

AUTH_SCHEMA = "auth"


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("auth.roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    schema=AUTH_SCHEMA,
)


# 1. Tabel Pivot (Many-to-Many) role_permissions
class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = {"schema": AUTH_SCHEMA}

    role_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth.roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth.permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


# 2. Tabel roles
class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": AUTH_SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    nama = Column("name", String(50), unique=True, nullable=False, index=True)
    deskripsi = Column("description", Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    permissions = relationship(
        "Permission",
        secondary="auth.role_permissions",
        back_populates="roles",
    )
    users = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
    )


# 3. Tabel permissions
class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": AUTH_SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    kode = Column("code", String(100), unique=True, nullable=False, index=True)
    resource = Column(String(50), nullable=False, index=True)
    aksi = Column("action", String(20), nullable=False)
    deskripsi = Column("description", Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    roles = relationship(
        "Role",
        secondary="auth.role_permissions",
        back_populates="permissions",
    )


# 4. Tabel users (auth.users)
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": AUTH_SCHEMA}

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    nama_lengkap = Column("full_name", String(150), nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )
    # Log audit append-only: jangan cascade delete/update. Trigger
    # audit.deny_modification() menolak UPDATE dan DELETE pada tabel ini.
    activities = relationship(
        "UserActivityLog",
        back_populates="user",
        passive_deletes=True,
    )

    @property
    def role(self):
        return self.roles[0] if self.roles else None

    @property
    def role_id(self):
        return self.role.id if self.role else None


# 5. Audit trail (audit.user_activities)
class UserActivityLog(Base):
    __tablename__ = "user_activities"
    __table_args__ = {"schema": "audit"}

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    aksi = Column("action", String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    record_id = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    status = Column(String(10), nullable=False)
    detail = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    user = relationship("User", back_populates="activities")
