-- Akses unduh peta (tombol Unduh Peta di halaman map). Superadmin selalu lolos di backend/FE.
-- Role yang sudah ada diberi akses supaya perilaku existing tidak berubah mendadak.
-- Aman dijalankan berulang kali.

INSERT INTO auth.permissions (code, resource, action, description)
VALUES ('map:download', 'map', 'download', 'Mengunduh peta (PDF) dari halaman map')
ON CONFLICT (code) DO NOTHING;

INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r
CROSS JOIN auth.permissions p
WHERE p.code = 'map:download'
ON CONFLICT DO NOTHING;
