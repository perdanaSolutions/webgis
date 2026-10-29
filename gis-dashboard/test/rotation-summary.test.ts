import { describe, expect, it } from "vitest";
import { rotationTotals } from "../utils/rotationSummary";

// gis_db_v4 estate E005, Jan–Agu 2026: luas tanam 1.406,53 ha tiap bulan, luas panen Σ(area×rotasi) per bulan.
const panen = [5637.75, 5230.96, 5425.12, 5065.49, 4282.87, 5256.52, 5478.45, 5104.09];
const rows = panen.map((luasPanen) => ({ luas: 1406.53, luasPanen }));

describe("rotationTotals", () => {
  it("pakai ringkasan backend apa adanya", () => {
    expect(rotationTotals(rows, { luas_panen: 41481.25, luas_tanam: 1406.53, rotasi: 29.49 }))
      .toEqual({ luas_panen: 41481.25, luas_tanam: 1406.53, rotasi: 29.49 });
  });
  it("cadangan lokal: Σ luas panen ÷ luas tanam bulan terakhir (bukan SUM rotasi)", () => {
    const t = rotationTotals(rows)!;
    expect(t.luas_panen).toBeCloseTo(41481.25, 2);
    expect(t.rotasi!).toBeCloseTo(29.49, 2);
  });
  it("luas tanam ikut bulan terakhir", () => {
    const t = rotationTotals([{ luas: 100, luasPanen: 300 }, { luas: 120, luasPanen: 360 }])!;
    expect(t).toEqual({ luas_panen: 660, luas_tanam: 120, rotasi: 5.5 });
  });
  it("respons lama tanpa luas_panen -> null", () => {
    expect(rotationTotals([{ luas: 100, luasPanen: null }])).toBeNull();
  });
});
