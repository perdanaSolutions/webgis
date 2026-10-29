import { describe, expect, it } from "vitest";
import { yearlySummaries, ytdGapMonths } from "../utils/productionSummary";

describe("yearlySummaries", () => {
  it("ton dijumlah, luas pakai periode terakhir, ton/ha = total ton / luas", () => {
    const rows = [
      { tahun: 2026, bulan: 2, ton: 29.17, luas: 29.72 },
      { tahun: 2026, bulan: 1, ton: 10, luas: 26.55 },
      { tahun: 2026, bulan: 3, ton: 38.36, luas: 29.72 },
    ];
    const [s] = yearlySummaries(rows);
    expect(s!.tahun).toBe(2026);
    expect(s!.periods).toBe(3);
    expect(s!.ton).toBeCloseTo(77.53, 6);
    expect(s!.luas).toBe(29.72);
    expect(s!.luasBulan).toBe(3);
    expect(s!.ton_ha).toBeCloseTo(77.53 / 29.72, 6);
  });
  it("Jjg/Pkk & Kg/Pkk dijumlah, BJR tertimbang = ΣKg/Pkk ÷ ΣJjg/Pkk", () => {
    const [s] = yearlySummaries([
      { tahun: 2026, bulan: 1, ton: 1, luas: 1, bjr: 14.12, jjg_ppk: 0.85, kg_ppk: 12 },
      { tahun: 2026, bulan: 2, ton: 1, luas: 1, bjr: 15.63, jjg_ppk: 0.64, kg_ppk: 10 },
    ]);
    expect(s!.jjg_ppk).toBeCloseTo(1.49, 10);
    expect(s!.kg_ppk).toBe(22);
    expect(s!.bjr).toBeCloseTo(22 / 1.49, 10);
  });
  it("BJR fallback rata-rata bulanan bila Jjg/Pkk kosong", () => {
    const [s] = yearlySummaries([
      { tahun: 2026, bulan: 1, ton: 1, luas: 1, bjr: 14, jjg_ppk: 0, kg_ppk: 0 },
      { tahun: 2026, bulan: 2, ton: 1, luas: 1, bjr: 16, jjg_ppk: 0, kg_ppk: 0 },
    ]);
    expect(s!.bjr).toBe(15);
  });
  it("satu ringkasan per tahun, tahun terbaru di atas", () => {
    const out = yearlySummaries([
      { tahun: 2025, bulan: 12, ton: 5, luas: 10 },
      { tahun: 2026, bulan: 1, ton: 7, luas: 0 },
    ]);
    expect(out.map((s) => s.tahun)).toEqual([2026, 2025]);
    expect(Number.isNaN(out[0]!.ton_ha)).toBe(true);
  });
});

describe("satu sumber dengan rekap_tahunan (data gis_db_v4 estate E005, 2026)", () => {
  // data_histori bulanan (sudah dibulatkan backend): [bulan, bjr, jjg_ppk, kg_ppk]
  const m: Array<[number, number, number, number]> = [
    [1, 17.47, 0.67, 12], [2, 16.83, 0.62, 10], [3, 16.82, 0.66, 11], [4, 16.43, 0.82, 14],
    [5, 16.36, 0.78, 13], [6, 16.17, 1.01, 16], [7, 16.36, 1.08, 18], [8, 15.94, 1.01, 16],
  ];
  const rows = m.map(([bulan, bjr, jjg_ppk, kg_ppk]) => ({ tahun: 2026, bulan, ton: 18025.67 / 8, luas: 1406.53, bjr, jjg_ppk, kg_ppk }));
  const recap = [{ tahun: 2026, jumlah_periode: 8, luas: 1406.53, ton: 18025.67, ton_ha: 12.82, bjr: 16.37, jjg_ppk: 6.66, kg_ppk: 110 }];

  it("hitungan lokal dari data_histori yang dibulatkan menyimpang (sebab bug)", () => {
    const [s] = yearlySummaries(rows);
    expect(s!.bjr).toBeCloseTo(16.54, 2); // Σ Kg/Pkk bulat (110) ÷ Σ Jjg/Pkk (6,65)
    expect(s!.jjg_ppk).toBeCloseTo(6.65, 2);
  });

  it("kartu Total memakai baris rekap_tahunan apa adanya", () => {
    const [s] = yearlySummaries(rows, recap);
    expect(s).toMatchObject({ tahun: 2026, periods: 8, luas: 1406.53, ton: 18025.67, ton_ha: 12.82, bjr: 16.37, jjg_ppk: 6.66, kg_ppk: 110 });
  });

  it("tahun tanpa rekap tetap memakai hitungan lokal", () => {
    const [s] = yearlySummaries(rows, [{ ...recap[0]!, tahun: 2025 }]);
    expect(s!.bjr).toBeCloseTo(16.54, 2);
  });
});

describe("ytdGapMonths", () => {
  it("hanya tahun filter, Jan s/d akhir YTD, urut bulan", () => {
    const rows = [
      { tahun: 2026, bulan: 3 }, { tahun: 2026, bulan: 1 }, { tahun: 2026, bulan: 11 },
      { tahun: 2025, bulan: 2 }, { tahun: 2026, bulan: null },
    ];
    expect(ytdGapMonths(rows, 2026, 10).map((r) => r.bulan)).toEqual([1, 3]);
  });
});
