import { describe, expect, it } from "vitest";

import {
  monthLabel,
  pctOf,
  periodTitle,
  scaleMax,
  tooltipRows,
  type ProductionGroupItem,
} from "../utils/productionGroups";

const item: ProductionGroupItem = {
  kode: "KUTIM2", nama: "KUTIM2",
  aktual_ton: 250591, budget_ton: 276647, aktual_tahun_lalu_ton: 249445,
  aktual_ton_ha: 16.74, budget_ton_ha: 18.48,
  var_budget_ton: -26056, var_budget_pct: -9.42, var_tahun_lalu_ton: 1146, var_tahun_lalu_pct: 0.46,
  luas_tanam: 14967, rut: 17.04,
};

describe("productionGroups", () => {
  it("label periode", () => {
    expect(monthLabel("10-2026")).toBe("Okt 2026");
    expect(periodTitle({ periode_awal: "1-2026", periode_akhir: "10-2026", year_to_date: true,
      tahun_lalu_awal: "1-2025", tahun_lalu_akhir: "10-2025" })).toBe("Year to Date Jan s/d Okt 2026");
    expect(periodTitle({ periode_awal: "10-2026", periode_akhir: "10-2026", year_to_date: false,
      tahun_lalu_awal: "10-2025", tahun_lalu_akhir: "10-2025" })).toBe("Okt 2026");
    expect(periodTitle(null)).toBe("");
  });

  it("skala memakai nilai terbesar dari aktual, budget, dan tahun lalu", () => {
    expect(scaleMax([item])).toBe(276647);
    expect(scaleMax([])).toBe(1);
    expect(pctOf(138323.5, 276647)).toBeCloseTo(50);
    expect(pctOf(-5, 100)).toBe(0);
    expect(pctOf(500, 100)).toBe(100);
  });

  it("tooltip mengikuti urutan referensi dan memberi warna selisih", () => {
    const rows = tooltipRows(item);
    expect(rows.map((r) => r.label)[0]).toBe("Aktual (A) (ton)");
    expect(rows[0]!.value).toBe("250.591");
    const varB = rows.find((r) => r.label === "Var (%) A vs B")!;
    expect(varB).toEqual({ label: "Var (%) A vs B", value: "-9,42 %", tone: "bad" });
    expect(rows.find((r) => r.label === "Var (%) A vs L")!.tone).toBe("good");
    expect(rows.at(-1)).toEqual({ label: "RUT (tahun)", value: "17,04" });
  });
});
