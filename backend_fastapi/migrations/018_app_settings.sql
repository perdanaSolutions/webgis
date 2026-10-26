-- Pengaturan aplikasi yang bisa diubah langsung dari database.
-- Aman dijalankan berulang kali (idempotent).
--
-- Mode maintenance:
--   NYALAKAN : UPDATE master.app_settings SET value = 'true',  updated_at = now(), updated_by = 'bayu' WHERE key = 'maintenance_mode';
--   MATIKAN  : UPDATE master.app_settings SET value = 'false', updated_at = now(), updated_by = 'bayu' WHERE key = 'maintenance_mode';
--   PESAN    : UPDATE master.app_settings SET value = 'Kami sedang upgrade sistem, kembali pukul 14.00 WIB.' WHERE key = 'maintenance_message';
-- Berlaku dalam ±10 detik (cache backend), browser menyusul ≤30 detik.

CREATE TABLE IF NOT EXISTS master.app_settings (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL,
    description  TEXT,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT
);

INSERT INTO master.app_settings (key, value, description) VALUES
    ('maintenance_mode', 'false', 'true = website menampilkan halaman "Website Sedang Dalam Perbaikan" dan API menolak request (503).'),
    ('maintenance_message', '', 'Pesan tambahan di halaman maintenance (kosong = pesan bawaan).')
ON CONFLICT (key) DO NOTHING;
