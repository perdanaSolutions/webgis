/**
 * Bubble jumlah blok per area (filter Kebun "Semua" di semua level).
 * Dikelompokkan per PT + area dari properti GeoJSON (`kode_pt`, `nama_pt`, `kode_area`).
 * Posisi bubble = tengah bbox (barat–timur, selatan–utara) semua blok area tersebut.
 */
import { bboxCenter, featuresBBox } from "./mapView";

export type AreaBubble = {
  key: string;
  kodePt: string;
  namaPt: string;
  kodeArea: string;
  count: number;
  lat: number;
  lng: number;
};

/**
 * Bubble tampil selama garis skala > 5 km per 100 px; hilang saat 5 km atau lebih dekat.
 * Toleransi 1%: skala hasil tombol "5 km" terukur sedikit di atas 5.000 m (5.002,5 m).
 */
export const AREA_BUBBLE_MIN_SCALE_M = 5000;
export function areaBubblesVisible(scaleMeters: number) {
  return scaleMeters > AREA_BUBBLE_MIN_SCALE_M * 1.01;
}

/** Diameter bubble (px): naik pelan mengikuti jumlah blok (log), 34–64 px. */
export function bubbleSize(count: number) {
  return Math.round(Math.min(64, 34 + Math.log10(Math.max(1, count)) * 10));
}

export function groupBlocksByArea(features: Array<{ geometry?: any; properties?: Record<string, any> | null }>): AreaBubble[] {
  const groups = new Map<string, { kodePt: string; namaPt: string; kodeArea: string; items: typeof features }>();
  for (const f of features) {
    const p = f?.properties ?? {};
    const kodeArea = String(p.kode_area ?? "").trim();
    const kodePt = String(p.kode_pt ?? "").trim();
    const key = `${kodePt}|${kodeArea}`;
    let g = groups.get(key);
    if (!g) {
      g = { kodePt, namaPt: String(p.nama_pt ?? "").trim() || kodePt, kodeArea, items: [] };
      groups.set(key, g);
    }
    g.items.push(f);
  }
  const out: AreaBubble[] = [];
  for (const [key, g] of groups) {
    const box = featuresBBox(g.items);
    if (!box) continue;
    const c = bboxCenter(box);
    out.push({ key, kodePt: g.kodePt, namaPt: g.namaPt, kodeArea: g.kodeArea, count: g.items.length, lat: c.lat, lng: c.lng });
  }
  return out.sort((a, b) => a.key.localeCompare(b.key));
}
