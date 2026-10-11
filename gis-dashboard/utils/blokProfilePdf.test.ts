import { describe, expect, it } from "vitest";

import { buildPdfLegend, pdfFileName, plainAttribution, rgbOf } from "./blokProfilePdf";

describe("blokProfilePdf", () => {
  it("membuat nama berkas dari label scope", () => {
    expect(pdfFileName("PT ABC / Estate 1")).toBe("blok-profile-pt_abc_estate_1.pdf");
    expect(pdfFileName("   ")).toBe("blok-profile-semua-wilayah.pdf");
  });

  it("menyusun legenda dari batas, yield gap, dan layer aktif", () => {
    const items = buildPdfLegend({
      showBlocks: true,
      showYieldGap: true,
      budgetColors: { OPTIMUM: true, "GAP I": false, "GAP II": true, "GAP III": true },
      overlays: [
        {
          name: "Slope",
          legend: [{ label: "0-3", color: "#d7e4c8" }],
          style: { defaultColor: "#fca5a5" },
        },
        { name: "Jalan", legend: [], style: { defaultColor: "#a16207" } },
      ],
    });
    expect(items.map((item) => item.label)).toEqual([
      "Batas blok",
      "Optimum",
      "Gap II",
      "Gap III",
      "Slope · 0-3",
      "Jalan",
    ]);
  });

  it("mengubah warna hex dan atribusi HTML", () => {
    expect(rgbOf("#638840")).toEqual([99, 136, 64]);
    expect(rgbOf("#abc")).toEqual([170, 187, 204]);
    expect(plainAttribution("Tiles &copy; Esri &mdash; <a href=\"x\">Esri</a>")).toBe("Tiles © Esri — Esri");
  });
});
