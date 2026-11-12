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

---

# Struktur schema audit, quarantine, spatial, trx dari gis_db_v4 (prod)

- File: `gis_db_v4_schema_audit_quarantine_spatial_trx_20261105.sql` (struktur saja, TANPA data)
- `pg_dump -d gis_db_v4 -n audit -n quarantine -n spatial -n trx --schema-only --no-owner --no-privileges -Fp`
- 22 tabel, 2 view, 6 fungsi. Butuh extension PostGIS di schema public, dan schema auth/master/ref sudah ter-import (FK ke master.*).
- Import: `CREATE EXTENSION IF NOT EXISTS postgis;` lalu
  `psql -d <db> -v ON_ERROR_STOP=1 -1 -f database/dump/gis_db_v4_schema_audit_quarantine_spatial_trx_20261105.sql`
- Kalau schema-schema ini sudah ada di db tujuan: backup lalu `DROP SCHEMA audit, quarantine, spatial, trx CASCADE;` dulu (JANGAN drop auth/master/ref).

---

# Dump schema trx dari gis_db_v4 (prod) — struktur + data

- File: `gis_db_v4_trx_full_20261111.sql` (struktur + seluruh data, plain SQL, 34 MB)
- Sumber: `gis_db_v4` di `gis-postgres` (PostgreSQL 16.4), dibuat 2026-11-11 10:09 WIB:
  `pg_dump -d gis_db_v4 -n trx --no-owner --no-privileges -Fp`
- Isi: 4 tabel + 1 view (`v_block_production_facts`) + 3 identity sequence.

  | Tabel | Baris |
  |-------|------:|
  | area_statements | 131784 |
  | area_statement_seed_varieties | 132852 |
  | block_productions | 115244 |
  | harvest_rotations | 26855 |

- Tidak ada kolom geometry/PostGIS, dan tidak ada kolom token/password/kredensial.
- Ketergantungan (wajib ada di database tujuan sebelum import):
  - Tipe `ref.month_period` (kolom `period` di 3 tabel) — sudah ada jika dump auth/master/ref 20261105 diimpor.
  - FK ke `master.blocks`, `master.areas`, `ref.planting_statuses`, `ref.soil_types`, `ref.topography_types`, `ref.seed_varieties`, `ref.rotation_statuses`.
  - FK ke `audit.upload_batches(id)`: semua baris trx punya `upload_batch_id` (90 UUID berbeda). Tanpa baris itu, import gagal saat menambah constraint.
  - Trigger `audit_row` / `audit_row_update` / `audit_truncate` memanggil `audit.log_row_change()` dan `audit.log_truncate()` — fungsi ini ada di dump struktur audit/quarantine/spatial/trx 20261105 (tanpa data `upload_batches`).
- PERINGATAN: berisi data transaksi prod (area statement, produksi, rotasi panen) di repo public.

## Restore (umum)

Database tujuan harus sudah punya schema auth, master, ref, dan audit (fungsi + tabel `upload_batches`). File ini dump penuh (CREATE SCHEMA/TABLE + data), jadi pendekatan truncate saja tidak cocok. Jika schema trx sudah ada, backup dulu lalu `DROP SCHEMA trx CASCADE` (JANGAN drop auth/master/ref/audit) dan import dalam satu transaksi.

```bash
# Sisipkan stub untuk UUID upload_batch_id yang belum ada, agar FK lolos
awk '
  /^COPY trx\./ && /upload_batch_id/ {p=1; next}
  p && $0=="\\." {p=0; next}
  p {print $NF}
' database/dump/gis_db_v4_trx_full_20261111.sql \
| sort -u \
| awk '{printf "INSERT INTO audit.upload_batches (id, source_type, target_table, record_count, status) SELECT '\''%s'\'', '\''IMPORT_STUB'\'', '\''trx'\'', 0, '\''COMPLETED'\'' WHERE NOT EXISTS (SELECT 1 FROM audit.upload_batches WHERE id = '\''%s'\'');\n", $1, $1}' \
| psql -U postgres -d gis_db_v4 -v ON_ERROR_STOP=1

# Backup schema trx yang ada, lalu ganti dengan dump ini (satu transaksi)
pg_dump -U postgres -d gis_db_v4 -n trx --no-owner --no-privileges -Fp > trx_backup_sebelum_import.sql
{
  echo "DROP SCHEMA IF EXISTS trx CASCADE;"
  cat database/dump/gis_db_v4_trx_full_20261111.sql
} | psql -U postgres -d gis_db_v4 -v ON_ERROR_STOP=1 -1
```

