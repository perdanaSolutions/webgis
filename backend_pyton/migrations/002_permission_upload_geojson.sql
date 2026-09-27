-- Permission upload GeoJSON sesuai matriks dbdiagram_2_users_permission.dbml:
--   upload:geojson -> superadmin (selalu lolos di backend) & admin.
-- Aman dijalankan berulang kali.

INSERT INTO auth.permissions (code, resource, action, description)
VALUES ('upload:geojson', 'upload', 'geojson', 'Unggah, analisis, dan hapus per periode data spasial GeoJSON')
ON CONFLICT (code) DO NOTHING;

INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r CROSS JOIN auth.permissions p
WHERE r.name = 'admin' AND p.code = 'upload:geojson'
ON CONFLICT DO NOTHING;
