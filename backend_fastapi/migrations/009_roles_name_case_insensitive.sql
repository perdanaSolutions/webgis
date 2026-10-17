-- Nama role unik tanpa membedakan huruf besar/kecil ('Admin' = 'admin'), dijaga juga di database
-- (API sudah mengecek lebih dulu dan membalas 409 "Role sudah ada."). Pastikan tidak ada duplikat
-- lower(name) sebelum menjalankan: SELECT lower(name), count(*) FROM auth.roles GROUP BY 1 HAVING count(*) > 1;
-- Aman dijalankan berulang kali.

CREATE UNIQUE INDEX IF NOT EXISTS ux_roles_name_lower ON auth.roles (lower(name));
