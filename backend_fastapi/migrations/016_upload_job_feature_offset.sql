-- Offset feature part terhadap file asli (0 untuk part pertama). Dipakai worker supaya
-- no_preview hasil analisis/karantina = nomor baris global di tabel preview FE.
-- Aman dijalankan berulang kali.

ALTER TABLE audit.upload_jobs
    ADD COLUMN IF NOT EXISTS feature_offset INTEGER NOT NULL DEFAULT 0;
