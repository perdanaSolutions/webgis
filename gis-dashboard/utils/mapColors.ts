/**
 * Sumber tunggal warna halaman Map (`/map` → BlokProfileView + panel/layer terkait).
 *
 * Cara pakai:
 * - JS/TS (Leaflet, legenda, chart): `import { MAP_UI, MAP_BUDGET_GAP, … } from "~/utils/mapColors"`
 * - Template Vue: bind style (`:style="{ color: MAP_UI.text.ink }"`) atau class Tailwind
 *   dengan hex yang sama (salin dari sini, jangan invent hex baru).
 * - CSS halaman map: inject `mapColorCssVars()` ke root shell (`.bp-map-shell`) lalu pakai `var(--map-*)`.
 *
 * Jangan menambah hex baru di komponen map tanpa memperbarui file ini dulu.
 */

// ---------------------------------------------------------------------------
// UI shell — brand, permukaan, teks, border, status
// ---------------------------------------------------------------------------

export const MAP_UI = {
  brand: {
    /** Primary hijau Teladan / tombol aksi / accent form */
    primary: "#638840",
    primaryHover: "#557536",
    primaryHoverStrong: "#527036",
    /** Secondary oranye (highlight rotasi, bubble area) */
    secondary: "#d87633",
    secondaryHover: "#c9661c",
    secondarySoft: "#e07b2a",
  },
  surface: {
    /** Latar penuh halaman map + loading “Membuka peta…” */
    page: "#f4f6f1",
    /** Hover toolbar / chip */
    hover: "#eef3e7",
    /** Kartu ringkas di panel samping */
    muted: "#eef2e8",
    /** Kartu glass (bp-card) */
    card: "rgba(255, 253, 249, 0.774)",
    cardSolid: "#fffdf9",
    white: "#ffffff",
  },
  text: {
    ink: "#1f2a18",
    soft: "#55604c",
    muted: "#6e7866",
    onPrimary: "#ffffff",
    /** Popup detail (netral slate) */
    popup: "#1f2937",
    popupTitle: "#111827",
    popupMuted: "#6b7280",
  },
  border: {
    default: "#d5dcc8",
    soft: "#e4eadc",
    list: "#e4e8de",
    block: "#1e293b",
  },
  status: {
    successBg: "#e8f5df",
    successText: "#3f6b24",
    errorBg: "#fdecea",
    errorText: "#b42318",
    warningText: "#b45309",
    dirtyDot: "#f59e0b",
  },
  overlay: {
    /** Scrim panel / dialog */
    scrim: "rgba(31, 42, 24, 0.45)",
    scrimLight: "rgba(31, 42, 24, 0.20)",
  },
} as const;

// ---------------------------------------------------------------------------
// Yield / budget gap — pewarnaan poligon blok + legenda
// ---------------------------------------------------------------------------

export const MAP_BUDGET_GAP = {
  OPTIMUM: "#3aa0ff",
  "GAP I": "#3ee07a",
  "GAP II": "#ffe34d",
  "GAP III": "#ff4d4d",
} as const;

export type MapBudgetGapKey = keyof typeof MAP_BUDGET_GAP;

// ---------------------------------------------------------------------------
// Kelas kemiringan — satu ramp hijau (terang → gelap)
// ---------------------------------------------------------------------------

export const MAP_SLOPE_RAMP = {
  "0-3": "#d7e4c8",
  "3-8": "#a3c07e",
  "8-15": "#638840",
  "15-25": "#3d5528",
} as const;

// ---------------------------------------------------------------------------
// Layer overlay (katalog spatial) — default + kategori
// ---------------------------------------------------------------------------

