import { describe, expect, it } from "vitest";
import {
  AFDELING_SELECTED_WEIGHT, AFDELING_WEIGHT, afdelingLabelsVisible, afdelingPopupRows, afdelingStyle, ringsDistance,
} from "../utils/afdelingBoundary";

describe("batas afdeling", () => {
  it("label hanya di skala 2–10 km dan bisa disembunyikan", () => {
    expect(afdelingLabelsVisible(1000)).toBe(false);
    expect(afdelingLabelsVisible(2000)).toBe(true);
    expect(afdelingLabelsVisible(10000)).toBe(true);
    expect(afdelingLabelsVisible(20000)).toBe(false);
    expect(afdelingLabelsVisible(5000, true)).toBe(false);
  });

  it("popup: Estate short name (cadangan kode), Afdeling, Jumlah blok, Luas", () => {
    expect(afdelingPopupRows({ kode_est: "E1", estate_short_name: "KSE", kode_afd: "AFD1", n_blok: 24, luas_ha: 512.345 }))
      .toEqual([["Estate", "KSE"], ["Afdeling", "AFD1"], ["Jumlah blok", "24"], ["Luas (ha)", "512,35"]]);
    expect(afdelingPopupRows({ kode_est: "E1", kode_afd: "A" }, { E1: "SHORT" })[0]).toEqual(["Estate", "SHORT"]);
    expect(afdelingPopupRows({ kode_est: "E2", kode_afd: "A" })[0]).toEqual(["Estate", "E2"]);
  });

  it("garis tanpa isi, afdeling terpilih lebih tebal", () => {
    expect(afdelingStyle({ kode_afd: "AFD1" }, "")).toMatchObject({ fill: false, weight: AFDELING_WEIGHT });
    expect(afdelingStyle({ kode_afd: "afd1" }, "AFD1").weight).toBe(AFDELING_SELECTED_WEIGHT);
  });

  it("jarak klik ke garis batas", () => {
    const sq = [[{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }]];
    expect(ringsDistance({ x: 5, y: 1 }, sq)).toBeCloseTo(1);
    expect(ringsDistance({ x: 5, y: 5 }, sq)).toBeCloseTo(5);
  });
});
