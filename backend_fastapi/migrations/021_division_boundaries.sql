-- 021: batas afdeling per periode (spatial.division_boundaries).
-- source = 'derived' : gabungan (union) batas blok afdeling itu per periode, dibersihkan (celah/lubang kecil),
--                      diisi otomatis setelah upload GeoJSON blok / backfill (python -m scripts.backfill_division_boundaries).
-- source = 'official': cadangan untuk batas afdeling resmi (belum ada alur upload-nya).
-- Hanya MENAMBAH tabel + index baru; tidak mengubah tabel lain. Idempoten.
CREATE TABLE IF NOT EXISTS spatial.division_boundaries (
    id bigserial PRIMARY KEY,
    division_id bigint NOT NULL REFERENCES master.divisions(id),
    estate_id bigint REFERENCES master.estates(id),
    period date NOT NULL,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    geom_display geometry(MultiPolygon, 4326),
    n_blok integer NOT NULL DEFAULT 0,
    luas_ha numeric(14, 4),
    source varchar(16) NOT NULL DEFAULT 'derived' CHECK (source IN ('derived', 'official')),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT division_boundaries_division_period_source_key UNIQUE (division_id, period, source)
);
CREATE INDEX IF NOT EXISTS division_boundaries_geom_gix ON spatial.division_boundaries USING gist (geom);
CREATE INDEX IF NOT EXISTS division_boundaries_geom_display_gix ON spatial.division_boundaries USING gist (geom_display);
CREATE INDEX IF NOT EXISTS division_boundaries_estate_idx ON spatial.division_boundaries (estate_id);
CREATE INDEX IF NOT EXISTS division_boundaries_period_idx ON spatial.division_boundaries (period);
