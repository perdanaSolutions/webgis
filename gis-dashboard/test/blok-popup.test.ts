import { describe, expect, it } from "vitest";
import { blokPopupFromDetail, buildBlokPopupHtml } from "../utils/mapBlokPopup";

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
});
