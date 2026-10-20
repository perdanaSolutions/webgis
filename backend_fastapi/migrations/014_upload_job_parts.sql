-- Metadata part Feature dari FE (mis. 1.000 feature/part). Setiap part tetap satu baris
-- upload_jobs yang diproses worker seperti biasa; kolom ini hanya untuk audit & UI progress.
-- Aman dijalankan berulang kali.

ALTER TABLE audit.upload_jobs
    ADD COLUMN IF NOT EXISTS upload_group_id UUID,
    ADD COLUMN IF NOT EXISTS part_index INTEGER,
    ADD COLUMN IF NOT EXISTS part_total INTEGER;

CREATE INDEX IF NOT EXISTS ix_upload_jobs_group
    ON audit.upload_jobs (upload_group_id, part_index)
    WHERE upload_group_id IS NOT NULL;
