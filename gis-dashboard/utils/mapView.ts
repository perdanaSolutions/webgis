/**
 * Perhitungan tampilan peta Blok Profile (tanpa Leaflet, agar bisa diuji unit).
 *
 * - `featuresBBox`: batas barat–timur dan selatan–utara dari SEMUA koordinat blok yang tampil.
 * - `bboxCenter`: titik tengah sebenarnya dari batas tersebut (lintang dihitung di proyeksi Web Mercator,
 *   sama dengan proyeksi peta, sehingga tengah di layar benar-benar tengah).
 * - `scaleStep`: tangga skala tombol zoom (100 m, lalu kelipatan 500 m).
 */

export type BBox = { west: number; south: number; east: number; north: number };

function visit(coords: unknown, box: BBox) {
  if (!Array.isArray(coords)) return;
  if (typeof coords[0] === "number" && typeof coords[1] === "number") {
    const lng = coords[0] as number;
    const lat = coords[1] as number;
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
    if (lng < box.west) box.west = lng;
    if (lng > box.east) box.east = lng;
    if (lat < box.south) box.south = lat;
    if (lat > box.north) box.north = lat;
    return;
  }
  for (const item of coords) visit(item, box);
}

function visitGeometry(geometry: any, box: BBox) {
  if (!geometry) return;
  if (geometry.type === "GeometryCollection") {
    for (const g of geometry.geometries ?? []) visitGeometry(g, box);
    return;
  }
  visit(geometry.coordinates, box);
}

/** Bounding box gabungan semua fitur. `null` bila tidak ada koordinat valid. */
export function featuresBBox(features: Array<{ geometry?: any } | null | undefined>): BBox | null {
  const box: BBox = { west: Infinity, south: Infinity, east: -Infinity, north: -Infinity };
  for (const f of features) visitGeometry(f?.geometry, box);
  if (!Number.isFinite(box.west) || !Number.isFinite(box.south)) return null;
  return box;
}

const RAD = Math.PI / 180;
function mercY(lat: number) {
  return Math.log(Math.tan(Math.PI / 4 + (lat * RAD) / 2));
}
function invMercY(y: number) {
  return (2 * Math.atan(Math.exp(y)) - Math.PI / 2) / RAD;
}

/** Titik tengah bbox: bujur = (barat+timur)/2, lintang = tengah di Web Mercator. */
export function bboxCenter(box: BBox): { lat: number; lng: number } {
  return {
    lng: (box.west + box.east) / 2,
    lat: invMercY((mercY(box.south) + mercY(box.north)) / 2),
  };
}

/** Skala minimum (blok spesifik) dan kelipatan tombol zoom, dalam meter per 100 px garis skala. */
export const BLOCK_SCALE_M = 100;
export const ZOOM_STEP_M = 500;
export const MAX_SCALE_M = 100000;

/**
 * Skala berikutnya untuk tombol zoom. Skala = jarak yang diwakili garis skala (100 px).
 * Tangga: 100 m, 500 m, 1.000 m, 1.500 m, … (kelipatan 500 m). Tidak melompati anak tangga.
 */
export function scaleStep(currentMeters: number, direction: "in" | "out"): number {
  const cur = Math.max(BLOCK_SCALE_M, Math.min(MAX_SCALE_M, currentMeters));
  // Toleransi relatif: skala hasil tombol sengaja dibuat 0,05% di atas target (agar label tidak
  // terbulatkan ke bawah) dan ada selisih ukur; toleransi tetap 1 m gagal mulai ~2 km (2500 m -> 2501,25 m).
  const eps = Math.max(1, cur * 0.002);
  if (direction === "in") {
    if (cur <= ZOOM_STEP_M + eps) return BLOCK_SCALE_M;
    const next = Math.ceil((cur - eps) / ZOOM_STEP_M) * ZOOM_STEP_M - ZOOM_STEP_M;
    return Math.max(ZOOM_STEP_M, next);
  }
  if (cur < ZOOM_STEP_M - eps) return ZOOM_STEP_M;
  const next = Math.floor((cur + eps) / ZOOM_STEP_M) * ZOOM_STEP_M + ZOOM_STEP_M;
  return Math.min(MAX_SCALE_M, next);
}

/** Zoom baru agar garis skala bernilai `targetMeters`. Jarak per piksel ∝ 2^-zoom. */
export function zoomForScale(currentZoom: number, currentMeters: number, targetMeters: number) {
  if (!(currentMeters > 0) || !(targetMeters > 0)) return currentZoom;
  return currentZoom + Math.log2(currentMeters / targetMeters);
}

/** Pembulatan label garis skala: < 500 m pakai angka bulat Leaflet, >= 500 m kelipatan 500 m. */
export function roundScaleMeters(meters: number, leafletRound: (n: number) => number) {
  if (meters >= ZOOM_STEP_M) return Math.floor(meters / ZOOM_STEP_M) * ZOOM_STEP_M;
  return leafletRound(meters);
}
