-- Nama pendek PT (companies.short_name), diisi dari properti GeoJSON short_name_pt
-- saat upload batas blok (analisis melaporkan rencana, execute menulis ke master).
-- Aman dijalankan berulang kali.

ALTER TABLE master.companies ADD COLUMN IF NOT EXISTS short_name VARCHAR(50);
