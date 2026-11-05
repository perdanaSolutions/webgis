# Dump struktur database db_uat_v1

- File: `db_uat_v1_schema_20261103.sql` (pg_dump `--schema-only`: struktur saja, tanpa data; format plain SQL)
- Sumber: database `db_uat_v1` di container `gis-postgres` (PostgreSQL 16.4, PostGIS 3.4.3)
- Dibuat: 2026-11-03 15:10 WIB, perintah:
  `pg_dump -d db_uat_v1 --schema-only --no-owner --no-privileges -Fp`
- Isi: 48 tabel (47 CREATE TABLE + spatial_ref_sys dari extension PostGIS), view, fungsi, index, constraint, sequence. Tidak ada data (repo ini public).

## Restore

Butuh PostgreSQL 16 + PostGIS 3.4 (mis. image postgis/postgis:16-3.4).

```bash
createdb -U postgres db_uat_v1_restore
psql -U postgres -d db_uat_v1_restore -v ON_ERROR_STOP=1 -f database/dump/db_uat_v1_schema_20261103.sql
```

---

# Dump schema auth, master, ref dari gis_db_v4 (prod)

- File: `gis_db_v4_auth_master_ref_20261105.sql` (struktur + seluruh data, plain SQL)
- Sumber: `gis_db_v4` di `gis-postgres` (PostgreSQL 16.4), dibuat 2026-11-05 WIB:
  `pg_dump -d gis_db_v4 -n auth -n master -n ref --no-owner --no-privileges -Fp`
- 26 tabel (auth 8, master 9, ref 9). Tidak bergantung pada PostGIS atau schema lain; butuh PostgreSQL >= 13 (gen_random_uuid).
- PERINGATAN: berisi data user prod (email, username, hash password) di repo public.

## Import ke server baru

```bash
createdb -U postgres gis_db_v4
psql -U postgres -d gis_db_v4 -v ON_ERROR_STOP=1 -1 -f database/dump/gis_db_v4_auth_master_ref_20261105.sql
```
