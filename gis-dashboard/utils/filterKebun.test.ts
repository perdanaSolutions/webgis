import { describe, expect, it } from "vitest";
import { afdelingOptionsFrom, blockOptionsFrom, geometrySimplifyMeters, isAllScope } from "./filterKebun";

describe("filterKebun", () => {
  it("Semua area / area / PT -> geometri disederhanakan 1 m; estate ke bawah asli", () => {
    expect(geometrySimplifyMeters({ estate: "", afdeling: "", blokId: "" })).toBe(1);
    expect(geometrySimplifyMeters({ estate: "E001", afdeling: "", blokId: "" })).toBeUndefined();
    expect(geometrySimplifyMeters({ estate: "", afdeling: "", blokId: "12" })).toBeUndefined();
  });

  it("isAllScope: semua field kosong = semua wilayah hak akses", () => {
    expect(isAllScope({ area: "", pt: "", estate: "", afdeling: "", blokId: "" })).toBe(true);
    expect(isAllScope({ area: "BERAU", pt: "", estate: "", afdeling: "", blokId: "" })).toBe(false);
  });

  it("opsi afdeling: kode kembar digabung jadi satu", () => {
    expect(
      afdelingOptionsFrom([
        { kode_afd: "AFDI02" },
        { kode_afd: "AFDI01" },
        { kode_afd: "AFDI02" },
        { kode_afd: "AFDI02" },
        { kode_afd: "" },
        { kode_afd: null },
      ]),
    ).toEqual([
      { label: "AFDI01", value: "AFDI01" },
      { label: "AFDI02", value: "AFDI02" },
    ]);
  });

  it("opsi blok: urut, kode kembar diberi estate/afdeling, id kosong dibuang", () => {
    const opts = blockOptionsFrom([
      { blok_id: 2, kode_blok: "B008", kode_est: "E1", kode_afd: "A1" },
      { blok_id: 3, kode_blok: "A001", kode_est: "E1", kode_afd: "A1" },
      { blok_id: 4, kode_blok: "B008", kode_est: "E2", kode_afd: "A3" },
      { blok_id: "", kode_blok: "X" },
    ]);
    expect(opts).toEqual([
      { label: "A001", value: "3" },
      { label: "B008 (E1/A1)", value: "2" },
      { label: "B008 (E2/A3)", value: "4" },
    ]);
  });

  it("4.000+ blok diproses cepat (satu request, tanpa batas 30 halaman)", () => {
    const rows = Array.from({ length: 4027 }, (_, i) => ({ blok_id: i + 1, kode_blok: `B${i}`, kode_est: "E", kode_afd: "A" }));
    const t0 = performance.now();
    expect(blockOptionsFrom(rows)).toHaveLength(4027);
    expect(performance.now() - t0).toBeLessThan(500);
  });
});
