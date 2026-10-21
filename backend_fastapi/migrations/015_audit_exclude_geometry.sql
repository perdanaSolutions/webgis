-- Audit per baris tidak lagi menyalin isi kolom geometri ke audit.change_logs.
--
-- Sebelumnya audit.log_row_change menyimpan to_jsonb(OLD/NEW) utuh, termasuk poligon dengan ratusan ribu
-- koordinat. Pada upload GeoJSON besar itu memakan lebih dari 85 persen waktu simpan (INSERT block_boundaries ±14 ms per baris)
-- dan membuat audit.change_logs membengkak.
--
-- Perilaku baru, hanya untuk tabel yang punya kolom bertipe geometry/geography:
--   * old_data / new_data memuat semua kolom KECUALI kolom geometri;
--   * pada UPDATE, nama kolom geometri yang nilainya berubah tetap masuk changed_cols (isinya tidak disimpan);
--   * isi geometri versi lama tidak dapat dipulihkan dari audit lagi -> andalkan backup database.
-- Tabel tanpa kolom geometri berjalan persis seperti sebelumnya. Baris audit lama tidak diubah.
--
-- Untuk membatalkan: jalankan ulang fungsi asli di bawah ini (disimpan sebagai komentar).
--   CREATE OR REPLACE FUNCTION audit.log_row_change() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
--   SET search_path TO pg_catalog, public AS $f$
--   DECLARE o jsonb; n jsonb; cols text[];
--   BEGIN
--       IF TG_OP IN ('UPDATE','DELETE') THEN o := to_jsonb(OLD); END IF;
--       IF TG_OP IN ('UPDATE','INSERT') THEN n := to_jsonb(NEW); END IF;
--       IF TG_OP = 'UPDATE' THEN
--           SELECT array_agg(k ORDER BY k) INTO cols FROM jsonb_object_keys(n) k WHERE n -> k IS DISTINCT FROM o -> k;
--       END IF;
--       INSERT INTO audit.change_logs (schema_name, table_name, operation, old_data, new_data, changed_cols, actor_user_id, application)
--       VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP, o, n, cols, audit.actor_user_id(), nullif(current_setting('application_name', true), ''));
--       RETURN NULL;
--   END $f$;
--
-- Aman dijalankan berulang kali.

-- Baris sebagai JSON hanya dari kolom `attrs` (urutan kolom tabel). jsonb_build_object dibatasi 100 argumen,
-- jadi dirakit per 40 kolom.
CREATE OR REPLACE FUNCTION audit.row_json_columns(r anyelement, attrs text[]) RETURNS jsonb
LANGUAGE plpgsql
SET search_path TO pg_catalog, public
AS $f$
DECLARE
    result jsonb := '{}'::jsonb;
    part jsonb;
    i int := 1;
BEGIN
    WHILE attrs IS NOT NULL AND i <= array_length(attrs, 1) LOOP
        EXECUTE 'SELECT jsonb_build_object(' ||
                (SELECT string_agg(quote_literal(k) || ', ($1).' || quote_ident(k), ', ') FROM unnest(attrs[i:i + 39]) AS k) || ')'
            INTO part USING r;
        result := result || part;
        i := i + 40;
    END LOOP;
    RETURN result;
END $f$;

CREATE OR REPLACE FUNCTION audit.log_row_change() RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $f$
DECLARE
    o jsonb;
    n jsonb;
    cols text[];
    attrs text[];
    geoms text[];
    geom_changed text[];
BEGIN
    SELECT array_agg(a.attname ORDER BY a.attnum) FILTER (WHERE t.typname NOT IN ('geometry', 'geography')),
           array_agg(a.attname ORDER BY a.attnum) FILTER (WHERE t.typname IN ('geometry', 'geography'))
      INTO attrs, geoms
      FROM pg_attribute a
      JOIN pg_type t ON t.oid = a.atttypid
     WHERE a.attrelid = TG_RELID AND a.attnum > 0 AND NOT a.attisdropped;

    IF geoms IS NULL THEN
        IF TG_OP IN ('UPDATE', 'DELETE') THEN o := to_jsonb(OLD); END IF;
        IF TG_OP IN ('UPDATE', 'INSERT') THEN n := to_jsonb(NEW); END IF;
    ELSE
        IF TG_OP IN ('UPDATE', 'DELETE') THEN o := audit.row_json_columns(OLD, attrs); END IF;
        IF TG_OP IN ('UPDATE', 'INSERT') THEN n := audit.row_json_columns(NEW, attrs); END IF;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        SELECT array_agg(k ORDER BY k) INTO cols
          FROM jsonb_object_keys(n) k
         WHERE n -> k IS DISTINCT FROM o -> k;
        IF geoms IS NOT NULL THEN
            EXECUTE 'SELECT array_remove(ARRAY[' ||
                    (SELECT string_agg('CASE WHEN ($1).' || quote_ident(g) || ' IS DISTINCT FROM ($2).' || quote_ident(g) || ' THEN ' || quote_literal(g) || ' END', ', ')
                       FROM unnest(geoms) AS g) || ']::text[], NULL)'
                INTO geom_changed USING OLD, NEW;
            IF coalesce(array_length(geom_changed, 1), 0) > 0 THEN
                SELECT array_agg(k ORDER BY k) INTO cols FROM unnest(coalesce(cols, '{}') || geom_changed) AS k;
            END IF;
        END IF;
    END IF;

    INSERT INTO audit.change_logs (schema_name, table_name, operation, old_data, new_data, changed_cols,
                                   actor_user_id, application)
    VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP, o, n, cols,
            audit.actor_user_id(), nullif(current_setting('application_name', true), ''));
    RETURN NULL;
END $f$;
