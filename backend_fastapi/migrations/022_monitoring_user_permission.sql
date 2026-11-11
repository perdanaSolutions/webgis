-- Monitoring user (GET /monitoring/users): superadmin selalu lolos di backend; role admin diberi akses.
-- Aman dijalankan berulang kali.

INSERT INTO auth.permissions (code, resource, action, description)
VALUES ('monitoring:read', 'monitoring', 'read', 'Melihat monitoring user (status online/offline)')
ON CONFLICT (code) DO NOTHING;

INSERT INTO auth.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM auth.roles r CROSS JOIN auth.permissions p
WHERE r.name = 'admin' AND p.code = 'monitoring:read'
ON CONFLICT DO NOTHING;
