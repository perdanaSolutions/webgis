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
  it("satu ringkasan per tahun, tahun terbaru di atas", () => {
    const out = yearlySummaries([
      { tahun: 2025, bulan: 12, ton: 5, luas: 10 },
      { tahun: 2026, bulan: 1, ton: 7, luas: 0 },
    ]);
    expect(out.map((s) => s.tahun)).toEqual([2026, 2025]);
    expect(Number.isNaN(out[0]!.ton_ha)).toBe(true);
  });
});
