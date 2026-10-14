from typing import Annotated, Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jwt import decode, PyJWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import SCOPE_PRODUKSI_IMPORT, SERVICE_TOKEN_TYPE
from app.core.database import SessionLocal
from app.db.session import set_audit_actor
from app.models.auth import User, Permission, Role

# Mengatur endpoint mana yang dijadikan acuan Swagger untuk mengambil token JWT
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/swagger-form",  # <--- ARINGKAN KE SINI
    auto_error=False,  # tanpa token: kita sendiri yang membalas 401 dengan format error standar
)


# Skema Bearer murni (tempel token di Swagger): dipakai endpoint yang juga menerima token akun layanan.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token JWT: token login user, atau token akun layanan untuk sistem lain.",
)


def _unauthorized(msg: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"errors": [{"type": "unauthorized", "field": "auth", "msg": msg, "input": None}]},
        headers={"WWW-Authenticate": "Bearer"},
    )

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def _authenticate(db: Session, token: str | None, scope: str | None = None) -> User:
    """
    Token biasa -> user login. Token layanan (typ=service) hanya diterima endpoint yang meminta `scope`
    yang ada di token, dan hanya selama akunnya aktif serta versi tokennya masih yang terbaru.
    """
    if not token:
        raise _unauthorized("Tidak terautentikasi")
    credentials_exception = _unauthorized("Token tidak valid atau telah kedaluwarsa")
    try:
        # Dekode token JWT menggunakan SECRET_KEY kita
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    is_service_token = payload.get("typ") == SERVICE_TOKEN_TYPE
    if is_service_token and (scope is None or scope not in (payload.get("scope") or [])):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"errors": [{"type": "forbidden", "field": "auth", "input": None,
                                "msg": "Token layanan tidak berlaku untuk endpoint ini"}]},
        )

    # Cari user di database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Akun tidak aktif")
    if is_service_token:
        if not user.is_service_account or payload.get("tv") != user.token_version:
            raise _unauthorized("Token layanan sudah dicabut atau diganti")
    elif user.is_service_account:
        raise credentials_exception  # akun layanan hanya boleh memakai token layanan

    # Trigger audit membaca pelaku dari setting app.user_id (lihat app/db/session.py)
    set_audit_actor(db, user.id)
    return user


def get_current_user(db: Session = Depends(get_db), token: str | None = Depends(oauth2_scheme)) -> User:
    """Dependency untuk mengambil data user yang sedang login berdasarkan JWT Token"""
    return _authenticate(db, token)


def user_or_service(scope: str):
    """Dependency: user login biasa, atau akun layanan yang tokennya memuat `scope`."""
    def dependency(db: Session = Depends(get_db),
                   credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User:
        return _authenticate(db, credentials.credentials if credentials else None, scope)
    return dependency


def user_has_permission(db: Session, user: User, permission: str) -> bool:
    """Superadmin selalu lolos; selain itu permission harus dimiliki salah satu role user."""
    if any(role.nama == "superadmin" for role in user.roles):
        return True
    return db.query(User).filter(
        User.id == user.id
    ).join(User.roles).join(Role.permissions).filter(
        Permission.kode == permission
    ).first() is not None


class PermissionChecker:
    """Class Dependency untuk mengecek apakah user memiliki permission tertentu"""
    def __init__(self, required_permission: str):
        # Contoh required_permission: "blok:read" atau "produksi:write"
        self.required_permission = required_permission

    def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not user_has_permission(db, current_user, self.required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Anda tidak memiliki hak akses ({self.required_permission}) untuk fitur ini"
            )
        return current_user


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CanImportProduksiJson = Annotated[User, Depends(user_or_service(SCOPE_PRODUKSI_IMPORT))]
CanUploadGeojson = Annotated[User, Depends(PermissionChecker("upload:geojson"))]
CanWriteAnnouncement = Annotated[User, Depends(PermissionChecker("pengumuman:write"))]
