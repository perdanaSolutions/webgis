from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.api import deps
from app.models.auth import Role, Permission
from app.schemas.role import RoleCreate, RoleResponse
from app.models.akses import LogAksesMenu, LogAksesData, LogAksesTransaksi
from app.services import access_service

router = APIRouter()


def _scope_rows(db: Session, roles: list[Role]) -> list[dict]:
    """Scope wilayah dari auth.role_data_scopes. Ekspansi kode dipakai bila view-nya ada."""
    role_ids = [role.id for role in roles]
    if not role_ids:
        return []
    try:
        with db.begin_nested():
            return access_service.expanded_scopes(db, role_ids)
    except Exception:
        rows = db.execute(
            text(
                """
                SELECT id, role_id, created_at,
                       CASE
                         WHEN division_id IS NOT NULL THEN 'division'
                         WHEN estate_id IS NOT NULL THEN 'estate'
                         WHEN company_id IS NOT NULL THEN 'company'
                         ELSE 'area'
                       END AS level,
                       NULL::text AS area_code,
                       NULL::text AS company_code,
                       NULL::text AS estate_code,
                       NULL::text AS division_code
                FROM auth.role_data_scopes
                WHERE role_id = ANY(CAST(:role_ids AS uuid[]))
                """
            ),
            {"role_ids": [str(role_id) for role_id in role_ids]},
        ).mappings()
        return [dict(row) for row in rows]


def _serialize_roles(db: Session, roles: list[Role]) -> list[dict]:
    """Baca hak akses dari tabel v3, bukan log_akses_* yang sudah tidak ada."""
    scopes = _scope_rows(db, roles)
    scopes_by_role: dict[str, list[dict]] = {}
    for row in scopes:
        scopes_by_role.setdefault(str(row["role_id"]), []).append(row)

    return [
        {
            "id": role.id,
            "nama": role.nama,
            "deskripsi": role.deskripsi,
            "created_at": role.created_at,
            "akses_menu": access_service.role_menu_rows(db, role.id),
            "akses_data": access_service.scopes_as_log_rows(scopes_by_role.get(str(role.id), [])),
            "akses_transaksi": access_service.role_transaction_rows(db, role.id),
        }
        for role in roles
    ]