## Import ke server TPA (container `global-postgres`, database `db_gis`)

Jalankan di server TPA, dari checkout repo (mis. `/home/ginanjar/aplikasi/webgis`), setelah auth/master/ref dan struktur audit sudah ada:

```bash
cd /home/ginanjar/aplikasi/webgis
PGU=$(docker exec global-postgres printenv POSTGRES_USER)
DUMP=database/dump/gis_db_v4_trx_full_20261111.sql

# 1. Backup schema trx yang sekarang ada di db_gis
docker exec global-postgres pg_dump -U "$PGU" -d db_gis -n trx --no-owner --no-privileges -Fp \
  > /tmp/db_gis_trx_backup_sebelum_import_20261111.sql

# 2. Stub audit.upload_batches untuk UUID yang dirujuk dump (lewati id yang sudah ada)
awk '
  /^COPY trx\./ && /upload_batch_id/ {p=1; next}
  p && $0=="\\." {p=0; next}
  p {print $NF}
' "$DUMP" \
| sort -u \
| awk '{printf "INSERT INTO audit.upload_batches (id, source_type, target_table, record_count, status) SELECT '\''%s'\'', '\''IMPORT_STUB'\'', '\''trx'\'', 0, '\''COMPLETED'\'' WHERE NOT EXISTS (SELECT 1 FROM audit.upload_batches WHERE id = '\''%s'\'');\n", $1, $1}' \
| docker exec -i global-postgres psql -U "$PGU" -d db_gis -v ON_ERROR_STOP=1

# 3. Ganti schema trx dalam satu transaksi
{
  echo "DROP SCHEMA IF EXISTS trx CASCADE;"
  cat "$DUMP"
} | docker exec -i global-postgres psql -U "$PGU" -d db_gis -v ON_ERROR_STOP=1 -1

# 4. Verifikasi jumlah baris (harus sama dengan tabel di atas)
docker exec global-postgres psql -U "$PGU" -d db_gis -c "
SELECT 'area_statements' AS tabel, COUNT(*) FROM trx.area_statements
UNION ALL SELECT 'area_statement_seed_varieties', COUNT(*) FROM trx.area_statement_seed_varieties
UNION ALL SELECT 'block_productions', COUNT(*) FROM trx.block_productions
UNION ALL SELECT 'harvest_rotations', COUNT(*) FROM trx.harvest_rotations;
"
```

---

# Dump schema trx + baris terkait audit.upload_batches dari gis_db_v4 (prod) — 2026-11-12

- File: `gis_db_v4_trx_and_related_20261112.sql` (plain SQL, ~35 MB)
- Sumber: `gis_db_v4` di `gis-postgres` (PostgreSQL 16.4), dibuat 2026-11-12 14:57 WIB
- Bagian A: 320 baris `audit.upload_batches` sebagai `INSERT ... ON CONFLICT (id) DO UPDATE` (idempotent; menimpa stub `IMPORT_STUB` jika ada). `uploaded_by` diisi hanya jika user sudah ada di `auth.users`.
- Bagian B: `DROP SCHEMA trx CASCADE` + `pg_dump -n trx --no-owner --no-privileges` (struktur + seluruh data).

  | Tabel | Baris |
  |-------|------:|
  | area_statements | 131784 |
  | area_statement_seed_varieties | 132852 |
  | block_productions | 115244 |
  | harvest_rotations | 26855 |

