-- Antrian upload GeoJSON: API menyimpan file + baris 'queued' lalu langsung membalas 202,
-- worker terpisah (python -m app.workers.upload_jobs) mengerjakan analisis/simpan dan menulis
-- tahap & hitungan progres ke sini. FE membaca status lewat GET /api/v1/upload-jobs/{id}.
-- Isi file disimpan di kolom `content` (bukan disk) karena API dan worker bisa berjalan di
-- container berbeda; kolom dikosongkan begitu job selesai.
-- Aman dijalankan berulang kali.

CREATE TABLE IF NOT EXISTS audit.upload_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES auth.users (id) ON DELETE SET NULL,
    kind             VARCHAR(10) NOT NULL CHECK (kind IN ('analyze', 'execute')),
    layer            VARCHAR(63) NOT NULL,
    bulan            SMALLINT NOT NULL CHECK (bulan BETWEEN 1 AND 12),
    tahun            SMALLINT NOT NULL,
    filename         VARCHAR(255),
    file_size        INTEGER NOT NULL,
    content          BYTEA,
    status           VARCHAR(10) NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    stage            VARCHAR(40),
    message          TEXT,
    progress_current INTEGER,
    progress_total   INTEGER,
    result           JSONB,
    error_message    TEXT,
    batch_id         UUID REFERENCES audit.upload_batches (id) ON DELETE SET NULL,
    cancel_requested BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at       TIMESTAMPTZ,
    heartbeat_at     TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_upload_jobs_queue ON audit.upload_jobs (created_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS ix_upload_jobs_running ON audit.upload_jobs (heartbeat_at) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS ix_upload_jobs_user ON audit.upload_jobs (user_id, created_at DESC);
