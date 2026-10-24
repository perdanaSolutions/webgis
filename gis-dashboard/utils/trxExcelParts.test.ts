import { describe, expect, it } from "vitest";
import { TRX_ROWS_PER_PART, chunkTrxRows, partRowOffset } from "./trxExcelParts";
import { TRX_KINDS, missingHeaderGroups } from "./trxUpload";

describe("trxExcelParts", () => {
  it("1.000 baris per part, sama dengan GeoJSON", () => {
    expect(TRX_ROWS_PER_PART).toBe(1000);
    const rows = Array.from({ length: 2500 }, (_, i) => ({ A: String(i) }));
    const parts = chunkTrxRows(["A"], rows);
    expect(parts.map((p) => p.rows.length)).toEqual([1000, 1000, 500]);
  });

  it("feature_offset = jumlah baris sebelum part (0 untuk part 1)", () => {
    expect(partRowOffset(1)).toBe(0);
    expect(partRowOffset(2)).toBe(1000);
    expect(partRowOffset(3, 10)).toBe(20);
  });
});

describe("missingHeaderGroups", () => {
  it("cocok tanpa beda huruf besar/kecil dan spasi", () => {
    const rotasi = TRX_KINDS.find((k) => k.id === "rotasi-pusingan")!;
    const headers = ["periode", "AREA", "pt", "estate", "AFDELING", "blok", "luas", "pokok", "rotasi", "pusingan",
      "statuspusingan", "bulan", "tanggal"];
    expect(missingHeaderGroups(headers, rotasi)).toEqual([]);
    const areal = TRX_KINDS.find((k) => k.id === "areal-statement")!;
    expect(missingHeaderGroups(areal.columns.map((c) => c.toUpperCase()), areal)).toEqual([]);
  });
});
