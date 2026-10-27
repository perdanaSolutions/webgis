-- READ-ONLY: layer yang belum terikat blok + baris tanpa block_id. Aman dijalankan kapan saja.
SET default_transaction_read_only = on;
SELECT lt.code, lt.table_name, lt.has_block,
       EXISTS (SELECT 1 FROM information_schema.columns c
                WHERE c.table_schema = split_part(lt.table_name, '.', 1)
                  AND c.table_name = split_part(lt.table_name, '.', 2)
                  AND c.column_name = 'block_id') AS punya_kolom_block_id
  FROM spatial.layer_types lt
 ORDER BY lt.has_block, lt.code;
-- Nullability block_id per tabel; is_nullable = NO berarti tidak mungkin ada baris tanpa blok.
-- Untuk tabel YES, hitung: SELECT count(*) FROM <tabel> WHERE block_id IS NULL;
SELECT c.table_schema || '.' || c.table_name AS tabel, c.is_nullable
  FROM information_schema.columns c
 WHERE c.table_schema = 'spatial' AND c.column_name = 'block_id'
 ORDER BY 1;
