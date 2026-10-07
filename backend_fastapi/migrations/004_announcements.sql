-- Pengumuman: dibuat/diubah/dihapus oleh yang punya permission pengumuman:write
-- (superadmin selalu lolos di backend), dibaca semua user yang login.
-- Aman dijalankan berulang kali.

CREATE TABLE IF NOT EXISTS master.announcements (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(200) NOT NULL,
    content     TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    start_at    TIMESTAMPTZ,
    end_at      TIMESTAMPTZ,
    created_by  UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT announcements_period_chk CHECK (end_at IS NULL OR start_at IS NULL OR end_at >= start_at)
);

CREATE INDEX IF NOT EXISTS ix_announcements_created_at ON master.announcements (created_at DESC);

INSERT INTO auth.permissions (code, resource, action, description)
VALUES ('pengumuman:write', 'pengumuman', 'write', 'Tambah, ubah, dan hapus pengumuman')
ON CONFLICT (code) DO NOTHING;

INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r CROSS JOIN auth.permissions p
WHERE r.name = 'admin' AND p.code = 'pengumuman:write'
ON CONFLICT DO NOTHING;
