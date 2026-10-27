import { describe, expect, it } from "vitest";
import { indexTablePreview } from "./geojsonFeatureParts";
import {
  buildFailedSheets, CELL_LIMIT, failedExportFilename, geometryToWkt, safeCell, TRUNC_NOTE, type FailureRow,
} from "./failedRowsExcel";

const PART = 1000;

function feature(no: number) {
  return { type: "Feature", properties: { OBJECTID: no, Blok: `B${no}`, Est_ID: "E001", Catatan: `n${no}` },
    geometry: { type: "Point", coordinates: [110 + no / 1e5, 0.5] } };
}

/** table_preview satu part persis seperti backend (no_preview = offset + nomor di part, mulai 1). */
function partPreview(offset: number, size: number, failed: (globalNo: number) => boolean): FailureRow[] {
  return Array.from({ length: size }, (_, i) => {
    const no = offset + i + 1;
    return failed(no)
      ? { no_preview: no, status_analisa: "GAGAL", kode_gagal: "GEOMETRI_TIDAK_VALID", alasan_gagal: `rusak #${no}` }
      : { no_preview: no, status_analisa: "AMAN", kode_gagal: null, alasan_gagal: null };
  });
}

describe("failedRowsExcel", () => {
  it("3 part >1000 gagal: semua data gagal masuk & kolom asli sama dengan baris preview di nomor itu", () => {
    const total = 3 * PART + 600; // 4 part: 1000,1000,1000,600 -> uji juga part terakhir tidak penuh
    const rows = Array.from({ length: total }, (_, i) => feature(i + 1));
    const isFailed = (no: number) => no % 7 !== 0; // > 1000 gagal per part
    let analysis: Record<number, FailureRow> = {};
    for (let p = 0; p * PART < total; p++) {
      analysis = indexTablePreview(analysis as any, partPreview(p * PART, Math.min(PART, total - p * PART), isFailed) as any) as any;
    }
    const expected = rows.filter((_, i) => isFailed(i + 1)).length;
    expect(expected).toBeGreaterThan(3000);

    const sheets = buildFailedSheets({ rows, analysis, kategori: "blok", filename: "kebun.geojson",
      columns: ["OBJECTID", "Blok", "Est_ID", "Catatan"] });
    expect(sheets.failedCount).toBe(expected);
    expect(sheets.data.length).toBe(expected + 1);
    const header = sheets.data[0] as string[];
    expect(header.slice(0, 9)).toEqual(["No", "No Data di File", "Kode Gagal", "Keterangan Kode", "Alasan Gagal",
      "OBJECTID", "Blok", "Est_ID", "Catatan"]);
    for (const line of sheets.data.slice(1) as unknown[][]) {
      const no = line[1] as number;
      const src = rows[no - 1]!;
      expect(line.slice(5, 9)).toEqual([src.properties.OBJECTID, src.properties.Blok, "E001", src.properties.Catatan]);
      expect(line[4]).toBe(`rusak #${no}`);
      expect(line[9]).toBe(geometryToWkt(src.geometry));
    }
    expect(sheets.summary.find((r) => r[0] === "Total Data Gagal")?.[1]).toBe(expected);
    expect(sheets.summary.find((r) => r[0] === "GEOMETRI_TIDAK_VALID")?.[1]).toBe(expected);
  });

  it("satu baris per data; beberapa kode digabung", () => {
    const rows = [feature(1), feature(2)];
    const analysis = { 2: { no_preview: 2, status_analisa: "GAGAL", kode_gagal: "OBJECTID_GANDA", alasan_gagal: "dobel dgn data #1",
      gagal_lain: [{ kode: "GEOMETRI_TIDAK_VALID", alasan: "kosong" }] } } as Record<number, FailureRow>;
    const s = buildFailedSheets({ rows, analysis, kategori: "tph", filename: "x.geojson" });
    expect(s.data.length).toBe(2);
    expect(s.data[1]![2]).toBe("OBJECTID_GANDA; GEOMETRI_TIDAK_VALID");
    expect(s.data[1]![4]).toBe("1. [OBJECTID_GANDA] dobel dgn data #1\n2. [GEOMETRI_TIDAK_VALID] kosong");
  });

  it("baris Excel transaksi (tanpa geometri)", () => {
    const rows = [{ Blok: "A1", Luas: "=1+1" }];
    const s = buildFailedSheets({ rows, analysis: { 1: { no_preview: 1, status_analisa: "GAGAL", kode_gagal: "NILAI_TIDAK_VALID", alasan_gagal: "x" } },
      kategori: "areal-statement", filename: "as.xlsx", columns: ["Blok", "Luas"] });
    expect(s.data[0]).not.toContain("Geometri (WKT)");
    expect(s.data[1]!.slice(5)).toEqual(["A1", "'=1+1"]);
  });

  it("escape formula & potong sel panjang", () => {
    for (const v of ["=A1", "+1", "-1", "@x", "\t=1"]) expect(safeCell(v)).toBe(`'${v}`);
    const long = safeCell("y".repeat(40000)) as string;
    expect(long.length).toBe(CELL_LIMIT);
    expect(long.endsWith(TRUNC_NOTE)).toBe(true);
  });

  it("WKT poligon & nama file WIB", () => {
    expect(geometryToWkt({ type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }))
      .toBe("POLYGON ((0 0, 1 0, 1 1, 0 0))");
    expect(failedExportFilename("blok", "Kebun A (final)_part1of3.geojson", new Date("2026-10-27T00:05:00Z")))
      .toBe("data_gagal_blok_Kebun_A_final_20261027-0705.xlsx");
  });
});
