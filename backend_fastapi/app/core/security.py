from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jwt import encode, decode, PyJWTError
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

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """Membuat JWT Access Token untuk user yang berhasil login"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Payload token (menyimpan 'sub' berupa user_id atau username)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

SERVICE_TOKEN_TYPE = "service"
SCOPE_PRODUKSI_IMPORT = "produksi_tbs:import"


def create_service_token(user_id: Any, token_version: int, expires_at: datetime, scopes: list[str]) -> str:
    """JWT akun layanan: hanya berlaku di endpoint yang meminta salah satu scope-nya."""
    payload = {"sub": str(user_id), "typ": SERVICE_TOKEN_TYPE, "scope": scopes, "tv": token_version,
               "exp": expires_at}
    return encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
