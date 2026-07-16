from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Import dependensi database
from app.api import deps  

# Import langsung secara spesifik ke file masing-masing untuk menghindari AttributeError
from app.models import akses as models
from app.schemas import akses as schemas

router = APIRouter()

# ==========================================
# 1. CRUD: LOG AKSES MENU
# ==========================================

@router.post("/menu", response_model=schemas.LogAksesMenuResponse, status_code=status.HTTP_201_CREATED)
def create_akses_menu(payload: schemas.LogAksesMenuCreate, db: Session = Depends(deps.get_db)):
    """Tambah hak akses menu untuk user tertentu."""
    db_akses = models.LogAksesMenu(
        user_id=payload.user_id,
        menu_id=payload.menu_id
    )
    db.add(db_akses)
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.put("/menu/{log_id}", response_model=schemas.LogAksesMenuResponse)
def update_akses_menu(log_id: int, payload: schemas.LogAksesMenuUpdate, db: Session = Depends(deps.get_db)):
    """Update hak akses menu berdasarkan ID log."""
    db_akses = db.query(models.LogAksesMenu).filter(models.LogAksesMenu.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses menu tidak ditemukan")
    
    # Konversi payload ke dictionary dan buang data yang bernilai None
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_akses, key, value)
        
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.get("/menu/user/{user_id}", response_model=List[schemas.LogAksesMenuResponse])
def get_user_akses_menu(user_id: str, db: Session = Depends(deps.get_db)):
    """Mendapatkan semua daftar menu yang boleh diakses oleh user tertentu."""
    return db.query(models.LogAksesMenu).filter(models.LogAksesMenu.user_id == user_id).all()

@router.delete("/menu/{log_id}", status_code=status.HTTP_200_OK)
def delete_akses_menu(log_id: int, db: Session = Depends(deps.get_db)):
    """Hapus hak akses menu berdasarkan ID log."""
    db_akses = db.query(models.LogAksesMenu).filter(models.LogAksesMenu.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses menu tidak ditemukan")
    db.delete(db_akses)
    db.commit()
    return {"message": f"Berhasil menghapus hak akses menu ID {log_id}"}


# ==========================================
# 2. CRUD: LOG AKSES DATA (GIS Wilayah)
# ==========================================

@router.post("/data", response_model=schemas.LogAksesDataResponse, status_code=status.HTTP_201_CREATED)
def create_akses_data(payload: schemas.LogAksesDataCreate, db: Session = Depends(deps.get_db)):
    """Tambah hak akses wilayah (Perusahaan/Estate) untuk user tertentu."""
    db_akses = models.LogAksesData(
        user_id=payload.user_id,
        kode_pt=payload.kode_pt,
        kode_est=payload.kode_est
    )
    db.add(db_akses)
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.put("/data/{log_id}", response_model=schemas.LogAksesDataResponse)
def update_akses_data(log_id: int, payload: schemas.LogAksesDataUpdate, db: Session = Depends(deps.get_db)):
    """Update hak akses wilayah (kode_pt / kode_est) berdasarkan ID log."""
    db_akses = db.query(models.LogAksesData).filter(models.LogAksesData.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses data tidak ditemukan")
    
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_akses, key, value)
        
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.get("/data/user/{user_id}", response_model=List[schemas.LogAksesDataResponse])
def get_user_akses_data(user_id: str, db: Session = Depends(deps.get_db)):
    """Mendapatkan daftar wilayah GIS yang boleh diakses oleh user tertentu."""
    return db.query(models.LogAksesData).filter(models.LogAksesData.user_id == user_id).all()

@router.delete("/data/{log_id}", status_code=status.HTTP_200_OK)
def delete_akses_data(log_id: int, db: Session = Depends(deps.get_db)):
    """Hapus hak akses data wilayah berdasarkan ID log."""
    db_akses = db.query(models.LogAksesData).filter(models.LogAksesData.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses data tidak ditemukan")
    db.delete(db_akses)
    db.commit()
    return {"message": f"Berhasil menghapus hak akses data ID {log_id}"}


# ==========================================
# 3. CRUD: LOG AKSES TRANSAKSI
# ==========================================

@router.post("/transaksi", response_model=schemas.LogAksesTransaksiResponse, status_code=status.HTTP_201_CREATED)
def create_akses_transaksi(payload: schemas.LogAksesTransaksiCreate, db: Session = Depends(deps.get_db)):
    """Tambah hak akses tabel transaksi untuk user tertentu."""
    db_akses = models.LogAksesTransaksi(
        user_id=payload.user_id,
        nama_table_transaksi=payload.nama_table_transaksi
    )
    db.add(db_akses)
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.put("/transaksi/{log_id}", response_model=schemas.LogAksesTransaksiResponse)
def update_akses_transaksi(log_id: int, payload: schemas.LogAksesTransaksiUpdate, db: Session = Depends(deps.get_db)):
    """Update hak akses tabel transaksi berdasarkan ID log."""
    db_akses = db.query(models.LogAksesTransaksi).filter(models.LogAksesTransaksi.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses transaksi tidak ditemukan")
    
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_akses, key, value)
        
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.get("/transaksi/user/{user_id}", response_model=List[schemas.LogAksesTransaksiResponse])
def get_user_akses_transaksi(user_id: str, db: Session = Depends(deps.get_db)):
    """Mendapatkan daftar tabel transaksi yang boleh diakses oleh user tertentu."""
    return db.query(models.LogAksesTransaksi).filter(models.LogAksesTransaksi.user_id == user_id).all()

@router.delete("/transaksi/{log_id}", status_code=status.HTTP_200_OK)
def delete_akses_transaksi(log_id: int, db: Session = Depends(deps.get_db)):
    """Hapus hak akses tabel transaksi berdasarkan ID log."""
    db_akses = db.query(models.LogAksesTransaksi).filter(models.LogAksesTransaksi.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses transaksi tidak ditemukan")
    db.delete(db_akses)
    db.commit()
    return {"message": f"Berhasil menghapus hak akses transaksi ID {log_id}"}