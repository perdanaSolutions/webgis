import { describe, expect, it } from "vitest";
import { yearlySummaries } from "../utils/productionSummary";

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
