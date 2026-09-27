# from datetime import timedelta
from datetime import timedelta, datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import bindparam, or_, text
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.models.auth import User, UserActivityLog
from app.schemas.user import UserLoginRequest

import jwt

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/swagger-form")

# =====================================================================
# 1. ENDPOINT LOGIN UTAMA - KHUSUS FRONTEND (Menerima JSON murni)
# =====================================================================
@router.post("/login")
def login_access_token_fe(
    payload: UserLoginRequest,  # Murni membaca JSON {"email": "...", "password": "..."}
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Endpoint login utama untuk Frontend Website (React/Vue/Next.js).
    Menerima JSON body dengan property 'email' dan 'password'.
    """
    return process_user_login(db, input_identifier=payload.email, input_password=payload.password)


# =====================================================================
# 2. ENDPOINT LOGIN CADANGAN - KHUSUS SWAGGER UI (Menerima Form-Data)
# =====================================================================
@router.post("/login/swagger-form", include_in_schema=True)
def login_access_token_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(), # Murni membaca Form-Data bawaan gembok
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Endpoint khusus menjembatani fitur gembok 'Authorize' Swagger UI agar tidak error.
    """
    return process_user_login(db, input_identifier=form_data.username, input_password=form_data.password)


def _role_ids(user: User) -> list:
    return [role.id for role in user.roles]


def _akses_menu(db: Session, role_ids: list) -> list[str]:
    if not role_ids:
        return []
    stmt = text(
        """
        SELECT DISTINCT menu_id::text AS menu_id
        FROM auth.role_menus
        WHERE role_id::text IN :role_ids
        """
    ).bindparams(bindparam("role_ids", expanding=True))
    rows = db.execute(stmt, {"role_ids": [str(role_id) for role_id in role_ids]}).all()
    return [row.menu_id for row in rows]


def _akses_data(db: Session, role_ids: list) -> list[dict]:
    if not role_ids:
        return []
    stmt = text(
        """
        SELECT
            a.code AS kode_area,
            COALESCE(c_direct.code, c_via_estate.code, c_via_div.code) AS kode_pt,
            COALESCE(e_direct.code, e_via_div.code) AS kode_est,
            d.code AS kode_afd
        FROM auth.role_data_scopes AS s
        LEFT JOIN master.areas AS a ON a.id = s.area_id
        LEFT JOIN master.companies AS c_direct ON c_direct.id = s.company_id
        LEFT JOIN master.estates AS e_direct ON e_direct.id = s.estate_id
        LEFT JOIN master.companies AS c_via_estate ON c_via_estate.id = e_direct.company_id
        LEFT JOIN master.divisions AS d ON d.id = s.division_id
        LEFT JOIN master.estates AS e_via_div ON e_via_div.id = d.estate_id
        LEFT JOIN master.companies AS c_via_div ON c_via_div.id = e_via_div.company_id
        WHERE s.role_id::text IN :role_ids
        """
    ).bindparams(bindparam("role_ids", expanding=True))
    rows = db.execute(stmt, {"role_ids": [str(role_id) for role_id in role_ids]}).mappings().all()
    return [
        {
            "kode_pt": row["kode_pt"],
            "kode_est": row["kode_est"],
            "kode_area": row["kode_area"],
            "kode_afd": row["kode_afd"],
        }
        for row in rows
    ]


def _session_user(db: Session, user: User) -> dict:
    role_ids = _role_ids(user)
    role_names = [role.nama for role in user.roles]
    primary_role = user.role
    return {
        "id": str(user.id),
        "username": user.username,
        "nama_lengkap": user.nama_lengkap,
        "email": user.email,
        "roles": role_names,
        "role": primary_role.nama if primary_role else None,
        "role_id": str(primary_role.id) if primary_role else None,
        "akses_menu": _akses_menu(db, role_ids),
        "akses_data": _akses_data(db, role_ids),
        "akses_transaksi": [],
    }


# =====================================================================
# 3. FUNGSI LOGIKA LOGIN (Reusable Function)
# =====================================================================
def process_user_login(db: Session, input_identifier: str, input_password: str) -> Any:
    # Ambil user dari database (Bisa pakai Username maupun Email)
    user = db.query(User).filter(
        or_(
            User.username == input_identifier,
            User.email == input_identifier
        )
    ).first()
    
    # Validasi kecocokan password
    if not user or not security.verify_password(input_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "errors": [
                    {
                        "type": "invalid_credentials",
                        "field": "auth",
                        "msg": "Username, email atau password yang Anda masukkan salah",
                        "input": None
                    }
                ]
            }
        )
        
    # Buat JWT Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )

    # Catat log aktivitas sukses login
    primary_role = user.role
    log_sukses = UserActivityLog(
        user_id=user.id,
        aksi="LOGIN",
        resource="auth",
        status="SUCCESS",
        detail={
            "nama_lengkap": user.nama_lengkap,
            "role_id": str(primary_role.id) if primary_role else None,
        },
    )
    db.add(log_sukses)
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _session_user(db, user),
    }

