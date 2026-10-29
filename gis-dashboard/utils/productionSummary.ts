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
 *
 * SATU SUMBER: bila backend mengirim `rekap_tahunan`, baris tahun itu dipakai apa adanya (luas, ton, ton/ha,
 * BJR = Σkg ÷ Σjanjang, Jjg/Pkk, Kg/Pkk, jumlah periode) supaya kartu "Total {tahun}" sama persis dengan tab
 * Tahunan. Hitungan lokal di bawah hanya cadangan (respons lama tanpa rekap_tahunan); hasilnya bisa sedikit
 * berbeda karena data_histori sudah dibulatkan per bulan (Kg/Pkk bulat, Jjg/Pkk 2 desimal).
 */
export type RecapRow = {
  tahun: number; luas: number; ton: number; ton_ha: number; bjr: number; jjg_ppk: number; kg_ppk: number;
  jumlah_periode?: number;
};

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

export function yearlySummaries(rows: HistoriRow[], recap: RecapRow[] = []): YearSummary[] {
  const local = localSummaries(rows);
  const byYear = new Map(recap.filter((r) => Number.isFinite(r.tahun)).map((r) => [r.tahun, r]));
  return local.map((s) => {
    const r = byYear.get(s.tahun);
    if (!r) return s;
    return {
      ...s,
      periods: r.jumlah_periode || s.periods,
      ton: fin(r.ton), luas: fin(r.luas), ton_ha: Number.isFinite(r.ton_ha) ? r.ton_ha : s.ton_ha,
      bjr: fin(r.bjr) > 0 ? r.bjr : s.bjr, jjg_ppk: fin(r.jjg_ppk), kg_ppk: fin(r.kg_ppk),
    };
  });
}

function localSummaries(rows: HistoriRow[]): YearSummary[] {
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

/** Baris gap per bulan untuk filter Year to Date: tahun filter, bulan 1 s/d `endMonth`, urut bulan. */
export function ytdGapMonths<T extends { tahun: number; bulan: number | null }>(rows: T[], year: number, endMonth: number): T[] {
  return rows
    .filter((row) => row.tahun === year && row.bulan != null && row.bulan >= 1 && row.bulan <= endMonth)
    .sort((a, b) => (a.bulan ?? 0) - (b.bulan ?? 0));
}
