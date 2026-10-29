/**
 * Total kartu Rotasi: Rotasi = Σ luas panen ÷ luas tanam (bukan SUM rotasi bulanan).
 * Sumber utama = `ringkasan` dari backend /spatial/history (trx_rotasi_pusingan); hitungan lokal hanya cadangan
 * untuk respons lama. Luas panen bulan = Σ(area_ha × rotation_no); luas tanam = Σ area_ha bulan terakhir.
 */
export type RotationSummary = { luas_panen: number; luas_tanam: number; rotasi: number | null };
type MonthRow = { luas: number; luasPanen: number | null };

export function rotationTotals(rows: MonthRow[], backend?: Partial<RotationSummary> | null): RotationSummary | null {
  if (backend && backend.luas_panen != null && backend.luas_tanam != null) {
    const luasTanam = Number(backend.luas_tanam);
    const luasPanen = Number(backend.luas_panen);
    const rotasi = backend.rotasi != null ? Number(backend.rotasi) : luasTanam > 0 ? luasPanen / luasTanam : null;
    return { luas_panen: luasPanen, luas_tanam: luasTanam, rotasi };
  }
  const last = rows[rows.length - 1];
  if (!last || rows.some((r) => r.luasPanen == null || !Number.isFinite(r.luasPanen))) return null;
  const luasPanen = rows.reduce((sum, r) => sum + (r.luasPanen ?? 0), 0);
  return { luas_panen: luasPanen, luas_tanam: last.luas, rotasi: last.luas > 0 ? luasPanen / last.luas : null };
}
