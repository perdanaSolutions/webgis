import { describe, expect, it } from "vitest";
import { blokDataPeriodLabel, MONTHS_FULL_ID } from "../utils/blokPeriodLabel";
import { infoPageFirstMove } from "../utils/blokProfilePdf";

describe("blokDataPeriodLabel", () => {
  it("terbaru vs periode spesifik", () => {
    expect(blokDataPeriodLabel({ bulan: 10, tahun: 2026 }, false)).toBe("Data terbaru: Oktober 2026");
    expect(blokDataPeriodLabel({ bulan: 9, tahun: 2026 }, true)).toBe("Data Periode: September 2026");
  });
  it("12 bulan nama lengkap", () => {
    const want = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
    expect([...MONTHS_FULL_ID]).toEqual(want);
    want.forEach((name, i) => {
      expect(blokDataPeriodLabel({ bulan: i + 1, tahun: 2025 }, false)).toBe(`Data terbaru: ${name} 2025`);
      expect(blokDataPeriodLabel({ bulan: i + 1, tahun: 2025 }, true)).toBe(`Data Periode: ${name} 2025`);
    });
  });
  it("periode tidak lengkap / kosong", () => {
    expect(blokDataPeriodLabel({ bulan: null, tahun: 2026 }, false)).toBe("Data terbaru: 2026");
    expect(blokDataPeriodLabel({ bulan: 13, tahun: 2026 }, true)).toBe("Data Periode: 2026");
    expect(blokDataPeriodLabel(null, false)).toBe("");
    expect(blokDataPeriodLabel(undefined, true)).toBe("");
    expect(blokDataPeriodLabel({ bulan: 5, tahun: 0 }, false)).toBe("");
  });
});

describe("urutan halaman PDF", () => {
  it("Informasi Blok (halaman kartu pertama) dipindah ke halaman 1", () => {
    expect(infoPageFirstMove(5)).toEqual({ from: 2, before: 1 });
    expect(infoPageFirstMove(2)).toEqual({ from: 2, before: 1 });
    expect(infoPageFirstMove(1)).toBeNull();
    expect(infoPageFirstMove(0)).toBeNull();
  });
});
