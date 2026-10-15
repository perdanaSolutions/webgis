-- Penguncian akun akibat salah password berulang kali.
--   failed_login_attempts : jumlah salah password berturut-turut (di-reset saat login berhasil / dibuka kuncinya).
--   locked_at             : waktu akun terkunci; NULL berarti tidak terkunci. Dibuka oleh admin (PUT /users/{id} is_locked=false).
-- Aman dijalankan berulang kali.

ALTER TABLE auth.users
    ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_at             TIMESTAMPTZ;
