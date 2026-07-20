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
def create_akses_menu(
    payload: schemas.LogAksesMenuCreate, 
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    """Tambah hak akses menu untuk role tertentu."""
    db_akses = models.LogAksesMenu(
        role_id=payload.role_id,
        menu_id=payload.menu_id
    )
    db.add(db_akses)
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.put("/menu/{log_id}", response_model=schemas.LogAksesMenuResponse)
def update_akses_menu(log_id: int, payload: schemas.LogAksesMenuUpdate, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
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

@router.get("/menu/role/{role_id}", response_model=List[schemas.LogAksesMenuResponse])
def get_role_akses_menu(role_id: str, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
    """Mendapatkan semua daftar menu yang boleh diakses oleh role tertentu."""
    return db.query(models.LogAksesMenu).filter(models.LogAksesMenu.role_id == role_id).all()

@router.delete("/menu/{log_id}", status_code=status.HTTP_200_OK)
def delete_akses_menu(log_id: int, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
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

@router.post("/data", status_code=status.HTTP_201_CREATED)
def create_akses_data(
    payload: schemas.LogAksesDataCreate, 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
    """Tambah hak akses wilayah (PT, Estate, Area, Afdeling). Mampu menangani multi area/afd."""
    inserted_logs = []

    # Skenario 1: Jika frontend mengirimkan list afdeling
    if payload.kode_afd:
        # Ambil nilai dasar kode_area dari array input (jika dikirim dalam bentuk list oleh frontend)
        base_area = payload.kode_area[0] if (payload.kode_area and len(payload.kode_area) > 0) else None
        
        for afd in payload.kode_afd:
            db_akses = models.LogAksesData(
                role_id=payload.role_id,
                kode_pt=payload.kode_pt,
                kode_est=payload.kode_est,   # Mengambil "E004" langsung dari string payload
                kode_area=base_area,         # Mengambil "BER" dari list payload.kode_area
                kode_afd=afd                 # Mengambil "AFDI01" dari list perulangan
            )
            db.add(db_akses)
            inserted_logs.append(db_akses)

    # Skenario 2: Jika hanya mengirimkan list area tanpa afdeling
    elif payload.kode_area:
        for area in payload.kode_area:
            db_akses = models.LogAksesData(
                role_id=payload.role_id,
                kode_pt=payload.kode_pt,
                kode_est=payload.kode_est,
                kode_area=area,
                kode_afd=None
            )
            db.add(db_akses)
            inserted_logs.append(db_akses)

    # Skenario 3: Jika hanya memberikan akses di tingkat PT saja
    else:
        db_akses = models.LogAksesData(
            role_id=payload.role_id,
            kode_pt=payload.kode_pt,
            kode_est=payload.kode_est, # Tetap simpan jika ada, atau None jika tidak dikirim
            kode_area=None,
            kode_afd=None
        )
        db.add(db_akses)
        inserted_logs.append(db_akses)
    
    db.commit()
    return {"message": f"Berhasil menambahkan {len(inserted_logs)} hak akses wilayah terbaru ke database"}


@router.put("/data/{log_id}", response_model=schemas.LogAksesDataResponse)
def update_akses_data(
    log_id: int, 
    payload: schemas.LogAksesDataUpdate, 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
    """Update hak akses wilayah (kode_pt / kode_area / kode_afd) berdasarkan ID log."""
    db_akses = db.query(models.LogAksesData).filter(models.LogAksesData.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses data tidak ditemukan")
    
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_akses, key, value)
        
    db.commit()
    db.refresh(db_akses)
    return db_akses


@router.get("/data/role/{role_id}", response_model=List[schemas.LogAksesDataResponse])
def get_role_akses_data(
    role_id: str, 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
    """Mendapatkan daftar wilayah GIS (PT/Area/Afdeling) yang boleh diakses oleh role tertentu."""
    return db.query(models.LogAksesData).filter(models.LogAksesData.role_id == role_id).all()


@router.delete("/data/{log_id}", status_code=status.HTTP_200_OK)
def delete_akses_data(
    log_id: int, 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
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
def create_akses_transaksi(payload: schemas.LogAksesTransaksiCreate, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
    """Tambah hak akses tabel transaksi untuk role tertentu."""
    db_akses = models.LogAksesTransaksi(
        role_id=payload.role_id,
        nama_table_transaksi=payload.nama_table_transaksi
    )
    db.add(db_akses)
    db.commit()
    db.refresh(db_akses)
    return db_akses

@router.put("/transaksi/{log_id}", response_model=schemas.LogAksesTransaksiResponse)
def update_akses_transaksi(log_id: int, payload: schemas.LogAksesTransaksiUpdate, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
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

@router.get("/transaksi/role/{role_id}", response_model=List[schemas.LogAksesTransaksiResponse])
def get_role_akses_transaksi(role_id: str, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
    """Mendapatkan daftar tabel transaksi yang boleh diakses oleh role tertentu."""
    return db.query(models.LogAksesTransaksi).filter(models.LogAksesTransaksi.role_id == role_id).all()

@router.delete("/transaksi/{log_id}", status_code=status.HTTP_200_OK)
def delete_akses_transaksi(log_id: int, db: Session = Depends(deps.get_db), current_user = Depends(deps.get_current_user)):
    """Hapus hak akses tabel transaksi berdasarkan ID log."""
    db_akses = db.query(models.LogAksesTransaksi).filter(models.LogAksesTransaksi.id == log_id).first()
    if not db_akses:
        raise HTTPException(status_code=404, detail="Log akses transaksi tidak ditemukan")
    db.delete(db_akses)
    db.commit()
    return {"message": f"Berhasil menghapus hak akses transaksi ID {log_id}"}