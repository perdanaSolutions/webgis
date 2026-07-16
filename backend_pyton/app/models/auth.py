from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text, BigInteger, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.akses import LogAksesMenu, LogAksesData, LogAksesTransaksi

# 1. Tabel Pivot (Many-to-Many) role_permissions
class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("roles.id", ondelete="CASCADE"), 
        primary_key=True
    )
    permission_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("permissions.id", ondelete="CASCADE"), 
        primary_key=True
    )
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=text("now()")
    )


# 2. Tabel roles
class Role(Base):
    __tablename__ = "roles"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("uuid_generate_v4()")
    )
    nama = Column(String(50), unique=True, nullable=False, index=True)
    deskripsi = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=text("now()")
    )

    # Relasi Many-to-Many ke Permission melalui RolePermission
    permissions = relationship(
        "Permission", 
        secondary="role_permissions", 
        back_populates="roles"
    )

    akses_menu = relationship(
        "LogAksesMenu", 
        primaryjoin="foreign(LogAksesMenu.role_id) == cast(Role.id, String)",
        lazy="selectin" # Rekomendasi: Gunakan selectin agar relasi langsung ikut ter-load otomatis saat query Role
    )
    
    akses_data = relationship(
        "LogAksesData", 
        primaryjoin="foreign(LogAksesData.role_id) == cast(Role.id, String)",
        lazy="selectin"
    )
    
    akses_transaksi = relationship(
        "LogAksesTransaksi", 
        primaryjoin="foreign(LogAksesTransaksi.role_id) == cast(Role.id, String)",
        lazy="selectin"
    )


# 3. Tabel permissions
class Permission(Base):
    __tablename__ = "permissions"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("uuid_generate_v4()")
    )
    kode = Column(String(100), unique=True, nullable=False, index=True)
    resource = Column(String(50), nullable=False, index=True)
    aksi = Column(String(20), nullable=False)
    deskripsi = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=text("now()")
    )

    # Relasi balik Many-to-Many ke Role
    roles = relationship(
        "Role", 
        secondary="role_permissions", 
        back_populates="permissions"
    )

# 4. Tabel users
class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("uuid_generate_v4()")
    )
    role_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("roles.id", ondelete="RESTRICT"), 
        nullable=False
    )
    nama_lengkap = Column(String(150), nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # 2. PERBAIKAN DI BARIS INI: Gunakan Boolean asli SQLAlchemy
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=text("now()")
    )

    # Relasi
    role = relationship("Role")
    activities = relationship("UserActivityLog", back_populates="user", cascade="all, delete-orphan")


# 5. Tabel user_activity_log (Audit Trail)
class UserActivityLog(Base):
    __tablename__ = "user_activity_log"

    # Menggunakan BigInteger karena tipe datanya bigserial di PostgreSQL
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    aksi = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    record_id = Column(Text, nullable=True)  # Menyimpan ID data yang diubah
    ip_address = Column(String(45), nullable=True)
    status = Column(String(10), nullable=False)  # e.g., 'SUCCESS', 'FAILED'
    detail = Column(JSONB, nullable=True)  # Menyimpan payload detail perubahan data
    created_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=text("now()")
    )

    # Relasi balik ke User
    user = relationship("User", back_populates="activities")