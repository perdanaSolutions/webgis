import { describe, expect, it } from "vitest";
import { periodAvailabilityNotice } from "../utils/mapBlokPopup";

describe("periodAvailabilityNotice", () => {
  const requested = { bulan: "2", tahun: "2022" };

  it("memberi pesan tidak ada data untuk periode sebelum transaksi pertama", () => {
    const notice = periodAvailabilityNotice({ mode: "TIDAK_ADA_DATA" }, requested);
    expect(notice).toBe("Tidak ada data pada periode Februari 2022.");
  });

  it("memberi pesan data terakhir bila periode tidak tersedia", () => {
    const notice = periodAvailabilityNotice(
      { mode: "LATEST_TAHUN_TANAM", periode: { bulan: 12, tahun: 2025 } },
      requested,
    );
    expect(notice).toContain("Periode Februari 2022 tidak tersedia");
    expect(notice).toContain("Desember 2025");
  });

  it("tanpa pesan bila periode ada", () => {
    expect(periodAvailabilityNotice({ mode: "SPESIFIK_TAHUN_TANAM" }, requested)).toBeUndefined();
  });
});
