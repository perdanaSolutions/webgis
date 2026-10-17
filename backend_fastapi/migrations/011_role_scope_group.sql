-- Hak akses data per GRUP (struktur v2): satu scope role boleh menunjuk satu grup (semua PT di grup itu,
-- termasuk PT yang kelak dipindah ke grup tersebut). Tetap tepat SATU level per baris scope.
-- Aman dijalankan berulang kali.

ALTER TABLE auth.role_data_scopes
    ADD COLUMN IF NOT EXISTS group_id BIGINT REFERENCES master.groups (id) ON DELETE CASCADE;

ALTER TABLE auth.role_data_scopes DROP CONSTRAINT IF EXISTS role_data_scopes_check;
ALTER TABLE auth.role_data_scopes ADD CONSTRAINT role_data_scopes_check
    CHECK (num_nonnulls(group_id, area_id, company_id, estate_id, division_id) = 1);

-- Unik per (role, node) termasuk grup; menggantikan constraint unik lama yang belum memuat group_id.
ALTER TABLE auth.role_data_scopes DROP CONSTRAINT IF EXISTS role_data_scopes_role_id_area_id_company_id_estate_id_divis_key;
CREATE UNIQUE INDEX IF NOT EXISTS ux_role_data_scopes_node
    ON auth.role_data_scopes (role_id, group_id, area_id, company_id, estate_id, division_id) NULLS NOT DISTINCT;
