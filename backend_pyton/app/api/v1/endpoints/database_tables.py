from fastapi import APIRouter, Depends
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from typing import List

from app.api import deps

router = APIRouter()

@router.get("/tables", response_model=List[str])
def get_database_tables(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    """
    Mengambil semua daftar nama tabel yang ada di dalam schema 'public' database.
    Berguna untuk opsi pilihan Hak Akses Transaksi di Frontend.
    """
    # 1. Dapatkan object engine dari koneksi DB session saat ini
    engine = db.get_bind()
    
    # 2. Inisialisasi SQLAlchemy Inspector untuk membaca metadata database
    inspector = inspect(engine)
    
    # 3. Ambil semua nama tabel yang berada di dalam schema 'public'
    tables = inspector.get_table_names(schema="public")
    
    # Optional: Jika ingin menyaring (filter) tabel bawaan sistem agar tidak muncul di pilihan UI
    # Misalnya, kita tidak ingin tabel migrasi (alembic) atau tabel log akses itu sendiri muncul di pilihan:
    ignored_tables = {
        "alembic_version", 
        "log_akses_menu", 
        "log_akses_data", 
        "log_akses_transaksi", 
        "log_akses_transaksi", 
        "permissions", "roles", "role_permissions",
        "spatial_ref_sys", 
        "afdeling", "blok", "estate", "menus", "perusahaan", "spatial_ref_sys", "sys_upload_log",
        "user_activity_log", "users"
    }
    filtered_tables = [table for table in tables if table not in ignored_tables]
    
    # Urutkan abjad agar rapi di UI
    filtered_tables.sort()
    
    return filtered_tables