- Objek trx lain: view `v_block_production_facts`, 3 identity sequence, 12 trigger audit (`audit.log_row_change` / `audit.log_truncate`).
- 90 UUID `upload_batch_id` dirujuk baris trx; 189 batch punya `target_table` `trx.*`; file ini membawa seluruh 320 baris `audit.upload_batches` agar FK lengkap tanpa stub.
- Tidak ada FK dari schema lain ke tabel trx. Data `master`/`ref` tidak di-dump ulang (sudah ada di `gis_db_v4_auth_master_ref_20261105.sql`; semua ID yang dirujuk trx ada di prod).
- Tidak ikut: `audit.upload_jobs` (0 baris terkait trx), `quarantine.rows` (ada ~11947 baris terkait batch target trx, tidak wajib untuk import), `audit.change_logs`.
- Tidak ada kolom token/password/kredensial. Metadata `upload_batches` hanya kunci operasional (`csv`, `detail_statistik`, `jenis`, `layer`, `periode`, `periode_target`, `step`).
- Selama import, `session_replication_role = replica` supaya trigger tidak menulis `audit.change_logs`.
- PERINGATAN: berisi data transaksi prod di repo public. Schema trx di database tujuan akan diganti; backup dulu. Schema auth/master/ref/audit/quarantine/spatial tidak di-drop.

## Import ke server TPA (container `global-postgres`, database `db_gis`)

Jalankan di server TPA, dari checkout repo (mis. `/home/ginanjar/aplikasi/webgis`). Database tujuan harus sudah punya schema auth, master, ref, dan struktur audit (hasil import dump 20261105). Jika schema trx sudah berisi data, langkah 2 akan menggantinya (backup di langkah 1).

```bash
cd /home/ginanjar/aplikasi/webgis
git checkout dev-bayu && git pull origin dev-bayu
PGU=$(docker exec global-postgres printenv POSTGRES_USER); PGU=${PGU:-postgres}; echo "user=[$PGU]"
DUMP=database/dump/gis_db_v4_trx_and_related_20261112.sql
ls -lh "$DUMP"     # sekitar 35 MB

# 1. Backup schema trx yang sekarang ada di db_gis (simpan di /root)
docker exec global-postgres pg_dump -U "$PGU" -d db_gis -n trx --no-owner --no-privileges   > /root/backup_db_gis_trx_$(date +%Y%m%d_%H%M).sql

# 2. Sisipkan/perbarui 320 baris audit.upload_batches, lalu ganti schema trx.
#    Satu transaksi: jika ada error, semua perubahan dibatalkan.
#    Schema auth/master/ref/audit/quarantine/spatial tidak di-drop.
docker exec -i global-postgres psql -U "$PGU" -d db_gis -v ON_ERROR_STOP=1 -1 < "$DUMP"

# 3. Verifikasi (harus 131784 / 132852 / 115244 / 26855, dan 90 batch dirujuk trx sudah ada)
docker exec global-postgres psql -U "$PGU" -d db_gis -c "
SELECT 'area_statements' t, count(*) FROM trx.area_statements
UNION ALL SELECT 'area_statement_seed_varieties', count(*) FROM trx.area_statement_seed_varieties
UNION ALL SELECT 'block_productions', count(*) FROM trx.block_productions
UNION ALL SELECT 'harvest_rotations', count(*) FROM trx.harvest_rotations
UNION ALL SELECT 'upload_batches_total', count(*) FROM audit.upload_batches
UNION ALL SELECT 'upload_batches_dirujuk_trx', count(DISTINCT bid) FROM (
  SELECT upload_batch_id bid FROM trx.area_statements
  UNION
  SELECT upload_batch_id FROM trx.block_productions
  UNION
  SELECT upload_batch_id FROM trx.harvest_rotations
) s;
"
```

Setelah selesai, restart backend di TPA supaya koneksi lamanya ter-refresh. Kalau langkah 2 error, seluruh transaksi dibatalkan (schema trx lama tetap ada); kirim pesan errornya.
