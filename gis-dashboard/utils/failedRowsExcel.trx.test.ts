import { describe, expect, it } from "vitest";
import { indexTablePreview } from "./geojsonFeatureParts";
import { buildFailedSheets, countFailedPreview, type FailureRow } from "./failedRowsExcel";
import { chunkTrxRows, partRowOffset } from "./trxExcelParts";

describe("Excel data gagal halaman transaksi (multi-part)", () => {
  it("count > 0 sejak part pertama selesai, dan export lengkap = semua baris gagal semua part", () => {
    const headers = ["Kode Blok", "Year", "Month", "Luas"];
    const rows = Array.from({ length: 3450 }, (_, i) => ({
      "Kode Blok": `B${i + 1}`, Year: "2026", Month: "6", Luas: i % 3 === 0 ? "" : String(i),
    }));
    const parts = chunkTrxRows(headers, rows);
    expect(parts.length).toBe(4);
    let analysis: Record<number, FailureRow> = {};
    parts.forEach((part, p) => {
      const offset = partRowOffset(p + 1);
      // table_preview backend trx: no_preview = offset + nomor baris data di part (mulai 1)
      const preview: FailureRow[] = part.rows.map((r, i) => {
        const failed = r.Luas === "";
        const no = offset + i + 1;
        return failed
          ? { no_preview: no, status_analisa: "GAGAL", kode_gagal: "NILAI_TIDAK_VALID", alasan_gagal: `Luas kosong (baris ${no + 1})`,
            ...(no % 9 === 1 ? { gagal_lain: [{ kode: "BLOK_TIDAK_DITEMUKAN", alasan: "blok tidak ada" }] } : {}) }
          : { no_preview: no, status_analisa: "AMAN", kode_gagal: null, alasan_gagal: null };
      });
      analysis = indexTablePreview(analysis as any, preview as any) as any;
      if (p === 0) expect(countFailedPreview(analysis)).toBeGreaterThan(0);
    });
    const expected = rows.filter((r) => r.Luas === "").length;
    expect(countFailedPreview(analysis)).toBe(expected);
    const s = buildFailedSheets({ rows, analysis, kategori: "areal-statement", filename: "as.xlsx", columns: headers });
    expect(s.failedCount).toBe(expected);
    expect(s.data.length).toBe(expected + 1);
    expect(s.data[0]).not.toContain("Geometri (WKT)");
    for (const line of s.data.slice(1) as unknown[][]) {
      const src = rows[(line[1] as number) - 1]!;
      expect(line.slice(5)).toEqual(headers.map((h) => (src as any)[h]));
      expect(src.Luas).toBe("");
    }
    expect(s.data.some((l) => l[2] === "NILAI_TIDAK_VALID; BLOK_TIDAK_DITEMUKAN")).toBe(true);
  });
});
