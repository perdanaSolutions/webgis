import { describe, expect, it } from "vitest";
import { areaBubblesVisible, bubbleSize, groupBlocksByArea } from "../utils/areaBubbles";
import { wheelZoomDelta } from "../utils/smoothWheelZoom";

const sq = (x: number, y: number, props: Record<string, any>) => ({
  geometry: { type: "Polygon", coordinates: [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y]]] }, properties: props,
});

describe("groupBlocksByArea", () => {
  it("menghitung blok per PT+area, posisi tengah bbox area", () => {
    const out = groupBlocksByArea([
      sq(0, 0, { kode_pt: "P1", nama_pt: "PT Satu", kode_area: "A1" }),
      sq(4, 0, { kode_pt: "P1", nama_pt: "PT Satu", kode_area: "A1" }),
      sq(10, 0, { kode_pt: "P1", nama_pt: "PT Satu", kode_area: "A2" }),
      sq(20, 0, { kode_pt: "P2", kode_area: "A1" }),
    ]);
    expect(out.map((b) => [b.key, b.count])).toEqual([["P1|A1", 2], ["P1|A2", 1], ["P2|A1", 1]]);
    expect(out[0]!.lng).toBeCloseTo(2.5, 10);
    expect(out[2]!.namaPt).toBe("P2");
  });
});

describe("visibility & size", () => {
  it("hilang pada skala 5 km atau lebih dekat", () => {
    expect(areaBubblesVisible(5000)).toBe(false);
    expect(areaBubblesVisible(4000)).toBe(false);
    expect(areaBubblesVisible(5002.5)).toBe(false); // "5 km" dari tombol
    expect(areaBubblesVisible(5500)).toBe(true);
    expect(areaBubblesVisible(20000)).toBe(true);
  });
  it("ukuran naik pelan", () => {
    expect(bubbleSize(1)).toBe(34);
    expect(bubbleSize(100)).toBe(54);
    expect(bubbleSize(100000)).toBe(64);
  });
});

describe("wheelZoomDelta", () => {
  it("mouse notch ±0,5 level, pinch lebih cepat, dibatasi 1 level", () => {
    expect(wheelZoomDelta({ deltaY: 100, deltaMode: 0, ctrlKey: false })).toBeCloseTo(-0.5);
    expect(wheelZoomDelta({ deltaY: -3, deltaMode: 1, ctrlKey: false })).toBeCloseTo(0.24);
    expect(wheelZoomDelta({ deltaY: -10, deltaMode: 0, ctrlKey: true })).toBeCloseTo(0.1);
    expect(wheelZoomDelta({ deltaY: -5000, deltaMode: 0, ctrlKey: false })).toBe(1);
  });
});
