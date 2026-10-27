-- Riwayat pengumuman yang sudah dibaca per user (login).
-- Aman dijalankan berulang kali.

CREATE TABLE IF NOT EXISTS master.announcement_reads (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    announcement_id   UUID NOT NULL REFERENCES master.announcements(id) ON DELETE CASCADE,
    read_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_announcement_reads_user_announcement UNIQUE (user_id, announcement_id)
);

CREATE INDEX IF NOT EXISTS ix_announcement_reads_user_id
    ON master.announcement_reads (user_id);

CREATE INDEX IF NOT EXISTS ix_announcement_reads_announcement_id
    ON master.announcement_reads (announcement_id);
