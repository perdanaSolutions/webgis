from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from uuid import uuid4

from jwt import encode
from passlib.context import CryptContext

from app.core.config import settings

# Mengatur passlib untuk menggunakan algoritma bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Memverifikasi apakah password input cocok dengan password ter-hash di DB"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Mengubah password teks biasa menjadi hash bcrypt sebelum disimpan ke DB"""
    return pwd_context.hash(password)

def create_access_token(
    subject: Union[str, Any],
    expires_delta: timedelta = None,
    jti: Optional[str] = None,
) -> str:
    """JWT access user: sub + exp + jti (+ iat). jti dipakai registry Redis (ADR-001)."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        "jti": jti or str(uuid4()),
    }
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

SERVICE_TOKEN_TYPE = "service"
SCOPE_PRODUKSI_IMPORT = "produksi_tbs:import"


def create_service_token(user_id: Any, token_version: int, expires_at: datetime, scopes: list[str]) -> str:
    """JWT akun layanan: hanya berlaku di endpoint yang meminta salah satu scope-nya."""
    payload = {"sub": str(user_id), "typ": SERVICE_TOKEN_TYPE, "scope": scopes, "tv": token_version,
               "exp": expires_at}
    return encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
