/** Nama tabel fisik yang disimpan di role, beserta kode layer / nama API lama. */
const GRANT_ALIASES: Record<string, string[]> = {
  "spatial.tph_points": ["tph"],
  "spatial.tree_censuses": ["sawit"],
  "spatial.palm_trees": ["sawit"],
  "spatial.slope_polygons": ["slope"],
  "spatial.landuse_polygons": ["landuse"],
  "spatial.roads": ["jalan"],
  "spatial.bridges": ["jembatan"],
  "spatial.block_boundaries": ["blok"],
  "trx.block_productions": ["trx_produksi_tbs"],
  "trx.area_statements": ["trx_areal_statement"],
  "trx.harvest_rotations": ["trx_rotasi_pusingan"],
};

export function expandTransactionGrants(values: unknown): Set<string> {
  const allowed = new Set<string>();
  const list = Array.isArray(values) ? values : [];
  for (const value of list) {
    const text = String(
      typeof value === "string"
        ? value
        : (value as { nama_table_transaksi?: string; table_name?: string; resource?: string })?.nama_table_transaksi
          ?? (value as { table_name?: string })?.table_name
          ?? (value as { resource?: string })?.resource
          ?? "",
    ).trim().toLowerCase();
    if (text) allowed.add(text);
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const [table, aliases] of Object.entries(GRANT_ALIASES)) {
      const group = [table, ...aliases];
      if (group.some((key) => allowed.has(key)) && group.some((key) => !allowed.has(key))) {
        group.forEach((key) => allowed.add(key));
        changed = true;
      }
    }
  }
  return allowed;
}

export function grantCovers(allowed: Set<string> | null, ...keys: string[]) {
  if (allowed === null) return true;
  return keys.some((key) => allowed.has(key.trim().toLowerCase()));
}
