import { formatDecimalId } from "./numberFormat";
/**
 * Layer "Batas Afdeling" (GET /spatial/afdeling/geojson): gaya garis, popup, dan aturan label.
 * Murni (tanpa Leaflet) supaya bisa dites di vitest.
 */

export const AFDELING_LAYER_CODE = "afdeling";
export const AFDELING_LAYER_NAME = "Batas Afdeling";
export const AFDELING_ENDPOINT = "/afdeling/geojson";
/** Kuning-oranye (amber-500), kontras dengan garis blok putih/abu. */
export const AFDELING_COLOR = "#f59e0b";
export const AFDELING_WEIGHT = 2.75;
export const AFDELING_SELECTED_WEIGHT = 5;
/**
 * Label afdeling selalu tampil selama layer aktif (semua skala). Di atas skala ini label yang bertabrakan
 * dirapikan (declutter: yang lebih kecil disembunyikan); di skala kerja (<= 5 km) semua label di layar tampil.
 */
export const AFDELING_DECLUTTER_MIN_SCALE_M = 5000;
/** Jarak minimum antar kotak label saat declutter (px). */
export const AFDELING_LABEL_PAD_PX = 6;
/** Jarak klik ke garis batas afdeling (px) supaya popup afdeling yang terbuka, bukan popup blok. */
export const AFDELING_HIT_PX = 6;

/** Label afdeling tampil di semua skala selama layer aktif (permintaan Bayu); `layerOn` = layer Batas Afdeling aktif. */
export function afdelingLabelsVisible(layerOn: boolean) {
  return layerOn;
}

export function afdelingDeclutter(scaleMeters: number) {
  return scaleMeters > AFDELING_DECLUTTER_MIN_SCALE_M;
}

/** Teks label: kode afdeling (mis. AFDI02) + short name estate (kode afdeling berulang antar estate). */
export function afdelingLabelText(properties: Record<string, any> | null | undefined, estateShortNames: Record<string, string> = {}) {
  const afd = String(properties?.kode_afd ?? "").trim().toUpperCase();
  if (!afd) return null;
  const est = String(properties?.estate_short_name || estateShortNames[String(properties?.kode_est ?? "")] || properties?.kode_est || "").trim();
  return { afd, est };
}

type XY = [number, number];

function ringArea(ring: XY[]) {
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) a += (ring[j]![0] - ring[i]![0]) * (ring[j]![1] + ring[i]![1]);
  return a / 2;
}

/** Bagian terbesar (luas cincin luar dikurangi lubang) dari multi-poligon [poly][ring][xy]. */
export function largestPart(polys: XY[][][]): XY[][] | null {
  let best: XY[][] | null = null;
  let bestArea = -1;
  for (const poly of polys) {
    if (!poly[0]?.length) continue;
    const area = Math.abs(ringArea(poly[0])) - poly.slice(1).reduce((s, r) => s + Math.abs(ringArea(r)), 0);
    if (area > bestArea) { bestArea = area; best = poly; }
  }
  return best;
}

function pointToPolygonDist(x: number, y: number, poly: XY[][]) {
  let inside = false;
  let min = Infinity;
  for (const ring of poly) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const a = ring[i]!; const b = ring[j]!;
      if ((a[1] > y) !== (b[1] > y) && x < ((b[0] - a[0]) * (y - a[1])) / (b[1] - a[1]) + a[0]) inside = !inside;
      const dx = b[0] - a[0]; const dy = b[1] - a[1];
      let t = dx || dy ? ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy) : 0;
      t = Math.max(0, Math.min(1, t));
      const ex = a[0] + t * dx - x; const ey = a[1] + t * dy - y;
      min = Math.min(min, ex * ex + ey * ey);
    }
  }
  return (inside ? 1 : -1) * Math.sqrt(min);
}

/**
 * Pole of inaccessibility (algoritma polylabel): titik di dalam poligon yang paling jauh dari tepi,
 * jadi label tidak jatuh di luar afdeling berbentuk L/U. Koordinat harus kira-kira isotropik (mis. lng·cos(lat), lat).
 */