export const MAP_OVERLAY = {
  afdeling: "#f59e0b",
  sawit: "#fde047",
  tph: "#22c55e",
  slopeDefault: "#fca5a5",
  landuse: {
    Sawit: "#86efac",
    Jalan: "#d6d3d1",
    Terjal: "#fca5a5",
    Rawa: "#93c5fd",
    default: "#c4b5fd",
  },
  jalan: {
    "Main Road": "#b45309",
    "Jalan Poros": "#d97706",
    "Collection Road": "#f59e0b",
    "Jalan Bantu": "#facc15",
    default: "#a16207",
  },
  jembatan: "#0284c7",
  drainase: "#0891b2",
  /** Layer katalog yang belum punya gaya khusus */
  generic: [
    "#06b6d4",
    "#ec4899",
    "#14b8a6",
    "#6366f1",
    "#84cc16",
    "#f43f5e",
  ],
} as const;

// ---------------------------------------------------------------------------
// Fitur peta Leaflet (batas blok, label, bubble area, popup)
// ---------------------------------------------------------------------------

export const MAP_FEATURE = {
  boundaryStroke: "#d4d4d4",
  selectedStroke: "#ffffff",
  label: "#ffffff",
  labelBelow: "#fbbf24",
  afdelingLabel: "#fde68a",
  areaBubble: {
    bg: "rgba(224, 123, 42, 0.92)",
    hover: "#c9661c",
    panel: "#3f4a3a",
  },
  zoomHint: {
    bg: "rgba(31, 42, 24, 0.92)",
    chip: "rgba(63, 87, 40, 0.92)",
  },
  clusterBadge: {
    border: "#55604c",
    bg: "rgba(255, 253, 249, 0.92)",
    text: "#24301c",
  },
  blocksPreview: "#2e7d32aa",
} as const;

// ---------------------------------------------------------------------------
// Kartu chart di panel blok (produksi TBS, rotasi)
// ---------------------------------------------------------------------------

export const MAP_CHART = {
  bar: {
    latest: "#638840",
    hover: "#d87633",
    idle: "#c5d4b4",
  },
  production: {
    positive: "#3a9a45",
    warning: "#e3b505",
    negative: "#c62828",
    track: "#eef3e7",
    deltaUp: "#2e7d32",
    deltaDown: "#c62828",
  },
} as const;

// ---------------------------------------------------------------------------
// Pratinjau kartu basemap (gradasi di panel layer)
// ---------------------------------------------------------------------------

export const MAP_BASEMAP_PREVIEW = {
  osm: "linear-gradient(135deg,#f2efe9 0%,#aad3df 100%)",
  satellite: "linear-gradient(135deg,#2f4a2a 0%,#5b7443 50%,#1d3b52 100%)",
  hybrid: "linear-gradient(135deg,#2f4a2a 0%,#5b7443 60%,#f8fafc 100%)",
  topo: "linear-gradient(135deg,#e8e4c9 0%,#c9d8a8 50%,#a7c7d8 100%)",
  "tpa-sga": "linear-gradient(135deg,#1f3b24 0%,#6d8a45 55%,#c4b48a 100%)",
  light: "linear-gradient(135deg,#fafafa 0%,#e5e7eb 100%)",
  dark: "linear-gradient(135deg,#1f2937 0%,#111827 100%)",
} as const;

// ---------------------------------------------------------------------------
// CSS custom properties — tempel ke root shell map
// ---------------------------------------------------------------------------

/** Object untuk `:style="mapColorCssVars()"` di `.bp-map-shell` / loading map. */
export function mapColorCssVars(): Record<string, string> {
  return {
    "--map-primary": MAP_UI.brand.primary,
    "--map-primary-hover": MAP_UI.brand.primaryHover,
    "--map-secondary": MAP_UI.brand.secondary,
    "--map-page": MAP_UI.surface.page,
    "--map-hover": MAP_UI.surface.hover,
    "--map-ink": MAP_UI.text.ink,
    "--map-muted": MAP_UI.text.muted,
    "--map-soft": MAP_UI.text.soft,
    "--map-border": MAP_UI.border.default,
    "--map-success-bg": MAP_UI.status.successBg,
    "--map-success-text": MAP_UI.status.successText,
    "--map-error-bg": MAP_UI.status.errorBg,
    "--map-error-text": MAP_UI.status.errorText,
  };
}
