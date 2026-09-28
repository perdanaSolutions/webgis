-- Menu bertingkat (maks 3 level) seperti di backend lama.
-- gis_db_v3 menyimpan auth.menus datar; FE (manageMenuStore) memakai parent_id & level.
-- Aman dijalankan berulang kali.

ALTER TABLE auth.menus ADD COLUMN IF NOT EXISTS parent_id uuid;
ALTER TABLE auth.menus ADD COLUMN IF NOT EXISTS level integer NOT NULL DEFAULT 1;
ALTER TABLE auth.menus ADD COLUMN IF NOT EXISTS is_favorite boolean NOT NULL DEFAULT false;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menus_parent_id_fkey') THEN
        ALTER TABLE auth.menus
            ADD CONSTRAINT menus_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES auth.menus(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menus_level_check') THEN
        ALTER TABLE auth.menus ADD CONSTRAINT menus_level_check CHECK (level BETWEEN 1 AND 3);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS menus_parent_id_idx ON auth.menus (parent_id);