@router.get("/me")
def get_user_me(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Mengambil informasi profil user yang sedang aktif berdasarkan token JWT.
    Berguna untuk menjaga sesi login saat halaman web di-refresh.
    """
    return _session_user(db, current_user)

@router.get("/check-token")
def check_token_validity(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    token: str = Depends(oauth2_scheme) 
) -> Any:
    """
    Endpoint untuk mengecek masa berlaku token yang sedang digunakan saat ini.
    """
    try:
        # (Sisa kode ke bawah seperti decode token, hitung sisa waktu, dst. tetap SAMA)
        payload = jwt.decode(token, options={"verify_signature": False})
        
        exp_timestamp = payload.get("exp")
        iat_timestamp = payload.get("iat")
        
        if not exp_timestamp:
            return {"status": "error", "message": "Token tidak memiliki klaim kedaluwarsa (exp)"}

        waktu_sekarang = datetime.now(timezone.utc)
        waktu_expired = datetime.fromtimestamp(exp_timestamp, timezone.utc)
        waktu_terbit = datetime.fromtimestamp(iat_timestamp, timezone.utc) if iat_timestamp else None
        
        sisa_waktu = waktu_expired - waktu_sekarang
        sisa_detik = int(sisa_waktu.total_seconds())
        
        if sisa_detik > 0:
            hari = sisa_detik // 86400
            jam = (sisa_detik % 86400) // 3600
            menit = (sisa_detik % 3600) // 60
            string_sisa = f"{hari} hari, {jam} jam, {menit} menit"
            is_expired = False
        else:
            string_sisa = "Token sudah kedaluwarsa"
            is_expired = True

        return {
            "status": "success",
            "is_expired": is_expired,
            "konfigurasi_sistem_menit": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "waktu_terbit_server": waktu_terbit.isoformat() if waktu_terbit else None,
            "waktu_expired_server": waktu_expired.isoformat(),
            "waktu_sekarang_server": waktu_sekarang.isoformat(),
            "sisa_waktu_aktif": string_sisa,
            "user": {
                "username": current_user.username,
                "nama_lengkap": current_user.nama_lengkap
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membedah token: {str(e)}")

@router.post("/logout")
def logout(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user) # Wajib bawa token aktif untuk logout
):
    """
    Endpoint Logout untuk mencatat log aktivitas keluar sistem.
    Frontend tetap harus menghapus token dari localStorage setelah menembak API ini.
    """
    log_logout = UserActivityLog(
        user_id=current_user.id,
        aksi="LOGOUT",
        resource="auth",
        status="SUCCESS",
        detail={"nama_lengkap": current_user.nama_lengkap}
    )
    db.add(log_logout)
    db.commit()
    
    return {"message": "Berhasil logout dari sistem, aktivitas telah dicatat."}