/**
 * Konfigurasi peta dasar (basemap) dan gaya layer tambahan untuk halaman peta.
 * Daftar layer tambahan diambil dari katalog backend (GET /v1/spatial/geo/catalog);
 * file ini hanya menentukan tampilannya. Layer yang belum dikenal memakai gaya default.
 */

export type BasemapKey = "osm" | "satellite" | "hybrid" | "topo" | "light" | "dark";

export type BasemapTile = {
  url: string;
  attribution: string;
  maxZoom?: number;
  subdomains?: string;
};

export type BasemapOption = {
  key: BasemapKey;
  label: string;
  preview: string; // warna/gradasi kartu pratinjau
  tiles: BasemapTile[]; // >1 = ditumpuk (mis. citra satelit + label)
};

const ESRI_ATTRIBUTION = "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, GIS User Community";
const OSM_ATTRIBUTION = "&copy; OpenStreetMap contributors";
const CARTO_ATTRIBUTION = `${OSM_ATTRIBUTION} &copy; CARTO`;

export const BASEMAPS: BasemapOption[] = [
  {
    key: "osm",
    label: "OpenStreetMap",
    preview: "linear-gradient(135deg,#f2efe9 0%,#aad3df 100%)",
    tiles: [{ url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: OSM_ATTRIBUTION, maxZoom: 19 }],
  },
  {
    key: "satellite",
    label: "Esri World Imagery",
    preview: "linear-gradient(135deg,#2f4a2a 0%,#5b7443 50%,#1d3b52 100%)",
    tiles: [{
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      attribution: ESRI_ATTRIBUTION,
      maxZoom: 19,
    }],
  },
  {
    key: "hybrid",
    label: "Esri Imagery + Label",
    preview: "linear-gradient(135deg,#2f4a2a 0%,#5b7443 60%,#f8fafc 100%)",
    tiles: [
      {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attribution: ESRI_ATTRIBUTION,
        maxZoom: 19,
      },
      {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
        attribution: "",
        maxZoom: 19,
      },
    ],
  },
  {
    key: "topo",
    label: "OpenTopoMap",
    preview: "linear-gradient(135deg,#e8e4c9 0%,#c9d8a8 50%,#a7c7d8 100%)",
    tiles: [{
      url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
      attribution: `${OSM_ATTRIBUTION}, SRTM | &copy; OpenTopoMap (CC-BY-SA)`,
      maxZoom: 17,
    }],
  },
  {
    key: "light",
    label: "CARTO Positron",
    preview: "linear-gradient(135deg,#fafafa 0%,#e5e7eb 100%)",
    tiles: [{
      url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      attribution: CARTO_ATTRIBUTION,
      maxZoom: 20,
      subdomains: "abcd",
    }],
  },
  {
    key: "dark",
    label: "CARTO Dark Matter",
    preview: "linear-gradient(135deg,#1f2937 0%,#111827 100%)",
    tiles: [{
      url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      attribution: CARTO_ATTRIBUTION,
      maxZoom: 20,
      subdomains: "abcd",
    }],
  },
];

export const DEFAULT_BASEMAP: BasemapKey = "osm";

/**
 * Kelas kemiringan = data berurutan (datar -> curam) -> SATU gradasi warna tanah,
 * terang ke gelap (bukan hue berbeda-beda yang sulit dibedakan pembaca buta warna).
 * Dipakai legenda peta, layer slope, dan donut Analisa Kemiringan.
 */
export const SLOPE_RAMP: Record<string, string> = {
  "0-3": "#e6d3ad",
  "3-8": "#c9a46a",
  "8-15": "#9c6f3a",
  "15-25": "#5a3a1c",
};

/** Warna blok dari properties.produksi_tbs.kategori_budget. */
export const BUDGET_GAP_LAYERS = [
  { key: "OPTIMUM", label: "Optimum", color: "#3aa0ff", hint: "Varians > 0%" },
  { key: "GAP I", label: "Gap I", color: "#3ee07a", hint: "Varians −1% s.d. −20%" },
  { key: "GAP II", label: "Gap II", color: "#ffe34d", hint: "Varians −20% s.d. −40%" },
  { key: "GAP III", label: "Gap III", color: "#ff4d4d", hint: "Varians < −40%" },
] as const;

export type BudgetGapKey = (typeof BUDGET_GAP_LAYERS)[number]["key"];

export const BUDGET_GAP_COLOR: Record<string, string> = Object.fromEntries(
  BUDGET_GAP_LAYERS.map((item) => [item.key, item.color]),
);

function asRecord(value: unknown): Record<string, any> | null {
  if (!value) return null;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown;
      return parsed && typeof parsed === "object" ? parsed as Record<string, any> : null;
    } catch {
      return null;
    }
  }
  return typeof value === "object" ? value as Record<string, any> : null;
}

function pickField(record: Record<string, any> | null, name: string) {
  if (!record) return undefined;
  if (record[name] != null && record[name] !== "") return record[name];
  const key = Object.keys(record).find((item) => item.toLowerCase() === name);
  return key ? record[key] : undefined;
}

