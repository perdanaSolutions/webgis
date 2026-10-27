-- 020: email user unik tanpa membedakan huruf besar/kecil (lower(email)).
-- Aplikasi sudah menyimpan email dalam huruf kecil dan mengecek duplikat; index ini menutup race condition.
-- Per 28-10-2026: 0 grup email duplikat (case-insensitive) di gis_db_v4 dan db_uat_v1.
-- Idempoten. Tidak mengubah/menghapus data.
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_key ON auth.users (lower(email));
