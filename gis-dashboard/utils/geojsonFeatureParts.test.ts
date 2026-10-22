import { describe, expect, it } from "vitest";
import {
  GEOJSON_FEATURES_PER_PART,
  chunkFeatureCollection,
  mergeAnalyzeResults,
  mergeExecuteResults,
  indexTablePreview,
  isPartAnalyzeResponse,
  partFeatureOffset,
  type GeoJsonCollection,
} from "./geojsonFeatureParts";

function collection(n: number): GeoJsonCollection {
  return {
    type: "FeatureCollection",
    features: Array.from({ length: n }, (_, i) => ({
      type: "Feature",
      properties: { id: i },
      geometry: { type: "Point", coordinates: [i, i] },
    })),
  };
}

describe("chunkFeatureCollection", () => {
  it("memecah sesuai ukuran part", () => {
    const parts = chunkFeatureCollection(collection(2500), 1000);
    expect(parts).toHaveLength(3);
    expect(parts[0]!.features).toHaveLength(1000);
    expect(parts[1]!.features).toHaveLength(1000);
    expect(parts[2]!.features).toHaveLength(500);
  });

  it("default 1000 feature per part", () => {
    expect(GEOJSON_FEATURES_PER_PART).toBe(1000);
    expect(chunkFeatureCollection(collection(1000))).toHaveLength(1);
  });
});

describe("mergeAnalyzeResults", () => {
  it("menggabungkan status dan angka", () => {
    const merged = mergeAnalyzeResults([
      {
        status_analisis: "SIAP",
        kesimpulan: "ok",
        total_data: 1000,
        peringatan: [{ kode: "A", jumlah: 2, pesan: "a" }],
        rincian: { data_ditolak: [{ x: 1 }] },
      },
      {
        status_analisis: "SIAP_DENGAN_CATATAN",
        total_data: 500,
        peringatan: [{ kode: "A", jumlah: 3, pesan: "a" }],
        rincian: { data_ditolak: [{ x: 2 }] },
      },
    ]);
    expect(merged.status_analisis).toBe("SIAP_DENGAN_CATATAN");
    expect(merged.total_data).toBe(1500);
    expect(merged.peringatan[0].jumlah).toBe(5);
    expect(merged.rincian.data_ditolak).toHaveLength(2);
  });
});

describe("mergeExecuteResults", () => {
  it("menjumlahkan detail statistik", () => {
    const merged = mergeExecuteResults([
      { status: "success", detail: { sukses: 10, status_proses: "SUCCESS" } },
      { status: "success", detail: { sukses: 5, status_proses: "PARTIAL_SUCCESS" } },
    ]);
    expect(merged.detail.sukses).toBe(15);
    expect(merged.detail.status_proses).toBe("PARTIAL_SUCCESS");
    expect(merged.parts).toBe(2);
  });
});

function partResponse(part: number, total: number, offset: number, gagal: number[]) {
  const rows = Array.from({ length: 3 }, (_, i) => {
    const no = offset + i + 1;
    const failed = gagal.includes(no);
    return {
      no_preview: no,
      status_analisa: failed ? "GAGAL" : "AMAN",
      kode_gagal: failed ? "BLOK_TIDAK_DITEMUKAN" : null,
      alasan_gagal: failed ? "Blok X tidak ada di master." : null,
    };
  });
  return {
    kategori: "landuse",
    bulan: 1,
    tahun: 2026,
    part,
    total_part: total,
    data: {
      table_preview: rows,
      analisa_aman: {
        jumlah_data: 3 - gagal.length,
        rincian: { per_estate: [{ estate: `E${part}`, data_siap: 3 - gagal.length }] },
        catatan: [{ kode: "MENGGANTI_DATA_LAMA", level: "INFO", jumlah: 1, pesan: "x" }],
      },
      analisa_gagal: {
        jumlah_data: gagal.length,
        per_kode: gagal.length
          ? [{ kode: "BLOK_TIDAK_DITEMUKAN", keterangan: "blok", jumlah: gagal.length,
               data: gagal.map((n) => ({ no_preview: n, alasan: "x" })) }]
          : [],
        rincian: { data_ditolak: gagal.map((n) => ({ no_preview: n, kode: "BLOK_TIDAK_DITEMUKAN", alasan: "x" })) },
        peringatan: gagal.length
          ? [{ kode: "BLOK_TIDAK_DITEMUKAN", level: "PERINGATAN", jumlah: gagal.length, pesan: "y" }]
          : [],
      },
      ringkasan: { status_analisis: gagal.length ? "SIAP_DENGAN_CATATAN" : "SIAP", kesimpulan: "k", total_data_landuse: 3 },
    },
  };
}

describe("partFeatureOffset", () => {
  it("offset global per part", () => {
    expect(partFeatureOffset(1)).toBe(0);
    expect(partFeatureOffset(3)).toBe(2 * GEOJSON_FEATURES_PER_PART);
  });
});

describe("mergeAnalyzeResults (respons per part)", () => {
  it("menggabung table_preview, analisa_aman dan analisa_gagal sesuai urutan part", () => {
    const merged = mergeAnalyzeResults([partResponse(2, 2, 1000, [1002]), partResponse(1, 2, 0, [3])]);
    expect(merged.total_part).toBe(2);
    expect(merged.table_preview.map((r: any) => r.no_preview)).toEqual([1001, 1002, 1003, 1, 2, 3]);
    expect(merged.per_part.map((p: any) => p.part)).toEqual([1, 2]);
    expect(merged.per_part[1].no_preview_awal).toBe(1001);
    expect(merged.analisa_aman.jumlah_data).toBe(4);
    expect(merged.analisa_aman.rincian.per_estate.map((r: any) => r.estate)).toEqual(["E1", "E2"]);
    expect(merged.analisa_aman.catatan[0].jumlah).toBe(2);
    expect(merged.analisa_gagal.jumlah_data).toBe(2);
    expect(merged.analisa_gagal.per_kode[0].jumlah).toBe(2);
    expect(merged.analisa_gagal.per_kode[0].data.map((d: any) => d.no_preview)).toEqual([3, 1002]);
    // bentuk lama tetap tersedia untuk AnalysisResult
    expect(merged.status_analisis).toBe("SIAP_DENGAN_CATATAN");
    expect(merged.total_data_landuse).toBe(6);
    expect(merged.rincian.data_ditolak).toHaveLength(2);
  });

  it("indexTablePreview memetakan no_preview ke hasil analisa", () => {
    const map = indexTablePreview({}, partResponse(1, 1, 0, [2]).data.table_preview);
    expect(map[2]!.status_analisa).toBe("GAGAL");
    expect(map[1]!.kode_gagal).toBeNull();
    expect(isPartAnalyzeResponse(partResponse(1, 1, 0, []))).toBe(true);
    expect(isPartAnalyzeResponse({ status_analisis: "SIAP" })).toBe(false);
  });
});
