-- Layer landuse: OBJECTID di export landuse tidak unik (satu OBJECTID dipakai beberapa blok, dan berulang antar
-- file wilayah), sehingga UNIQUE (period, objectid) membuang/menimpa polygon yang sah. Penggantian data saat
-- upload ulang cukup per blok + periode. Aman dijalankan berulang kali.

ALTER TABLE spatial.landuse_polygons DROP CONSTRAINT IF EXISTS landuse_polygons_period_objectid_key;
CREATE INDEX IF NOT EXISTS ix_landuse_polygons_block_period ON spatial.landuse_polygons (block_id, period);
