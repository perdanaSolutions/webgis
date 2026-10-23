import { describe, expect, it } from "vitest";

import { plantingYearLegend, readPlantingYear } from "./mapLayers";

const block = (tahun: number | null, warna: string | null) => ({
  properties: { areal_statement: { tahun_tanam: tahun, warna_tahun_tanam: warna } },
});

describe("tahun tanam", () => {
  it("membaca tahun tanam dan warnanya dari areal_statement", () => {
    expect(readPlantingYear(block(2007, "#0000FF").properties)).toEqual({ tahun: 2007, color: "#0000FF" });
    expect(readPlantingYear(block(1999, null).properties)).toBeNull();
    expect(readPlantingYear({})).toBeNull();
  });

  it("legenda hanya berisi tahun yang ada, urut naik, tanpa duplikat", () => {
    const legend = plantingYearLegend([
      block(2008, "#FF0000"), block(2006, "#FF6600"), block(2008, "#FF0000"), block(null, null), { properties: null },
    ]);
    expect(legend).toEqual([
      { label: "Tahun Tanam 2006", color: "#FF6600" },
      { label: "Tahun Tanam 2008", color: "#FF0000" },
    ]);
  });
});
