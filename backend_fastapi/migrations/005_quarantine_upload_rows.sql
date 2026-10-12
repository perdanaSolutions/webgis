-- Karantina upload: baris transaksi (Excel/JSON) dan fitur GeoJSON yang TIDAK lolos validasi
-- disimpan utuh ke quarantine.rows (tabel yang sama dengan karantina migrasi gis_db_v3),
-- dikaitkan ke batch upload-nya. Baris lama hasil migrasi tetap (upload_batch_id NULL).
-- Aman dijalankan berulang kali.

ALTER TABLE quarantine.rows
    ADD COLUMN IF NOT EXISTS upload_batch_id UUID REFERENCES audit.upload_batches(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS reason_code VARCHAR(50);

CREATE INDEX IF NOT EXISTS ix_quarantine_rows_upload_batch ON quarantine.rows (upload_batch_id)
    WHERE upload_batch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_quarantine_rows_quarantined_at ON quarantine.rows (quarantined_at DESC);