export function polylabel(poly: XY[][], precision?: number): XY {
  const outer = poly[0] ?? [];
  let minX = Infinity; let minY = Infinity; let maxX = -Infinity; let maxY = -Infinity;
  for (const [x, y] of outer) { minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y); }
  const w = maxX - minX; const h = maxY - minY;
  const size = Math.min(w, h);
  if (!outer.length) return [0, 0];
  if (size === 0) return [minX, minY];
  const eps = precision ?? Math.max(w, h) / 1000;
  type Cell = { x: number; y: number; h: number; d: number; max: number };
  const cell = (x: number, y: number, hh: number): Cell => {
    const d = pointToPolygonDist(x, y, poly);
    return { x, y, h: hh, d, max: d + hh * Math.SQRT2 };
  };
  const queue: Cell[] = [];
  const half = size / 2;
  for (let x = minX; x < maxX; x += size) for (let y = minY; y < maxY; y += size) queue.push(cell(x + half, y + half, half));
  // titik awal: centroid area & pusat bbox
  let A = 0; let cx = 0; let cy = 0;
  for (let i = 0, j = outer.length - 1; i < outer.length; j = i++) {
    const a = outer[i]!; const b = outer[j]!; const f = a[0] * b[1] - b[0] * a[1];
    cx += (a[0] + b[0]) * f; cy += (a[1] + b[1]) * f; A += f * 3;
  }
  let best = A ? cell(cx / A, cy / A, 0) : cell(minX + w / 2, minY + h / 2, 0);
  const box = cell(minX + w / 2, minY + h / 2, 0);
  if (box.d > best.d) best = box;
  let guard = 0;
  while (queue.length && guard++ < 20000) {
    let k = 0;
    for (let i = 1; i < queue.length; i++) if (queue[i]!.max > queue[k]!.max) k = i;
    const c = queue.splice(k, 1)[0]!;
    if (c.d > best.d) best = c;
    if (c.max - best.d <= eps) continue;
    const hh = c.h / 2;
    queue.push(cell(c.x - hh, c.y - hh, hh), cell(c.x + hh, c.y - hh, hh), cell(c.x - hh, c.y + hh, hh), cell(c.x + hh, c.y + hh, hh));
  }
  return [best.x, best.y];
}

export type LabelBox = { id: string; x: number; y: number; w: number; h: number; priority: number };

/** Declutter rakus: urut prioritas (luas) turun, label yang menimpa label lebih besar disembunyikan. Return id tampil. */
export function declutterLabels(boxes: LabelBox[], pad = AFDELING_LABEL_PAD_PX): Set<string> {
  const placed: LabelBox[] = [];
  const shown = new Set<string>();
  for (const b of [...boxes].sort((p, q) => q.priority - p.priority)) {
    const hit = placed.some((p) => Math.abs(p.x - b.x) * 2 < p.w + b.w + pad * 2 && Math.abs(p.y - b.y) * 2 < p.h + b.h + pad * 2);
    if (hit) continue;
    placed.push(b);
    shown.add(b.id);
  }
  return shown;
}

export function isSelectedAfdeling(properties: Record<string, any> | null | undefined, selected: string | undefined) {
  const want = String(selected ?? "").trim().toUpperCase();
  if (!want) return false;
  return [properties?.kode_afd, properties?.division_id].some((v) => String(v ?? "").trim().toUpperCase() === want);
}

export function afdelingStyle(properties: Record<string, any> | null | undefined, selected: string | undefined, opacity = 1) {
  const on = isSelectedAfdeling(properties, selected);
  return {
    color: AFDELING_COLOR,
    weight: on ? AFDELING_SELECTED_WEIGHT : AFDELING_WEIGHT,
    opacity: Math.max(0.35, opacity),
    fill: false,
    lineJoin: "round" as const,
  };
}

function escapeHtml(value: unknown) {
  return String(value ?? "-").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

function num(value: unknown, _digits: number) {
  const n = Number(value);
  if (value === null || value === undefined || value === "" || !Number.isFinite(n)) return "-";
  return formatDecimalId(n);
}

/** Baris popup: Estate (short name, cadangan kode), Afdeling, Jumlah blok, Luas (ha). */
export function afdelingPopupRows(properties: Record<string, any>, estateShortNames: Record<string, string> = {}): Array<[string, string]> {
  const code = String(properties.kode_est ?? "").trim();
  const estate = properties.estate_short_name || estateShortNames[code] || code || "-";
  return [
    ["Estate", String(estate)],
    ["Afdeling", String(properties.kode_afd ?? "-")],
    ["Jumlah blok", num(properties.n_blok, 0)],
    ["Luas (ha)", num(properties.luas_ha, 2)],
  ];
}

export function afdelingPopupHtml(properties: Record<string, any>, estateShortNames: Record<string, string> = {}) {
  const rows = afdelingPopupRows(properties, estateShortNames)
    .map(([k, v]) => `<div class="bp-detail-row"><span>${escapeHtml(k)}</span><span>:</span><span>${escapeHtml(v)}</span></div>`)
    .join("");
  const period = properties.periode_batas ? `<span class="bp-period">Batas ${escapeHtml(properties.periode_batas)}</span>` : "";
  return `<div class="bp-popup"><div class="bp-popup-title"><span class="bp-dot" style="background:${AFDELING_COLOR}"></span>${AFDELING_LAYER_NAME}${period}</div>${rows}</div>`;
}

type Pt = { x: number; y: number };

/** Jarak titik ke segmen (piksel layar). */
export function segmentDistance(p: Pt, a: Pt, b: Pt) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0;
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

/** Jarak terdekat titik ke kumpulan ring (tiap ring = deret titik layar, tertutup). */
export function ringsDistance(p: Pt, rings: Pt[][]) {
  let best = Infinity;
  for (const ring of rings) {
    for (let i = 0; i < ring.length; i += 1) {
      const a = ring[i]!;
      const b = ring[(i + 1) % ring.length]!;
      best = Math.min(best, segmentDistance(p, a, b));
    }
  }
  return best;
}
