/**
 * WORKSHOP — Yield Gap 2 (aktual vs sensus)
 *
 * Tes ini sengaja GAGAL di branch workshop/yield-gap-mulai. Tugas peserta: buat semua tes lulus,
 * lalu sambungkan ke peta. Backend sudah mengirim `kategori_sensus` di properties.produksi_tbs
 * (lihat backend_fastapi/app/services/map_service.py · _produksi_payload), jadi tidak ada perubahan backend.
 *
 * Langkah:
 *  1. utils/mapLayers.ts          — YIELD_GAP_BASES, type YieldGapBasis, readGapCategory(); fungsi lama jadi pembungkus.
 *  2. stores/blokProfileStore.ts  — redactProperties menyimpan SEMUA kategori (bukan hanya kategori_budget).
 *  3. BlokProfileView.vue         — satu mode pewarnaan (none | tahun-tanam | budget | sensus) menggantikan dua boolean.
 *  4. BlokProfileMap.vue          — blockFill() & comparisonMarkerColor() memakai pembanding aktif.
 *  5. FilterPanel.vue             — saklar Yield Gap dibuat dari YIELD_GAP_BASES (v-for).
 *  6. exportBlokProfilePdf.ts, blokProfilePdf.ts — warna & legenda PDF ikut pembanding aktif.
 *  7. Uji manual: saklar saling mematikan, titik pembanding ikut, PDF benar, role tanpa hak produksi tetap berwarna.
 *
 * Jalankan: npx vitest run utils/mapLayers.yieldGap.test.ts
 */
import { describe, expect, it } from "vitest";

import { buildPdfLegend } from "./blokProfilePdf";
import {
  readBudgetCategory,
  readComparisonBudgetCategory,
  readGapCategory,
  YIELD_GAP_BASES,
} from "./mapLayers";

const blok = {
  produksi_tbs: { kategori_budget: "OPTIMUM", kategori_sensus: "GAP 2" },
  produksi_tbs_comparison: { kategori_budget: "GAP I", kategori_sensus: "gap iii" },
};

describe("daftar pembanding Yield Gap", () => {
  it("berisi budget dan sensus dengan field kategori dari API", () => {
    expect(YIELD_GAP_BASES.map((b) => [b.key, b.field])).toEqual([
      ["budget", "kategori_budget"],
      ["sensus", "kategori_sensus"],
    ]);
  });
});

describe("readGapCategory", () => {
  it("membaca kategori periode sesuai pembanding", () => {
    expect(readGapCategory(blok, "budget")).toBe("OPTIMUM");
    expect(readGapCategory(blok, "sensus")).toBe("GAP II");
  });

  it("membaca kategori periode pembanding (titik tengah)", () => {
    expect(readGapCategory(blok, "budget", true)).toBe("GAP I");
    expect(readGapCategory(blok, "sensus", true)).toBe("GAP III");
  });

  it("membaca kategori di level atas (sisa redaksi untuk role tanpa hak produksi)", () => {
    expect(readGapCategory({ kategori_sensus: "GAP I" }, "sensus")).toBe("GAP I");
  });

  it("kosong bila tidak ada data", () => {
    expect(readGapCategory({}, "sensus")).toBe("");
    expect(readGapCategory(null, "budget", true)).toBe("");
  });

  it("fungsi lama tetap bekerja (pembanding budget)", () => {
    expect(readBudgetCategory(blok)).toBe("OPTIMUM");
    expect(readComparisonBudgetCategory(blok)).toBe("GAP I");
  });
});

describe("legenda PDF", () => {
  const base = { showBlocks: false, showYieldGap: true, budgetColors: {}, overlays: [] };

  it("budget: label kategori seperti sebelumnya", () => {
    expect(buildPdfLegend({ ...base, yieldGapBasis: "budget" }).map((i) => i.label))
      .toEqual(["Optimum", "Gap I", "Gap II", "Gap III"]);
  });

  it("sensus: label diberi nama pembanding agar tidak tertukar dengan budget", () => {
    expect(buildPdfLegend({ ...base, yieldGapBasis: "sensus" }).map((i) => i.label))
      .toEqual(["Sensus · Optimum", "Sensus · Gap I", "Sensus · Gap II", "Sensus · Gap III"]);
  });
});
