-- Migrasi relasi user-role dari 1:N (users.role_id) menjadi M:N (auth.user_roles).
-- PERINGATAN: ALTER TABLE ... DROP COLUMN di akhir file ini tidak bisa dibatalkan
-- terhadap kode aplikasi yang masih membaca users.role_id. Terapkan file ini
-- berbarengan dengan deploy kode backend yang sudah tidak memakai role_id.
-- Aman dijalankan berulang kali.

CREATE TABLE IF NOT EXISTS auth.user_roles (
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_id    UUID NOT NULL REFERENCES auth.roles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'auth' AND table_name = 'users' AND column_name = 'role_id'
    ) THEN
        INSERT INTO auth.user_roles (user_id, role_id)
        SELECT u.id, u.role_id FROM auth.users u WHERE u.role_id IS NOT NULL
        ON CONFLICT (user_id, role_id) DO NOTHING;
    END IF;
END $$;

ALTER TABLE auth.users DROP COLUMN IF EXISTS role_id;
