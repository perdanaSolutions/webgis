/** Helper Filter Kebun (halaman Blok Profile). */

export type FilterScope = { area: string; pt: string; estate: string; afdeling: string; blokId: string };

/**
 * Toleransi penyederhanaan garis batas (meter) untuk GeoJSON blok.
 * Lingkup luas (tanpa estate/afdeling/blok) -> 1 m: ukuran respons "Semua" UAT turun ~20 MB -> ~6,3 MB
 * (gzip 3,9 MB -> 1,1 MB) tanpa beda yang terlihat di peta. Estate ke bawah memakai geometri asli.
 */
export function geometrySimplifyMeters(scope: Pick<FilterScope, "estate" | "afdeling" | "blokId">): number | undefined {
  return scope.estate || scope.afdeling || scope.blokId ? undefined : 1;
}

export type BlockOptionRow = { blok_id: string | number; kode_blok?: string | null; kode_afd?: string | null; kode_est?: string | null };

/** Opsi dropdown blok: label = kode blok (+ afdeling/estate bila kode sama muncul di beberapa tempat), urut kode. */
export function blockOptionsFrom(rows: BlockOptionRow[]): Array<{ label: string; value: string }> {
  const counts = new Map<string, number>();
  for (const r of rows) {
    const code = String(r.kode_blok ?? "").trim();
    counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  return rows
    .map((r) => {
      const value = String(r.blok_id ?? "").trim();
      const code = String(r.kode_blok ?? "").trim() || value;
      const where = [r.kode_est, r.kode_afd].filter(Boolean).join("/");
      const label = (counts.get(code) ?? 0) > 1 && where ? `${code} (${where})` : code;
      return { label, value };
    })
    .filter((o) => o.value)
    .sort((a, b) => a.label.localeCompare(b.label, "id"));
}

/** Teks lingkup: kosong di semua level = semua wilayah dalam hak akses user. */
export function isAllScope(scope: FilterScope): boolean {
  return !scope.area && !scope.pt && !scope.estate && !scope.afdeling && !scope.blokId;
}
