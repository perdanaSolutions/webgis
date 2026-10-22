/**
 * Kolom pengelompokan di tabel preview upload GeoJSON yang selalu diberi filter gaya Excel.
 * Nama kolom di file sumber berbeda-beda, jadi dicocokkan lewat alias (tanpa beda huruf besar/kecil).
 */
export type GroupFilterDef = { key: string; label: string; aliases: string[] };

export const GROUP_FILTER_DEFS: GroupFilterDef[] = [
  { key: "group", label: "Group", aliases: ["group", "grup", "nama_group", "nama_grup"] },
  {
    key: "perusahaan",
    label: "Perusahaan",
    aliases: ["perusahaan", "nama_perusahaan", "kode_pt", "short_name_pt", "company_code", "pt", "company"],
  },
  { key: "area", label: "Area", aliases: ["area", "nama_area", "kode_area"] },
  {
    key: "estate",
    label: "Estate",
    aliases: ["estate", "kode_est", "kode_estate", "est_id", "estid", "est", "nama_estate"],
  },
  { key: "afdeling", label: "Afdeling", aliases: ["afdeling", "kode_afd", "afd"] },
  { key: "blok", label: "Blok", aliases: ["blok", "block", "kode_blok"] },
];

function normalize(name: string): string {
  return name.trim().toLowerCase().replace(/[\s-]+/g, "_");
}

/** Kolom file yang cocok dengan salah satu grup, urut sesuai GROUP_FILTER_DEFS lalu urutan alias. */
export function findGroupColumns(headers: string[]): Array<{ key: string; label: string; column: string }> {
  const byName = new Map<string, string>();
  for (const header of headers) {
    const norm = normalize(header);
    if (!byName.has(norm)) byName.set(norm, header);
  }
  const found: Array<{ key: string; label: string; column: string }> = [];
  for (const def of GROUP_FILTER_DEFS) {
    for (const alias of def.aliases) {
      const column = byName.get(alias);
      if (column && !found.some((f) => f.column === column)) found.push({ key: def.key, label: def.label, column });
    }
  }
  return found;
}
