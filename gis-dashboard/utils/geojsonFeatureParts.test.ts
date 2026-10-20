import { describe, expect, it } from "vitest";
import {
  GEOJSON_FEATURES_PER_PART,
  chunkFeatureCollection,
  mergeAnalyzeResults,
  mergeExecuteResults,
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
