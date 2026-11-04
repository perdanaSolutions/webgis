import threading
import time
from typing import Annotated, Generator
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from jwt import decode, PyJWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import SCOPE_PRODUKSI_IMPORT, SERVICE_TOKEN_TYPE
from app.core.database import SessionLocal
from app.core.auth_session import AuthSessionRevoked, AuthSessionUnavailable, assert_session
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


def _auth_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"errors": [{"type": "auth_unavailable", "field": "auth",
                            "msg": "Layanan autentikasi sementara tidak tersedia", "input": None}]},
    )


def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def _decode_token(token: str | None, scope: str | None) -> tuple[dict, bool]:
    """Validasi JWT (tanpa I/O). Kembalikan (payload, is_service_token)."""
    if not token:
        raise _unauthorized("Tidak terautentikasi")
    credentials_exception = _unauthorized("Token tidak valid atau telah kedaluwarsa")
    try:
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
    return payload, is_service_token


def _load_user(db: Session, payload: dict, is_service_token: bool, set_actor: bool = True) -> User:
    """
    Bagian cek login yang memakai DB. SINKRON: selalu panggil lewat run_in_threadpool dari kode async.
    Query sinkron di event loop membekukan seluruh proses selama menunggu DB (insiden 4 Nov 2026: PgBouncer
    penuh -> query menunggu sampai 120 dtk -> /health tidak terjawab -> HAProxy menandai semua replika DOWN).
    """
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Akun tidak aktif")
    if is_service_token:
        if not user.is_service_account or payload.get("tv") != user.token_version:
            raise _unauthorized("Token layanan sudah dicabut atau diganti")
    elif user.is_service_account:
        raise _unauthorized("Token tidak valid atau telah kedaluwarsa")  # akun layanan hanya boleh token layanan
    if set_actor:
        set_audit_actor(db, user.id)
    return user


async def _check_session(payload: dict) -> None:
    """User JWT: registry Redis memastikan logout/revoke konsisten di semua instance."""
    try:
        await assert_session(payload.get("jti"))
    except AuthSessionRevoked:
        raise _unauthorized("Token tidak valid atau telah kedaluwarsa")
    except AuthSessionUnavailable:
        raise _auth_unavailable()


async def _authenticate(db: Session, token: str | None, scope: str | None = None) -> User:
    """
    Token biasa -> user login (+ cek sesi Redis jti bila REDIS_AUTH_ENABLED).
    Token layanan (typ=service) hanya diterima endpoint yang meminta `scope`
    yang ada di token, dan hanya selama akunnya aktif serta versi tokennya masih yang terbaru.
    """
    payload, is_service_token = _decode_token(token, scope)
    user = await run_in_threadpool(_load_user, db, payload, is_service_token)
    if not is_service_token:
        await _check_session(payload)
    return user


async def get_current_user(db: Session = Depends(get_db), token: str | None = Depends(oauth2_scheme)) -> User:
    """Dependency untuk mengambil data user yang sedang login berdasarkan JWT Token"""
    return await _authenticate(db, token)


# Cache user per proses untuk get_current_user_released: {user_id: (kedaluwarsa_monotonic, User terlepas)}.
_user_cache: dict[str, tuple[float, User]] = {}
_user_cache_lock = threading.Lock()
_USER_CACHE_MAX = 5000


def _cached_user(payload: dict) -> User:
    """Cari user di cache; bila tidak ada/kedaluwarsa, baca dari DB (sesi langsung ditutup). SINKRON."""
    user_id = str(payload.get("sub"))
    now = time.monotonic()
    ttl = settings.AUTH_USER_CACHE_SECONDS
    if ttl > 0:
        with _user_cache_lock:
            hit = _user_cache.get(user_id)
        if hit and hit[0] > now:
            return hit[1]
    db = SessionLocal()
    try:
        user = _load_user(db, payload, is_service_token=False, set_actor=False)
        db.expunge(user)
    finally:
        db.close()
    if ttl > 0:
        with _user_cache_lock:
            if len(_user_cache) >= _USER_CACHE_MAX:
                for key in [k for k, (exp, _) in _user_cache.items() if exp <= now] or list(_user_cache)[:500]:
                    _user_cache.pop(key, None)
            _user_cache[user_id] = (now + ttl, user)
    return user


def clear_user_cache() -> None:
    with _user_cache_lock:
        _user_cache.clear()


async def get_current_user_released(token: str | None = Depends(oauth2_scheme)) -> User:
    """
    Untuk endpoint bervolume tinggi yang lama menunggu layanan luar (ubin foto udara): tidak memegang koneksi DB
    selama request, dan status user di-cache AUTH_USER_CACHE_SECONDS per proses, sehingga satu layar peta
    (puluhan ubin) tidak menjadi puluhan query ke DB/PgBouncer. Sesi (logout/revoke) tetap dicek di Redis setiap
    request; user yang dinonaktifkan admin tertolak paling lambat setelah TTL cache. Hanya token user biasa
    (token layanan sudah ditolak oleh _decode_token karena endpoint ini tanpa scope). User yang dikembalikan
    terlepas dari sesi DB (jangan memuat relasi lazy darinya).
    """
    payload, _ = _decode_token(token, None)
    user = await run_in_threadpool(_cached_user, payload)
    await _check_session(payload)
    return user


# CATATAN (Nov 2026): POST /pokok-produksi/import-json kini tanpa autentikasi, sehingga token akun layanan
# (user_or_service / CanImportProduksiJson, scope produksi_tbs:import) tidak dipakai endpoint mana pun lagi.
# Fitur sengaja dibiarkan (model, endpoint user, kolom migrasi 006) agar mudah diaktifkan kembali:
# cukup pasang lagi `user: CanImportProduksiJson` di endpoint tersebut.
def user_or_service(scope: str):
    """Dependency: user login biasa, atau akun layanan yang tokennya memuat `scope`."""
    async def dependency(db: Session = Depends(get_db),
                   credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User:
        return await _authenticate(db, credentials.credentials if credentials else None, scope)
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

    async def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        # Sinkron (query + relasi lazy) -> threadpool agar event loop tidak ikut menunggu DB.
        if not await run_in_threadpool(user_has_permission, db, current_user, self.required_permission):
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
