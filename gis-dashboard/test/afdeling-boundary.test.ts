import { describe, expect, it } from "vitest";
import {
  AFDELING_SELECTED_WEIGHT, AFDELING_WEIGHT, afdelingDeclutter, afdelingLabelText, afdelingLabelsVisible, declutterLabels, largestPart, polylabel, afdelingPopupRows, afdelingStyle, ringsDistance,
} from "../utils/afdelingBoundary";

describe("batas afdeling", () => {
  it("label hanya di skala 2–10 km dan bisa disembunyikan", () => {
    // label selalu tampil selama layer aktif (semua skala), hilang saat layer mati
    expect(afdelingLabelsVisible(true)).toBe(true);
    expect(afdelingLabelsVisible(false)).toBe(false);
    expect(afdelingDeclutter(1000)).toBe(false);
    expect(afdelingDeclutter(5000)).toBe(false);
    expect(afdelingDeclutter(20000)).toBe(true);
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

describe("label batas afdeling", () => {
  it("teks = kode afdeling + short name estate", () => {
    expect(afdelingLabelText({ kode_afd: "afdi02", kode_est: "E005" }, { E005: "SBE" })).toEqual({ afd: "AFDI02", est: "SBE" });
    expect(afdelingLabelText({ kode_afd: "AFDP03", estate_short_name: "KME" })).toEqual({ afd: "AFDP03", est: "KME" });
    expect(afdelingLabelText({})).toBeNull();
  });

  it("titik label di dalam poligon berbentuk L (bukan pusat bbox yang di luar)", () => {
    const L: [number, number][][] = [[[0, 0], [10, 0], [10, 2], [2, 2], [2, 10], [0, 10], [0, 0]]];
    const [x, y] = polylabel(L);
    const insideBottom = y >= 0 && y <= 2 && x >= 0 && x <= 10;
    const insideLeft = x >= 0 && x <= 2 && y >= 0 && y <= 10;
    expect(insideBottom || insideLeft).toBe(true);
    // pusat bbox (5,5) ada di luar L
    expect(Math.hypot(x - 5, y - 5)).toBeGreaterThan(1);
  });

  it("multi-bagian: pakai bagian terluas", () => {
    const small: [number, number][][] = [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]];
    const big: [number, number][][] = [[[10, 10], [20, 10], [20, 20], [10, 20], [10, 10]]];
    expect(largestPart([small, big])).toBe(big);
    const [x, y] = polylabel(big);
    expect(x).toBeCloseTo(15, 0);
    expect(y).toBeCloseTo(15, 0);
  });

  it("declutter: label yang menimpa label lebih besar disembunyikan, yang terpisah tetap tampil", () => {
    const shown = declutterLabels([
      { id: "besar", x: 100, y: 100, w: 60, h: 30, priority: 10 },
      { id: "kecil-tabrak", x: 110, y: 105, w: 60, h: 30, priority: 1 },
      { id: "jauh", x: 300, y: 300, w: 60, h: 30, priority: 1 },
    ]);
    expect([...shown].sort()).toEqual(["besar", "jauh"]);
  });
});
