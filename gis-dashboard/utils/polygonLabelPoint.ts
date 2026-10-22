type LngLat = [number, number];
type Ring = LngLat[];

/** Titik label di dalam bagian poligon terluas, sedekat mungkin dengan pusatnya. */
export function polygonLabelLngLat(geometry: GeoJSON.Geometry | null | undefined): LngLat | null {
  const polygons = polygonRings(geometry);
  let best: Ring[] | null = null;
  let bestArea = 0;
  for (const polygon of polygons) {
    const area = Math.abs(ringArea(polygon[0] ?? []));
    if (area > bestArea) {
      best = polygon;
      bestArea = area;
    }
  }
  const outer = best?.[0];
  if (!outer || outer.length < 3) return null;
  const holes = (best ?? []).slice(1).filter((ring) => ring.length >= 3);
  const centroid = ringCentroid(outer);
  if (centroid && insidePolygon(centroid, outer, holes)) return centroid;
  return interiorPoint(outer, holes) ?? centroid ?? outer[0] ?? null;
}

function polygonRings(geometry: GeoJSON.Geometry | null | undefined): Ring[][] {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return [asRings(geometry.coordinates)];
  if (geometry.type === "MultiPolygon") return geometry.coordinates.map(asRings);
  return [];
}

function asRings(coordinates: number[][][]): Ring[] {
  return coordinates.map((ring) =>
    ring
      .map((pair) => [Number(pair[0]), Number(pair[1])] as LngLat)
      .filter((pair) => Number.isFinite(pair[0]) && Number.isFinite(pair[1])),
  );
}

function ringArea(ring: Ring): number {
  let sum = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x1, y1] = ring[j]!;
    const [x2, y2] = ring[i]!;
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}

function ringCentroid(ring: Ring): LngLat | null {
  let area = 0;
  let x = 0;
  let y = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x1, y1] = ring[j]!;
    const [x2, y2] = ring[i]!;
    const cross = x1 * y2 - x2 * y1;
    area += cross;
    x += (x1 + x2) * cross;
    y += (y1 + y2) * cross;
  }
  if (Math.abs(area) < 1e-12) return null;
  return [x / (3 * area), y / (3 * area)];
}

function insidePolygon(point: LngLat, outer: Ring, holes: Ring[]): boolean {
  return pointInRing(point, outer) && holes.every((hole) => !pointInRing(point, hole));
}

function pointInRing(point: LngLat, ring: Ring): boolean {
  const [x, y] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]!;
    const [xj, yj] = ring[j]!;
    const crosses = yi > y !== yj > y;
    if (!crosses) continue;
    const xAtY = ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (x < xAtY) inside = !inside;
  }
  return inside;
}

/** Irisan mendatar terpanjang yang masih di dalam poligon, dipilih yang paling dekat ke pusat kotak. */
function interiorPoint(outer: Ring, holes: Ring[]): LngLat | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of outer) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  if (!Number.isFinite(minX) || maxY === minY) return null;
  const target: LngLat = [(minX + maxX) / 2, (minY + maxY) / 2];
  const samples = 32;
  let longest = 0;
  const candidates: Array<{ point: LngLat; length: number }> = [];
  for (let step = 1; step < samples; step += 1) {
    const y = minY + ((maxY - minY) * step) / samples;
    for (const [x0, x1] of horizontalSpans(outer, holes, y)) {
      const length = x1 - x0;
      if (length <= 0) continue;
      if (length > longest) longest = length;
      candidates.push({ point: [(x0 + x1) / 2, y], length });
    }
  }
  const nearLongest = candidates.filter((item) => item.length >= longest * 0.98);
  let best: LngLat | null = null;
  let bestDist = Infinity;
  for (const item of nearLongest) {
    const dx = item.point[0] - target[0];
    const dy = item.point[1] - target[1];
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) {
      best = item.point;
      bestDist = dist;
    }
  }
  return best;
}

function horizontalSpans(outer: Ring, holes: Ring[], y: number): Array<[number, number]> {
  let spans = pairIntersections(intersections(outer, y));
  for (const hole of holes) {
    const cuts = pairIntersections(intersections(hole, y));
    spans = spans.flatMap((span) => subtractSpan(span, cuts));
  }
  return spans;
}

function intersections(ring: Ring, y: number): number[] {
  const xs: number[] = [];
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x1, y1] = ring[j]!;
    const [x2, y2] = ring[i]!;
    if ((y1 <= y && y2 > y) || (y2 <= y && y1 > y)) {
      xs.push(x1 + ((y - y1) * (x2 - x1)) / (y2 - y1));
    }
  }
  xs.sort((a, b) => a - b);
  return xs;
}

function pairIntersections(xs: number[]): Array<[number, number]> {
  const spans: Array<[number, number]> = [];
  for (let i = 0; i + 1 < xs.length; i += 2) spans.push([xs[i]!, xs[i + 1]!]);
  return spans;
}

function subtractSpan(span: [number, number], cuts: Array<[number, number]>): Array<[number, number]> {
  let parts: Array<[number, number]> = [span];
  for (const [cutStart, cutEnd] of cuts) {
    const next: Array<[number, number]> = [];
    for (const [start, end] of parts) {
      if (cutEnd <= start || cutStart >= end) {
        next.push([start, end]);
        continue;
      }
      if (cutStart > start) next.push([start, Math.min(cutStart, end)]);
      if (cutEnd < end) next.push([Math.max(cutEnd, start), end]);
    }
    parts = next.filter(([start, end]) => end - start > 0);
  }
  return parts;
}
