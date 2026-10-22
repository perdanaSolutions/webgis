import { describe, expect, it } from "vitest";

import { buildArealReport } from "./arealStatementReport";

const summary = {
  periode: { areal_statement: "10-2026", landuse: "9-2026" },
  areal_tanam: {
    total_luas_tanam: 100,
    per_status: [{ status: "TM", label: "TM", luas_tanam: 90 }, { status: "TB", label: "TB", luas_tanam: 10 }],
    per_tahun_tanam: [
      { tahun_tanam: 2006, warna: "#FF6600", luas_tanam: 60, persen: 60 },
      { tahun_tanam: 2007, warna: "#0000FF", luas_tanam: 40, persen: 40 },
    ],
  },
  populasi: {
    kelas: [
      { kode: "ATAS_136", label: "x", jumlah_blok: 3, luas_tanam: 86, persen: 86 },
      { kode: "ANTARA_130_135", label: "x", jumlah_blok: 1, luas_tanam: 12, persen: 12 },
      { kode: "BAWAH_130", label: "x", jumlah_blok: 1, luas_tanam: 2, persen: 2 },
    ],
  },
  areal_non_tanam: {
    total_luas: 30,
    per_baris: [
      { kode: "LC", label: "LC", luas: 5, persen: 0 },
      { kode: "BIBITAN", label: "Bibitan", luas: 10, persen: 0 },
      { kode: "BUKIT_SUNGAI_RAWA", label: "Bukit", luas: 12, persen: 0 },
      { kode: "LAINNYA", label: "Lainnya", luas: 3, persen: 0 },
    ],
  },
  total: { grand_total_areal: 130 },
};

const luasOf = (rows: ReturnType<typeof buildArealReport>, label: string) => rows.find((r) => r.label === label)?.luas;

describe("buildArealReport", () => {
  it("menyusun baris sesuai laporan areal statement", () => {
    const rows = buildArealReport(summary);
    expect(rows.map((r) => r.label)).toEqual([
      "Tanaman (TM+TBM+TB)", "Tahun Tanam 2006", "Tahun Tanam 2007", "Tanaman Baru (TB)",
      "Populasi Tanaman (PKK/HA)", "Diatas 136 Pokok/Ha", "130 - 135 Pokok/Ha", "Dibawah 130 Pokok/Ha",
      "Pembukaan Lahan / LC", "a. LC (Perun) Dikerjakan", "b. LC (Perun) Belum Dikerjakan",
      "Total Ditanam + LC (Perun)", "Bibitan", "Emplasemen/Pondok", "Pabrik", "Jalan/Jembatan/Prasarana Lain",
      "Cadangan", "Okupasi", "Tanah Desa", "Bukit, Sungai, Rawa, Tandus dll", "Lainnya", "Grand Total Areal",
    ]);
    expect(rows[1]).toMatchObject({ swatch: "#FF6600", luas: 60 });
    expect(rows[5]).toMatchObject({ dot: "#22a33a", luas: 86, persen: 86 });
    expect(luasOf(rows, "Tanaman Baru (TB)")).toBe(10);
    expect(luasOf(rows, "Pembukaan Lahan / LC")).toBe(5);
    expect(luasOf(rows, "Total Ditanam + LC (Perun)")).toBe(105);
    expect(luasOf(rows, "Pabrik")).toBe(0);
    expect(luasOf(rows, "Tanah Desa")).toBeNull();
    expect(luasOf(rows, "Grand Total Areal")).toBe(130);
  });

  it("baris landuse kosong (null) bila tidak ada data landuse", () => {
    const rows = buildArealReport({ ...summary, areal_non_tanam: null, total: null });
    expect(luasOf(rows, "Bibitan")).toBeNull();
    expect(luasOf(rows, "Total Ditanam + LC (Perun)")).toBe(100);
    expect(luasOf(rows, "Grand Total Areal")).toBeNull();
    expect(rows.some((r) => r.label === "Lainnya")).toBe(false);
  });
});
