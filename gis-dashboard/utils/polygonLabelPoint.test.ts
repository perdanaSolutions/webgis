import { describe, expect, it } from "vitest";

import { polygonLabelLngLat } from "./polygonLabelPoint";

function pointInRing(point: [number, number], ring: number[][]): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i]![0]!;
    const yi = ring[i]![1]!;
    const xj = ring[j]![0]!;
    const yj = ring[j]![1]!;
    const crosses = yi > y !== yj > y;
    if (!crosses) continue;
    const xAtY = ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (x < xAtY) inside = !inside;
  }
  return inside;
}

describe("polygonLabelLngLat", () => {
  it("meletakkan label di pusat persegi", () => {
    const point = polygonLabelLngLat({
      type: "Polygon",
      coordinates: [[[0, 0], [4, 0], [4, 2], [0, 2], [0, 0]]],
    });
    expect(point?.[0]).toBeCloseTo(2, 5);
    expect(point?.[1]).toBeCloseTo(1, 5);
  });

  it("memilih bagian terluas pada multipolygon", () => {
    const point = polygonLabelLngLat({
      type: "MultiPolygon",
      coordinates: [
        [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        [[[10, 0], [14, 0], [14, 4], [10, 4], [10, 0]]],
      ],
    });
    expect(point?.[0]).toBeGreaterThan(10);
    expect(point?.[0]).toBeLessThan(14);
    expect(point?.[1]).toBeGreaterThan(0);
    expect(point?.[1]).toBeLessThan(4);
    expect(point?.[0]).toBeCloseTo(12, 5);
    expect(point?.[1]).toBeCloseTo(2, 5);
  });

  it("tetap di dalam poligon cekung", () => {
    const ring = [
      [0, 0], [4, 0], [4, 1], [1, 1], [1, 2], [4, 2], [4, 3], [0, 3], [0, 0],
    ];
    const point = polygonLabelLngLat({ type: "Polygon", coordinates: [ring] });
    expect(point).not.toBeNull();
    expect(pointInRing(point!, ring)).toBe(true);
  });
});
