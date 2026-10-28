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
/** Label kode afdeling tampil saat garis skala 2–10 km (di bawah 2 km giliran label blok). */
export const AFDELING_LABEL_MIN_SCALE_M = 2000;
export const AFDELING_LABEL_MAX_SCALE_M = 10000;
/** Jarak klik ke garis batas afdeling (px) supaya popup afdeling yang terbuka, bukan popup blok. */
export const AFDELING_HIT_PX = 6;

export function afdelingLabelsVisible(scaleMeters: number, suppressed = false) {
  // `suppressed`: mis. saat gelembung jumlah blok per area tampil (> 5 km), label afdeling disembunyikan supaya tidak bertabrakan.
  return !suppressed && scaleMeters >= AFDELING_LABEL_MIN_SCALE_M && scaleMeters <= AFDELING_LABEL_MAX_SCALE_M * 1.01;
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

function num(value: unknown, digits: number) {
  const n = Number(value);
  if (value === null || value === undefined || value === "" || !Number.isFinite(n)) return "-";
  return n.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });
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
