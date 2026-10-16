-- Struktur v2:
--   Organisasi : master.groups -> master.companies (group_id) -> master.estates -> divisions -> blocks
--   Wilayah    : master.areas  -> master.estates (area_id) = area SAAT INI estate
--   Riwayat area per bulan tetap di trx.area_statements.area_id (tidak berubah).
-- Sumber resmi grup PT dan area estate = upload GeoJSON blok (properti Group dan Area).
-- Aman dijalankan berulang kali: nilai yang sudah terisi tidak ditimpa.

ALTER TABLE master.companies ADD COLUMN IF NOT EXISTS group_id BIGINT REFERENCES master.groups (id);
CREATE INDEX IF NOT EXISTS ix_companies_group_id ON master.companies (group_id);

ALTER TABLE master.estates ADD COLUMN IF NOT EXISTS area_id BIGINT REFERENCES master.areas (id);
CREATE INDEX IF NOT EXISTS ix_estates_area_id ON master.estates (area_id);

-- 1. Grup PT dari grup estate struktur lama. PT yang estatenya beda-beda grup tidak bisa dipindah otomatis:
--    migrasi berhenti di sini (sebelum kolom lama dihapus) supaya data grup estate tidak hilang.
DO $$
DECLARE
    mixed text;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'master' AND table_name = 'estates' AND column_name = 'group_id') THEN
        SELECT string_agg(co.code, ', ' ORDER BY co.code) INTO mixed
        FROM master.companies co
        WHERE co.id IN (SELECT company_id FROM master.estates WHERE group_id IS NOT NULL
                        GROUP BY company_id HAVING count(DISTINCT group_id) > 1);
        IF mixed IS NOT NULL THEN
            -- Pesan disusun tanpa placeholder persen: runner migrasi mengirim SQL lewat driver Python.
            RAISE EXCEPTION USING MESSAGE = 'Migrasi 010 dibatalkan: PT ' || mixed
                || ' punya estate dengan grup berbeda. Samakan grup estatenya dulu.';
        END IF;
        UPDATE master.companies co SET group_id = x.group_id
        FROM (SELECT company_id, min(group_id) AS group_id FROM master.estates
              WHERE group_id IS NOT NULL GROUP BY company_id HAVING count(DISTINCT group_id) = 1) x
        WHERE co.id = x.company_id AND co.group_id IS NULL;
    END IF;
END $$;

-- 2. Cadangan untuk database tanpa grup estate: grup per kode PT dari Blok_TPA_SGA.geojson (Okt 2026).
UPDATE master.companies co SET group_id = gr.id
FROM (VALUES
    ('1100', 'TPA'), ('1200', 'TPA'), ('1300', 'TPA'), ('1400', 'TPA'), ('1500', 'TPA'), ('1600', 'TPA'),
    ('1610', 'TPA'), ('1800', 'TPA'), ('1900', 'TPA'),
    ('3100', 'SGA'), ('3200', 'SGA'), ('3300', 'SGA')
) AS v (company_code, group_code)
JOIN master.groups gr ON gr.code = v.group_code
WHERE co.code = v.company_code AND co.group_id IS NULL;

-- 3. Area estate = area pada periode areal statement terbaru estate itu
--    (bila periode itu punya beberapa area, area dengan blok terbanyak).
UPDATE master.estates es SET area_id = x.area_id
FROM (
    SELECT DISTINCT ON (estate_id) estate_id, area_id
    FROM (
        SELECT dv.estate_id, a.area_id, a.period, count(*) AS n
        FROM trx.area_statements a
        JOIN master.blocks bl ON bl.id = a.block_id
        JOIN master.divisions dv ON dv.id = bl.division_id
        WHERE a.area_id IS NOT NULL
        GROUP BY dv.estate_id, a.area_id, a.period
    ) t
    ORDER BY estate_id, period DESC, n DESC
) x
WHERE es.id = x.estate_id AND es.area_id IS NULL;

-- 4. View hierarki: grup lewat PT, area lewat estate. Kolom grup di estate (struktur lama) dihapus.
DROP VIEW IF EXISTS master.v_block_hierarchy;
ALTER TABLE master.estates DROP COLUMN IF EXISTS group_id;

CREATE VIEW master.v_block_hierarchy AS
SELECT bl.id AS block_id,
       bl.code AS block_code,
       bt.name AS block_type,
       dv.id AS division_id,
       dv.code AS division_code,
       es.id AS estate_id,
       es.code AS estate_code,
       es.name AS estate_name,
       es.short_name AS estate_short_name,
       co.id AS company_id,
       co.code AS company_code,
       co.name AS company_name,
       ar.id AS area_id,
       ar.code AS area_code,
       gr.id AS group_id,
       gr.code AS group_code,
       gr.name AS group_name
FROM master.blocks bl
JOIN master.divisions dv ON dv.id = bl.division_id
JOIN master.estates es ON es.id = dv.estate_id
JOIN master.companies co ON co.id = es.company_id
LEFT JOIN ref.block_types bt ON bt.id = bl.block_type_id
LEFT JOIN master.areas ar ON ar.id = es.area_id
LEFT JOIN master.groups gr ON gr.id = co.group_id;
