import { describe, expect, it } from "vitest";
import { blokPopupFromDetail, buildBlokPopupHtml, comparisonFromProperties } from "../utils/mapBlokPopup";

const detail = {
  informasi_blok: {
    blok_id: 299,
    nama_blok: "Blok D065",
    kode_blok: "D065",
    tipe_blok: "Inti",
    tahun_tanam: 2009,
    bulan_tanam: "Sep",
    jenis_bibit: "Socfin",
    status_tanam: "TM",
    jenis_topografi: "GELOMBANG",
    jenis_tanah: "TANAH MINERAL",
    luas_tanam: 11.64,
    luas_tanah: 26.43,
    pokok: 1483,
    sph: 127.41,
    tbs: { aktual: 44681.8, budget: 15290.0, sensus: 15940.0 },
    jjg: { aktual: 2709, budget: 1062, sensus: 1124 },
    bjr: { aktual: 16.49, budget: 14.4, sensus: 0.0 },
    yield: { aktual: 3.84, budget: 1.31, sensus: 1.37 },
    gap_act_bgt: { value: 193.13, kategori: "OPTIMUM" },
    gap_act_sns: { value: 180.29, kategori: "OPTIMUM" },
    hierarki: {
      kode_area: "BERAU",
      nama_area: "BERAU",
      kode_pt: "1100",
      nama_pt: "PT. TANJUNG BUYU PERKASA PLANTATION",
      kode_est: "E004",
      nama_estate: "Biatan Estate",
      kode_afd: "AFDI03",
      nama_afd: "AFDI03",
    },
  },
};

describe("popup detail blok", () => {
  it("menampilkan field informasi_blok apa adanya", () => {
    const data = blokPopupFromDetail(detail, { bulan: "9", tahun: "2026" });
    expect(data).toMatchObject({
      area: "BERAU",
      pt: "PT. TANJUNG BUYU PERKASA PLANTATION",
      estate: "Biatan Estate",
      afdeling: "AFDI03",
      blok: "D065",
      tipe: "Inti",
      tahunTanam: "2009",
      bulanTanam: "Sep",
      bibit: "Socfin",
      statusTanam: "TM",
      topografi: "GELOMBANG",
      jenisTanah: "TANAH MINERAL",
      luasTanam: "11,64",
      luasTanah: "26,43",
      pokok: "1.483",
      sph: "127,41",
      tbs: { aktual: "44.681,80", budget: "15.290", sensus: "15.940" },
      jjg: { aktual: "2.709", budget: "1.062", sensus: "1.124" },
      bjr: { aktual: "16,49", budget: "14,40", sensus: "0" },
      yieldHa: { aktual: "3,84", budget: "1,31", sensus: "1,37" },
      gapBudget: "193,13 %",
      kategoriBudget: "OPTIMUM",
      gapSensus: "180,29 %",
      kategoriSensus: "OPTIMUM",
    });

    const html = buildBlokPopupHtml(data);
    expect(html).toContain("Tipe Blok");
    expect(html).toContain("TANAH MINERAL");
    expect(html).toContain("Gap Budget");
    expect(html).toContain("Gap Sensus");
    expect(html).toContain("44.681,80");
    expect(html).not.toContain("Kg/pkk");
  });

  it("menampilkan TBS s/d yield dan persen gap untuk periode pembanding", () => {
    const comparison = comparisonFromProperties({
      produksi_tbs_comparison: {
        periode_awal: "1-2025", periode_akhir: "3-2025",
        tbs_aktual: 12000, tbs_budget: 10000, tbs_sensus: 11000,
        janjang_aktual: 800, janjang_budget: 700, janjang_sensus: 750,
        bjr_aktual: 15, bjr_budget: 14.29, bjr_sensus: 14.67,
        y_aktual: 1.03, y_budget: 0.86, y_sensus: 0.95,
        gap_budget_pct: 19.77, kategori_budget: "OPTIMUM",
        gap_sensus_pct: -25.5, kategori_sensus: "GAP II",
      },
    });
    expect(comparison).toEqual({
      periode: "1-2025 s/d 3-2025",
      tbs: { aktual: "12.000", budget: "10.000", sensus: "11.000" },
      jjg: { aktual: "800", budget: "700", sensus: "750" },
      bjr: { aktual: "15", budget: "14,29", sensus: "14,67" },
      yieldHa: { aktual: "1,03", budget: "0,86", sensus: "0,95" },
      gapBudget: "19,77 %",
      kategoriBudget: "OPTIMUM",
      gapSensus: "-25,50 %",
      kategoriSensus: "GAP II",
    });

    const html = buildBlokPopupHtml(blokPopupFromDetail(detail), { comparison });
    const section = html.slice(html.indexOf("data-popup-comparison"));
    expect(section).toContain("1-2025 s/d 3-2025");
    expect(section).toContain("12.000");
    expect(section).toContain("0,95");
    expect(section).toContain("19,77 %");
    expect(section).toContain("-25,50 %");
  });

  it("tanpa filter pembanding tidak ada bagian pembanding", () => {
    expect(comparisonFromProperties({})).toBeNull();
    expect(buildBlokPopupHtml(blokPopupFromDetail(detail))).not.toContain("data-popup-comparison");
  });
});
