import os
import sys
from uuid import uuid4

# Daftarkan path agar python bisa mendeteksi folder 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.auth import Role, Permission, User


def seed_data():
    db = SessionLocal()
    try:
        print("====== MEMULAI SEEDING DATA AUTHENTIKASI ======")

        # 1. Ambil nilai credential superadmin dari .env via settings
        seed_admin_username = settings.SEED_ADMIN_USERNAME
        seed_admin_email = settings.SEED_ADMIN_EMAIL
        seed_admin_password = settings.SEED_ADMIN_PASSWORD

        # 2. Daftar Permission Bawaan
        permissions_data = [
            {"resource": "blok", "aksi": "read", "deskripsi": "Melihat data blok"},
            {"resource": "blok", "aksi": "write", "deskripsi": "Menambah/mengubah data blok"},
            {"resource": "blok", "aksi": "delete", "deskripsi": "Menghapus data blok"},
            {"resource": "produksi", "aksi": "read", "deskripsi": "Melihat data produksi"},
            {"resource": "produksi", "aksi": "write", "deskripsi": "Menginput data produksi"},
            {"resource": "user", "aksi": "read", "deskripsi": "Melihat data user"},
            {"resource": "user", "aksi": "write", "deskripsi": "Mengelola data user"},
        ]

        inserted_permissions = {}
        for p in permissions_data:
            kode = f"{p['resource']}:{p['aksi']}"
            # Cek apakah permission sudah ada
            permission = db.query(Permission).filter(Permission.kode == kode).first()
            if not permission:
                permission = Permission(
                    id=uuid4(),
                    kode=kode,
                    resource=p["resource"],
                    aksi=p["aksi"],
                    deskripsi=p["deskripsi"]
                )
                db.add(permission)
                print(f"✓ Permission dibuat: {kode}")
            inserted_permissions[kode] = permission
        
        db.commit()

        # 3. Daftar Role Bawaan
        roles_data = [
            {"nama": "superadmin", "deskripsi": "Akses penuh semua fitur & semua area"},
            {"nama": "admin", "deskripsi": "Kelola user & data, scope area tertentu"},
            {"nama": "manager", "deskripsi": "Lihat semua data, input produksi & cuaca"},
            {"nama": "surveyor", "deskripsi": "Input data survei lapangan"},
            {"names": "viewer", "deskripsi": "Read-only, hanya melihat laporan & peta"},
        ]

        inserted_roles = {}
        for r in roles_data:
            role = db.query(Role).filter(Role.nama == r["nama"]).first()
            if not role:
                role = Role(
                    id=uuid4(),
                    nama=r["nama"],
                    deskripsi=r["deskripsi"]
                )
                db.add(role)
                print(f"✓ Role dibuat: {r['nama']}")
            inserted_roles[r["nama"]] = role
        
        db.commit()

        # 4. Hubungkan Semua Permission ke Superadmin (Many-to-Many)
        superadmin_role = inserted_roles["superadmin"]
        # Kosongkan dulu relasi lama agar tidak duplikat saat skrip dijalankan ulang
        superadmin_role.permissions = []
        for perm in inserted_permissions.values():
            superadmin_role.permissions.append(perm)
        
        db.commit()
        print("✓ Seluruh permission telah dihubungkan ke Role superadmin")

        # 5. Buat Akun Superadmin Pertama berdasarkan data dari .env
        admin_user = db.query(User).filter(User.username == seed_admin_username).first()
        
        if not admin_user:
            admin_user = User(
                id=uuid4(),
                role_id=superadmin_role.id,
                nama_lengkap="Super Administrator",
                username=seed_admin_username,
                email=seed_admin_email,
                hashed_password=get_password_hash(seed_admin_password), 
                is_active=True
            )
            db.add(admin_user)
            print(f"✓ User Akun Utama Berhasil Dibuat!")
            print(f"  -> Username: {seed_admin_username}")
            print(f"  -> Email   : {seed_admin_email}")
            print(f"  -> Password: {seed_admin_password}")
        else:
            print(f"i User dengan username '{seed_admin_username}' sudah ada di database.")

        db.commit()
        print("====== SEEDING AUTH BERHASIL SELESAI ======")

    except Exception as e:
        db.rollback()
        print(f"❌ Terjadi kesalahan saat seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()