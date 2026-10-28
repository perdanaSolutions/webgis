import { describe, expect, it } from "vitest";
import { bboxCenter, featuresBBox, roundScaleMeters, scaleStep, zoomForScale } from "../utils/mapView";

const poly = (coords: number[][]) => ({ geometry: { type: "Polygon", coordinates: [coords] } });

describe("featuresBBox / bboxCenter", () => {
  it("menghitung barat-timur dan selatan-utara dari semua blok", () => {
    const box = featuresBBox([
      poly([[110, 1], [110.2, 1], [110.2, 1.1], [110, 1]]),
      { geometry: { type: "MultiPolygon", coordinates: [[[[109.5, 0.5], [109.6, 0.5], [109.6, 0.6], [109.5, 0.5]]]] } },
      null,
    ]);
    expect(box).toEqual({ west: 109.5, south: 0.5, east: 110.2, north: 1.1 });
    const c = bboxCenter(box!);
    expect(c.lng).toBeCloseTo(109.85, 10);
    expect(c.lat).toBeGreaterThan(0.79);
    expect(c.lat).toBeLessThan(0.81);
  });
  it("bukan rata-rata centroid: blok kecil jauh tetap menggeser tengah", () => {
    const box = featuresBBox([poly([[0, 0], [1, 0], [1, 1], [0, 0]]), poly([[9, 0], [9.01, 0], [9.01, 0.01], [9, 0]])]);
    expect(bboxCenter(box!).lng).toBeCloseTo(4.505, 10);
  });
  it("null bila kosong", () => {
    expect(featuresBBox([])).toBeNull();
  });
});

describe("scaleStep", () => {
  it("zoom out naik 500 m per klik", () => {
    expect(scaleStep(100, "out")).toBe(500);
    expect(scaleStep(500, "out")).toBe(1000);
    expect(scaleStep(1000, "out")).toBe(1500);
    expect(scaleStep(1234, "out")).toBe(1500);
  });
  it("zoom in turun 500 m per klik, minimum 100 m", () => {
    expect(scaleStep(1500, "in")).toBe(1000);
    expect(scaleStep(1234, "in")).toBe(1000);
    expect(scaleStep(1000, "in")).toBe(500);
    expect(scaleStep(500, "in")).toBe(100);
    expect(scaleStep(100, "in")).toBe(100);
  });
  it("zoom in dari skala bukan kelipatan selalu turun ke kelipatan 500 m di bawahnya", () => {
    const seq = (start: number) => { const out = [start]; for (let i = 0; i < 6; i++) out.push(scaleStep(out.at(-1)!, "in")); return out; };
    expect(seq(5000)).toEqual([5000, 4500, 4000, 3500, 3000, 2500, 2000]);
    expect(seq(2300)).toEqual([2300, 2000, 1500, 1000, 500, 100, 100]);
    expect(seq(700)).toEqual([700, 500, 100, 100, 100, 100, 100]);
    expect(seq(476)).toEqual([476, 100, 100, 100, 100, 100, 100]);
    // nilai terukur sedikit di atas target (faktor 1.0005) tidak boleh diam di tempat
    expect(scaleStep(1000.5, "in")).toBe(500);
    expect(scaleStep(1500.75, "in")).toBe(1000);
    // regresi t114u: 2,5 km hasil tombol terukur 2501,25 m -> harus ke 2 km, bukan diam di 2,5 km
    expect(scaleStep(2501.25, "in")).toBe(2000);
    expect(scaleStep(7503.75, "in")).toBe(7000);
    expect(scaleStep(7503.75, "out")).toBe(8000);
  });
  it("zoom in lalu zoom out simetris", () => {
    for (const v of [500, 1000, 1500, 2000, 4500]) expect(scaleStep(scaleStep(v, "in"), "out")).toBe(v === 500 ? 500 : v);
  });
  it("zoomForScale: skala 2x lebih kecil = zoom +1", () => {
    expect(zoomForScale(10, 1000, 500)).toBeCloseTo(11, 10);
  });
  it("label skala kelipatan 500 m", () => {
    expect(roundScaleMeters(1499.9, (n) => n)).toBe(1000);
    expect(roundScaleMeters(1500.2, (n) => n)).toBe(1500);
    expect(roundScaleMeters(100, () => 100)).toBe(100);
  });
});