/** Nilai properties.produksi_tbs.kategori_budget, termasuk bila tersimpan sebagai JSON string. */
export function readBudgetCategory(properties: Record<string, any> | null | undefined): string {
  const props = properties ?? {};
  const produksi = asRecord(props.produksi_tbs);
  const raw = pickField(produksi, "kategori_budget") ?? pickField(props, "kategori_budget") ?? pickField(asRecord(produksi?.tbs), "kategori_budget");
  const text = String(raw ?? "").trim().toUpperCase().replace(/\s+/g, " ");
  if (text === "OPTIMUM") return "OPTIMUM";
  if (text === "GAP I" || text === "GAP 1") return "GAP I";
  if (text === "GAP II" || text === "GAP 2") return "GAP II";
  if (text === "GAP III" || text === "GAP 3") return "GAP III";
  return "";
}

// ---------------------------------------------------------------------------
// Gaya layer tambahan
// ---------------------------------------------------------------------------

export type LegendItem = { label: string; color: string };

export type OverlayStyle = {
  /** properti fitur yang menentukan warna (kategori) */
  colorBy?: string;
  colors?: Record<string, string>;
  defaultColor: string;
  radius?: number; // untuk titik
  weight?: number; // untuk garis/tepi
  fillOpacity?: number;
  /** properti yang ditampilkan di popup (urut), beserta labelnya */
  popupFields: Array<[string, string]>;
};

const BLOCK_FIELDS: Array<[string, string]> = [
  ["kode_est", "Estate"],
  ["kode_afd", "Afdeling"],
  ["kode_blok", "Blok"],
];

export const OVERLAY_STYLES: Record<string, OverlayStyle> = {
  sawit: {
    colorBy: "kategori",
    colors: { Normal: "#16a34a", Kuning: "#eab308", Mati: "#dc2626" },
    defaultColor: "#64748b",
    radius: 3,
    popupFields: [["objectid", "Object ID"], ["kategori", "Kondisi"], ["diameter", "Diameter"], ["jarak", "Jarak"], ...BLOCK_FIELDS],
  },
  tph: {
    colorBy: "kategori",
    colors: { Estimasi: "#f97316", Survei: "#8b5cf6" },
    defaultColor: "#f97316",
    radius: 5,
    popupFields: [["tph_id", "ID TPH"], ["kategori", "Kategori"], ...BLOCK_FIELDS],
  },
  slope: {
    colorBy: "kelerengan",
    colors: SLOPE_RAMP,
    defaultColor: "#fca5a5",
    weight: 0.6,
    fillOpacity: 0.55,
    popupFields: [["kelerengan", "Kelerengan (%)"], ["kategori", "Kategori"], ["luas", "Luas (ha)"], ...BLOCK_FIELDS],
  },
  landuse: {
    colorBy: "landuse",
    colors: { Sawit: "#86efac", Jalan: "#d6d3d1", Terjal: "#fca5a5", Rawa: "#93c5fd" },
    defaultColor: "#c4b5fd",
    weight: 0.6,
    fillOpacity: 0.55,
    popupFields: [["landuse", "Land Use"], ["landuse_class", "Kelas"], ["ownership", "Kepemilikan"], ["luas", "Luas (ha)"], ...BLOCK_FIELDS],
  },
  jalan: {
    colorBy: "kategori",
    colors: { "Main Road": "#b45309", "Jalan Poros": "#d97706", "Collection Road": "#f59e0b", "Jalan Bantu": "#facc15" },
    defaultColor: "#a16207",
    weight: 3,
    popupFields: [["kategori", "Kategori"], ["lebar", "Lebar (m)"], ["panjang", "Panjang (m)"], ["ownership", "Kepemilikan"], ...BLOCK_FIELDS],
  },
  jembatan: {
    defaultColor: "#0284c7",
    radius: 7,
    popupFields: [["kategori", "Kategori"], ["objectid", "Object ID"], ...BLOCK_FIELDS],
  },
  drainase: {
    defaultColor: "#0891b2",
    radius: 5,
    popupFields: [
      ["nama", "Nama"], ["kategori", "Kategori"], ["jenis", "Jenis"],
      ["diameter", "Diameter"], ["panjang", "Panjang (m)"], ["kedalaman", "Kedalaman"],
      ["kondisi", "Kondisi"], ["keterangan", "Keterangan"], ...BLOCK_FIELDS,
    ],
  },
};

const GENERIC_COLORS = ["#06b6d4", "#ec4899", "#14b8a6", "#6366f1", "#84cc16", "#f43f5e"];

export function getOverlayStyle(code: string, index = 0): OverlayStyle {
  return OVERLAY_STYLES[code] ?? {
    defaultColor: GENERIC_COLORS[index % GENERIC_COLORS.length] as string,
    radius: 5,
    weight: 2,
    fillOpacity: 0.45,
    popupFields: [],
  };
}

export function getOverlayColor(style: OverlayStyle, properties: Record<string, unknown> | null | undefined): string {
  if (!style.colorBy || !style.colors) return style.defaultColor;
  const value = properties?.[style.colorBy];
  return (value != null && style.colors[String(value)]) || style.defaultColor;
}

export function getOverlayLegend(style: OverlayStyle): LegendItem[] {
  if (!style.colors) return [];
  return Object.entries(style.colors).map(([label, color]) => ({ label, color }));
}