# 1. GET ALL ROLES (Hanya untuk yang punya hak kelola user/role)
@router.get("/", response_model=List[RoleResponse])
def get_all_roles(
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    """Mengambil semua daftar role beserta hak akses menu, data, dan transaksi."""
    roles = db.query(Role).order_by(Role.created_at).all()
    return _serialize_roles(db, roles)

@router.get("/{role_id}", response_model=RoleResponse)
def get_role_by_id(
    role_id: UUID,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user)
):
    """
    Mengambil data detail satu Role berdasarkan ID-nya
    beserta konfigurasi hak akses menu, data, dan transaksinya.
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role dengan ID {role_id} tidak ditemukan"
        )
        
    return _serialize_roles(db, [role])[0]


# 2. CREATE NEW ROLE
@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user) # Proteksi Login
):
    """Membuat role baru beserta konfigurasi Akses Menu, Data GIS, dan Transaksi."""
    # 1. Cek apakah nama role sudah terpakai
    existing_role = db.query(Role).filter(Role.nama == payload.nama.lower()).first()
    if existing_role:
        raise HTTPException(status_code=400, detail=f"Role dengan nama '{payload.nama}' sudah ada.")

    # 2. Buat objek role baru
    new_role = Role(
        nama=payload.nama,
        deskripsi=payload.deskripsi
    )
    db.add(new_role)
    db.flush() # Flush untuk mendapatkan new_role.id (UUID) sebelum di-commit

    role_id_str = str(new_role.id)

    # 3. Simpan Akses Menu (jika ada)
    if payload.akses_menu:
        for menu_id in payload.akses_menu:
            db.add(LogAksesMenu(role_id=role_id_str, menu_id=menu_id))

    # 4. Simpan Akses Data GIS (jika ada)
    if payload.akses_data:
        for item_data in payload.akses_data:
            # Skenario jika frontend mengirimkan list afdeling/area di dalam item_data
            if item_data.kode_afd:
                base_area = item_data.kode_area[0] if (item_data.kode_area and len(item_data.kode_area) > 0) else None
                for afd in item_data.kode_afd:
                    db.add(LogAksesData(
                        role_id=role_id_str,
                        kode_pt=item_data.kode_pt,
                        kode_est=item_data.kode_est,
                        kode_area=base_area,
                        kode_afd=afd
                    ))
            elif item_data.kode_area:
                for area in item_data.kode_area:
                    db.add(LogAksesData(
                        role_id=role_id_str,
                        kode_pt=item_data.kode_pt,
                        kode_est=item_data.kode_est,
                        kode_area=area,
                        kode_afd=None
                    ))
            else:
                db.add(LogAksesData(
                    role_id=role_id_str,
                    kode_pt=item_data.kode_pt,
                    kode_est=item_data.kode_est,
                    kode_area=None,
                    kode_afd=None
                ))

    # 5. Simpan Akses Transaksi (jika ada)
    if payload.akses_transaksi:
        for table_name in payload.akses_transaksi:
            db.add(LogAksesTransaksi(role_id=role_id_str, nama_table_transaksi=table_name))

    db.commit()
    db.refresh(new_role)
    return _serialize_roles(db, [new_role])[0]


# ----------------------------------------------------
# 2. UPDATE ROLE (Sinkronisasi Ulang Akses)
# ----------------------------------------------------
@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    payload: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_user) # Proteksi Login
):
    """Mengubah data role dan melakukan SINKRONISASI ULANG seluruh konfigurasi hak akses."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role tidak ditemukan")

    if role.nama == "superadmin":
        raise HTTPException(status_code=400, detail="Role bawaan 'superadmin' tidak boleh dimodifikasi")

    role.nama = payload.nama.lower()
    role.deskripsi = payload.deskripsi

    role_id_str = str(role.id)

    # ------------------------------------------------------------------
    # SINKRONISASI (Hapus akses lama lalu timpa dengan konfigurasi baru)
    # ------------------------------------------------------------------
    
    # Hanya sinkronkan akses yang benar-benar dikirim. Default kosong bukan perintah hapus.
    sent = payload.model_fields_set

    # 1. Update Akses Menu
    if "akses_menu" in sent and payload.akses_menu is not None:
        db.query(LogAksesMenu).filter(LogAksesMenu.role_id == role_id_str).delete(synchronize_session=False)
        for menu_id in payload.akses_menu:
            db.add(LogAksesMenu(role_id=role_id_str, menu_id=menu_id))

    # 2. Update Akses Data GIS
    if "akses_data" in sent and payload.akses_data is not None:
        db.query(LogAksesData).filter(LogAksesData.role_id == role_id_str).delete(synchronize_session=False)
        for item_data in payload.akses_data:
            if item_data.kode_afd:
                base_area = item_data.kode_area[0] if (item_data.kode_area and len(item_data.kode_area) > 0) else None
                for afd in item_data.kode_afd:
                    db.add(LogAksesData(
                        role_id=role_id_str,
                        kode_pt=item_data.kode_pt,
                        kode_est=item_data.kode_est,
                        kode_area=base_area,
                        kode_afd=afd
                    ))
            elif item_data.kode_area:
                for area in item_data.kode_area:
                    db.add(LogAksesData(
                        role_id=role_id_str,
                        kode_pt=item_data.kode_pt,
                        kode_est=item_data.kode_est,
                        kode_area=area,
                        kode_afd=None
                    ))
            else:
                db.add(LogAksesData(
                    role_id=role_id_str,
                    kode_pt=item_data.kode_pt,
                    kode_est=item_data.kode_est,
                    kode_area=None,
                    kode_afd=None
                ))

    # 3. Update Akses Transaksi
    if "akses_transaksi" in sent and payload.akses_transaksi is not None:
        db.query(LogAksesTransaksi).filter(LogAksesTransaksi.role_id == role_id_str).delete(synchronize_session=False)
        for table_name in payload.akses_transaksi:
            db.add(LogAksesTransaksi(role_id=role_id_str, nama_table_transaksi=table_name))

    db.commit()
    db.refresh(role)
    return _serialize_roles(db, [role])[0]