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

@router.get("/data/role/{role_id}", response_model=List[schemas.AreaTreeSchema])
def get_role_akses_data(
    role_id: str, 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
    """Mendapatkan hak akses wilayah GIS berjenjang (Area -> PT -> Estate -> Afdeling) berdasarkan Role."""
    
    # 1. Ambil semua baris log_akses_data untuk role tersebut
    logs = db.query(models.LogAksesData).filter(models.LogAksesData.role_id == role_id).all()
    if not logs:
        return []

    # 2. Kelompokkan data menggunakan struktur dictionary Python
    tree_map: Dict[str, dict] = {}

    for log in logs:
        area_id = log.kode_area or "UNASSIGNED"
        pt_id = log.kode_pt
        est_id = log.kode_est
        afd_id = log.kode_afd

        # Biarkan nama_xxx sama dengan kode jika belum ada master tabel penamaan
        area_nama = area_id
        pt_nama = pt_id
        est_nama = est_id
        afd_nama = afd_id

        # Layer 1: Area
        if area_id not in tree_map:
            tree_map[area_id] = {
                "id_area": area_id,
                "nama_area": area_nama,
                "perusahaan_map": {}
            }

        # Layer 2: Perusahaan / PT
        pt_map = tree_map[area_id]["perusahaan_map"]
        if pt_id and pt_id not in pt_map:
            pt_map[pt_id] = {
                "id_perusahaan": pt_id,
                "nama_perusahaan": pt_nama,
                "estate_map": {}
            }

        # Layer 3: Estate
        if pt_id and est_id:
            est_map = pt_map[pt_id]["estate_map"]
            if est_id not in est_map:
                est_map[est_id] = {
                    "id_estate": est_id,
                    "nama_estate": est_nama,
                    "afdeling_map": {}
                }

            # Layer 4: Afdeling
            if afd_id:
                afd_map = est_map[est_id]["afdeling_map"]
                if afd_id not in afd_map:
                    afd_map[afd_id] = {
                        "id_afdeling": afd_id,
                        "nama_afdeling": afd_nama
                    }

    # 3. Format ulang dictionary menjadi List/Array JSON sesuai skema Pydantic
    result = []
    for area_id, area_data in tree_map.items():
        perusahaan_list = []
        for pt_id, pt_data in area_data["perusahaan_map"].items():
            estate_list = []
            for est_id, est_data in pt_data["estate_map"].items():
                afdeling_list = list(est_data["afdeling_map"].values())
                estate_list.append({
                    "id_estate": est_data["id_estate"],
                    "nama_estate": est_data["nama_estate"],
                    "afdeling": afdeling_list
                })
            perusahaan_list.append({
                "id_perusahaan": pt_data["id_perusahaan"],
                "nama_perusahaan": pt_data["nama_perusahaan"],
                "estate": estate_list
            })
        result.append({
            "id_area": area_data["id_area"],
            "nama_area": area_data["nama_area"],
            "perusahaan": perusahaan_list
        })

    return result


# ----------------------------------------------------
# 2. POST: Menambah Hak Akses dalam bentuk Hierarki Tree
# ----------------------------------------------------
@router.post("/data/role/{role_id}", status_code=status.HTTP_201_CREATED)
def create_role_akses_data_tree(
    role_id: str,
    payload: List[schemas.AreaTreeSchema], 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
    """Menambahkan data hak akses wilayah berjenjang secara eksplisit."""
    inserted_count = 0

    for area in payload:
        kode_area = area.id_area
        
        # Skenario 1: Hanya level Area
        if not area.perusahaan:
            db.add(models.LogAksesData(
                role_id=role_id, kode_area=kode_area, kode_pt=None, kode_est=None, kode_afd=None
            ))
            inserted_count += 1
            continue

        for pt in area.perusahaan:
            kode_pt = pt.id_perusahaan
            
            # Skenario 2: Sampai level Perusahaan/PT
            if not pt.estate:
                db.add(models.LogAksesData(
                    role_id=role_id, kode_area=kode_area, kode_pt=kode_pt, kode_est=None, kode_afd=None
                ))
                inserted_count += 1
                continue

            for est in pt.estate:
                kode_est = est.id_estate

                # Skenario 3: Sampai level Estate
                if not est.afdeling:
                    db.add(models.LogAksesData(
                        role_id=role_id, kode_area=kode_area, kode_pt=kode_pt, kode_est=kode_est, kode_afd=None
                    ))
                    inserted_count += 1
                    continue

                # Skenario 4: Sampai level Afdeling
                for afd in est.afdeling:
                    db.add(models.LogAksesData(
                        role_id=role_id, kode_area=kode_area, kode_pt=kode_pt, kode_est=kode_est, kode_afd=afd.id_afdeling
                    ))
                    inserted_count += 1

    db.commit()
    return {"message": f"Berhasil menambahkan {inserted_count} record hak akses wilayah"}


# ----------------------------------------------------
# 3. PUT: Sinkronisasi Ulang (Replace All Tree Data)
# ----------------------------------------------------
@router.put("/data/role/{role_id}", response_model=List[schemas.AreaTreeSchema])
def update_role_akses_data_tree(
    role_id: str,
    payload: List[schemas.AreaTreeSchema], 
    db: Session = Depends(deps.get_db), 
    current_user = Depends(deps.get_current_user)
):
    """Melakukan reset/replace total hak akses wilayah untuk role tertentu."""
    
    # 1. Hapus semua hak akses lama milik role ini
    db.query(models.LogAksesData).filter(models.LogAksesData.role_id == role_id).delete(synchronize_session=False)

    # 2. Panggil logika insert data baru
    create_role_akses_data_tree(role_id=role_id, payload=payload, db=db, current_user=current_user)

    # 3. Kembalikan data hierarki terbaru
    return get_role_akses_data(role_id=role_id, db=db, current_user=current_user)


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