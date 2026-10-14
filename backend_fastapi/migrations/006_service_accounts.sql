-- Akun layanan (service account): dipakai sistem lain lewat Bearer token berumur panjang.
--   is_service_account : akun tidak bisa login biasa; hanya token layanan yang diterbitkan admin.
--   token_expires_at   : kedaluwarsa token layanan terakhir (informasi untuk admin).
--   token_version      : dinaikkan saat token diterbitkan ulang, sehingga token lama otomatis tidak berlaku.
-- Aman dijalankan berulang kali.

ALTER TABLE auth.users
    ADD COLUMN IF NOT EXISTS is_service_account BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS token_expires_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS token_version      INTEGER NOT NULL DEFAULT 1;
