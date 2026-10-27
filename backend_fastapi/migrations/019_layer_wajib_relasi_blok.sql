-- 019: semua layer wajib terikat blok (relasi_blok / has_block = true).
-- Data layer hanya bisa dibatasi hak akses wilayah (role) lewat block_id -> master.blocks.
-- Hanya mengubah flag konfigurasi; TIDAK mengubah/menghapus data layer.
-- Hanya layer yang tabelnya sudah punya kolom block_id yang di-set true (tabel lain perlu backfill dulu).
-- Idempoten. Per 27-10-2026: satu-satunya baris has_block=false adalah 'blok' (spatial.block_boundaries,
-- block_id NOT NULL) di db_uat_v1 dan gis_db_v4.
UPDATE spatial.layer_types lt
   SET has_block = true
 WHERE lt.has_block IS DISTINCT FROM true
   AND EXISTS (
       SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema = split_part(lt.table_name, '.', 1)
          AND c.table_name = split_part(lt.table_name, '.', 2)
          AND c.column_name = 'block_id');
