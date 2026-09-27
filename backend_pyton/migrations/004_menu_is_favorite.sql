-- Penanda menu favorit global. Tampil untuk semua user yang punya akses role ke menu itu.
-- Aman dijalankan berulang kali.

ALTER TABLE auth.menus ADD COLUMN IF NOT EXISTS is_favorite boolean NOT NULL DEFAULT false;
