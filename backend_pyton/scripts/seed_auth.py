import os
import sys
from uuid import uuid4

# Daftarkan path agar python bisa mendeteksi folder 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.auth import Role, Permission, User


def seed_data():
    db = SessionLocal()
    try:
        print("====== MEMULAI SEEDING DATA AUTHENTIKASI ======")

        # 1. Ambil nilai credential superadmin dari .env (dengan fallback default jika tidak ada)
        SEED_ADMIN_USERNAME = os.getenv("DB_USER", "superadmin")
        SEED_ADMIN_EMAIL = os.getenv("DB_EMAIL", "superadmin@plantation.com")
        SEED_ADMIN_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

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
        admin_user = db.query(User).filter(User.username == SEED_ADMIN_USERNAME).first()
        
        if not admin_user:
            admin_user = User(
                id=uuid4(),
                role_id=superadmin_role.id,
                nama_lengkap="Super Administrator",
                username=SEED_ADMIN_USERNAME,
                email=SEED_ADMIN_EMAIL,
                hashed_password=get_password_hash(SEED_ADMIN_PASSWORD), 
                is_active=True
            )
            db.add(admin_user)
            print(f"✓ User Akun Utama Berhasil Dibuat!")
            print(f"  -> Username: {SEED_ADMIN_USERNAME}")
            print(f"  -> Email   : {SEED_ADMIN_EMAIL}")
            print(f"  -> Password: {SEED_ADMIN_PASSWORD}")
        else:
            print(f"i User dengan username '{SEED_ADMIN_USERNAME}' sudah ada di database.")

        db.commit()
        print("====== SEEDING AUTH BERHASIL SELESAI ======")

    except Exception as e:
        db.rollback()
        print(f"❌ Terjadi kesalahan saat seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()