/**
 * Ringkasan 1 tahun untuk kartu Data Histori, dihitung di frontend dari SELURUH baris histori
 * (bukan hanya halaman yang tampil).
 *
 * - Ton    : jumlah Ton semua periode pada tahun itu (akumulasi).
 * - Luas   : luas periode TERAKHIR pada tahun itu (luas tanam berulang tiap bulan, jadi tidak dijumlah).
 * - Ton/ha : total Ton / luas periode terakhir.
 * - Jjg/Pkk, Kg/Pkk : jumlah nilai bulanan (total setahun per pokok).
 * - BJR    : rata-rata tertimbang = ΣKg/Pkk ÷ ΣJjg/Pkk (= total kg ÷ total janjang per pokok).
 *            Bila ΣJjg/Pkk = 0 -> rata-rata BJR bulanan.
 * - Satu ringkasan per tahun; tahun terbaru di atas.
 */
export type HistoriRow = {
  tahun: number; bulan: number | null; ton: number; luas: number;
  bjr?: number; jjg_ppk?: number; kg_ppk?: number;
};

export type YearSummary = {
  tahun: number;
  periods: number;
  ton: number;
  luas: number;
  /** Bulan dari periode yang luasnya dipakai (null untuk data tahunan). */
  luasBulan: number | null;
  ton_ha: number;
  bjr: number;
  jjg_ppk: number;
  kg_ppk: number;
};

const fin = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);

export function yearlySummaries(rows: HistoriRow[]): YearSummary[] {
  const byYear = new Map<number, HistoriRow[]>();
  for (const row of rows) {
    if (!Number.isFinite(row.tahun)) continue;
    const list = byYear.get(row.tahun) ?? [];
    list.push(row);
    byYear.set(row.tahun, list);
  }
  return [...byYear.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([tahun, list]) => {
      const sorted = [...list].sort((a, b) => (a.bulan ?? 0) - (b.bulan ?? 0));
      const last = sorted[sorted.length - 1]!;
      const ton = sorted.reduce((acc, row) => acc + (Number.isFinite(row.ton) ? row.ton : 0), 0);
      const luas = Number.isFinite(last.luas) ? last.luas : 0;
      const jjg = sorted.reduce((acc, row) => acc + fin(row.jjg_ppk), 0);
      const kg = sorted.reduce((acc, row) => acc + fin(row.kg_ppk), 0);
      const bjrRows = sorted.filter((row) => fin(row.bjr) > 0);
      const bjr = jjg > 0 && kg > 0
        ? kg / jjg
        : bjrRows.length ? bjrRows.reduce((acc, row) => acc + fin(row.bjr), 0) / bjrRows.length : NaN;
      return {
        tahun, periods: sorted.length, ton, luas, luasBulan: last.bulan, ton_ha: luas > 0 ? ton / luas : NaN,
        bjr, jjg_ppk: jjg, kg_ppk: kg,
      };
    });
}
