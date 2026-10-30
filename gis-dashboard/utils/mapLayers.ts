/**
 * Konfigurasi peta dasar (basemap) dan gaya layer tambahan untuk halaman peta.
 * Daftar layer tambahan diambil dari katalog backend (GET /v1/spatial/geo/catalog);
 * file ini hanya menentukan tampilannya. Layer yang belum dikenal memakai gaya default.
 */

export type BasemapKey =
  | "osm"
  | "satellite"
  | "hybrid"
  | "topo"
  | "tpa-sga"
  | "light"
  | "dark";

export type BasemapTile = {
  url: string;
  attribution: string;
  maxZoom?: number;
  subdomains?: string;
  /** `wms` = GeoServer/MapServer. Kosong = ubin XYZ. */
  service?: "xyz" | "wms";
  /** Nama layer WMS, persis seperti tag `<Name>` di GetCapabilities. */
  layers?: string;
  format?: string;
  version?: string;
  transparent?: boolean;
  /** Query token akses. Nilainya tidak disimpan di sini; diambil dari env TOKEN_BASE_MAP. */
  tokenParam?: string;
  /**
   * `true` = ubin diminta ke proxy backend (`url` relatif ke apiBaseUrlPython, pakai JWT user);
   * backend yang menempelkan token GeoServer, jadi token tidak pernah sampai ke browser.
   */
  proxy?: boolean;
  /** Host server asli (untuk pesan dialog) bila `url` adalah proxy. */
  upstreamHost?: string;
  /** Zoom tertinggi yang masih menambah detail; di atasnya Leaflet memperbesar ubin ini (hemat request). */
  maxNativeZoom?: number;
  /** WMS: minta gambar lebih rapat dari ukuran ubin CSS (layar retina / zoom pecahan). Lihat wmsPixelRatio. */
  hiDpi?: boolean;
};

export type BasemapOption = {
  key: BasemapKey;
  label: string;
  preview: string; // warna/gradasi kartu pratinjau
  tiles: BasemapTile[]; // >1 = ditumpuk (mis. citra satelit + label)
};

const ESRI_ATTRIBUTION =
  "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, GIS User Community";
const OSM_ATTRIBUTION = "&copy; OpenStreetMap contributors";
const CARTO_ATTRIBUTION = `${OSM_ATTRIBUTION} &copy; CARTO`;

export const BASEMAPS: BasemapOption[] = [
  {
    key: "osm",
    label: "OpenStreetMap",
    preview: "linear-gradient(135deg,#f2efe9 0%,#aad3df 100%)",
    tiles: [
      {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: OSM_ATTRIBUTION,
        maxZoom: 19,
      },
    ],
  },
  {
    key: "satellite",
    label: "Esri World Imagery",
    preview: "linear-gradient(135deg,#2f4a2a 0%,#5b7443 50%,#1d3b52 100%)",
    tiles: [
      {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attribution: ESRI_ATTRIBUTION,
        maxZoom: 19,
      },
    ],
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
    tiles: [
      {
        url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attribution: `${OSM_ATTRIBUTION}, SRTM | &copy; OpenTopoMap (CC-BY-SA)`,
        maxZoom: 17,
      },
    ],
  },
  {
    key: "tpa-sga",
    label: "Foto Udara",
    preview: "linear-gradient(135deg,#1f3b24 0%,#6d8a45 55%,#c4b48a 100%)",
    tiles: [
      {
        // GeoServer digilink lewat proxy backend (GET /v1/basemap/foto-udara/wms). tpgis:tpgis_fu = layer group
        // gabungan seluruh foto udara (Berau, Kutim, Paser, ...); tpgis:TPA-SGA tidak ada di GeoServer.
        service: "wms",
        proxy: true,
        url: "/v1/basemap/foto-udara/wms",
        upstreamHost: "digilink.teladanprima.com",
        layers: "tpgis:tpgis_fu",
        // Foto: JPEG ~3–10x lebih kecil dari PNG dengan ketajaman setara (uji 30 Okt 2026), jadi ubin retina
        // 512 px JPEG (~45–75 KB) tetap lebih ringan dari ubin 256 px PNG lama (~140–170 KB).
        format: "image/jpeg",
        version: "1.1.1",
        transparent: false,
        hiDpi: true,
        // Resolusi sumber ~7 cm (WCS offsetVector 7,19e-7° Kutim2B, 0,07 m BERAU2); ubin 512 px pada z20 = ~7,5 cm
        // per piksel perangkat. Di atas z20 detail tidak bertambah, jadi ubin z20 diperbesar Leaflet.
        maxNativeZoom: 20,
        attribution: "Foto Udara &copy; Teladan Prima Agro",
        maxZoom: 22,
      },
    ],
  },
  // {
  //   key: "light",
  //   label: "CARTO Positron",
  //   preview: "linear-gradient(135deg,#fafafa 0%,#e5e7eb 100%)",
  //   tiles: [{
  //     url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  //     attribution: CARTO_ATTRIBUTION,
  //     maxZoom: 20,
  //     subdomains: "abcd",
  //   }],
  // },
  // {
  //   key: "dark",
  //   label: "CARTO Dark Matter",
  //   preview: "linear-gradient(135deg,#1f2937 0%,#111827 100%)",
  //   tiles: [{
  //     url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  //     attribution: CARTO_ATTRIBUTION,
  //     maxZoom: 20,
  //     subdomains: "abcd",
  //   }],
  // },
];

export const DEFAULT_BASEMAP: BasemapKey = "osm";

/**
 * Kelas kemiringan = data berurutan (datar -> curam) -> SATU gradasi hijau primary,
 * terang ke gelap (bukan hue berbeda-beda yang sulit dibedakan pembaca buta warna).
 * Dipakai legenda peta, layer slope, dan donut Analisa Kemiringan.
 */
export const SLOPE_RAMP: Record<string, string> = {
  "0-3": "#d7e4c8",
  "3-8": "#a3c07e",
  "8-15": "#638840",
  "15-25": "#3d5528",
};

/** Warna blok dari properties.produksi_tbs.kategori_budget. */
export const BUDGET_GAP_LAYERS = [
  { key: "OPTIMUM", label: "Optimum", color: "#3aa0ff", hint: "Varians > 0%" },
  {
    key: "GAP I",
    label: "Gap I",
    color: "#3ee07a",
    hint: "Varians −1% s.d. −20%",
  },
  {
    key: "GAP II",
    label: "Gap II",
    color: "#ffe34d",
    hint: "Varians −20% s.d. −40%",
  },
  {
    key: "GAP III",
    label: "Gap III",
    color: "#ff4d4d",
    hint: "Varians < −40%",
  },
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
      return parsed && typeof parsed === "object"
        ? (parsed as Record<string, any>)
        : null;
    } catch {
      return null;
    }
  }
  return typeof value === "object" ? (value as Record<string, any>) : null;
}

function pickField(record: Record<string, any> | null, name: string) {
  if (!record) return undefined;
  if (record[name] != null && record[name] !== "") return record[name];
  const key = Object.keys(record).find((item) => item.toLowerCase() === name);
  return key ? record[key] : undefined;
}

function normalizeBudgetCategory(raw: unknown): string {
  const text = String(raw ?? "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, " ");
  if (text === "OPTIMUM") return "OPTIMUM";
  if (text === "GAP I" || text === "GAP 1") return "GAP I";
  if (text === "GAP II" || text === "GAP 2") return "GAP II";
  if (text === "GAP III" || text === "GAP 3") return "GAP III";
  return "";
}

/** Nilai properties.produksi_tbs.kategori_budget, termasuk bila tersimpan sebagai JSON string. */
export function readBudgetCategory(
  properties: Record<string, any> | null | undefined,
): string {
  const props = properties ?? {};
  const produksi = asRecord(props.produksi_tbs);
  const raw =
    pickField(produksi, "kategori_budget") ??
    pickField(props, "kategori_budget") ??
    pickField(asRecord(produksi?.tbs), "kategori_budget");
  return normalizeBudgetCategory(raw);
}

/** Kategori budget periode pembanding (`produksi_tbs_comparison.kategori_budget`). */
export function readComparisonBudgetCategory(
  properties: Record<string, any> | null | undefined,
): string {
  const comparison = asRecord(properties?.produksi_tbs_comparison);
  return normalizeBudgetCategory(pickField(comparison, "kategori_budget"));
}

/** Tahun tanam blok dan warnanya dari properties.areal_statement (warna dari API). */
export function readPlantingYear(
  properties: Record<string, any> | null | undefined,
): { tahun: number; color: string } | null {
  const statement = asRecord(properties?.areal_statement);
  const tahun = Number(pickField(statement, "tahun_tanam"));
  const color = pickField(statement, "warna_tahun_tanam");
  if (!tahun || typeof color !== "string" || !color) return null;
  return { tahun, color };
}

/** Legenda tahun tanam: hanya tahun yang ada di blok peta, urut naik. */
export function plantingYearLegend(
  features: Array<{ properties?: Record<string, any> | null }>,
): LegendItem[] {
  const colors = new Map<number, string>();
  for (const feature of features) {
    const item = readPlantingYear(feature.properties);
    if (item) colors.set(item.tahun, item.color);
  }
  return [...colors.entries()]
    .sort(([a], [b]) => a - b)
    .map(([tahun, color]) => ({ label: `Tahun Tanam ${tahun}`, color }));
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

/** Tiga baris pertama semua popup layer (t121u): Estate, Afdeling, Blok — mengikuti slope. */
export const BLOCK_FIELDS: Array<[string, string]> = [
  ["kode_est", "Estate"],
  ["kode_afd", "Afdeling"],
  ["kode_blok", "Blok"],
];

export const OVERLAY_STYLES: Record<string, OverlayStyle> = {
  // Batas afdeling (garis kuning-oranye tanpa isi); popup khusus di utils/afdelingBoundary.ts.
  afdeling: {
    defaultColor: "#f59e0b",
    weight: 2.75,
    fillOpacity: 0,
    popupFields: [],
  },
  sawit: {
    colorBy: "kategori",
    colors: { Normal: "#16a34a", Kuning: "#eab308", Mati: "#dc2626" },
    defaultColor: "#64748b",
    radius: 3,
    popupFields: [
      ...BLOCK_FIELDS,
      ["objectid", "Object ID"],
      ["kategori", "Kondisi"],
      ["diameter", "Diameter"],
      ["jarak", "Jarak"],
    ],
  },
  tph: {
    colorBy: "kategori",
    colors: { Estimasi: "#f97316", Survei: "#8b5cf6" },
    defaultColor: "#f97316",
    radius: 5,
    popupFields: [
      ...BLOCK_FIELDS,
      ["tph_id", "ID TPH"],
      ["kategori", "Kategori"],
    ],
  },
  slope: {
    colorBy: "kelerengan",
    colors: SLOPE_RAMP,
    defaultColor: "#fca5a5",
    weight: 0.6,
    fillOpacity: 0.55,
    // Urutan permintaan Bayu (t120u): Estate, Afdeling, Blok, Kelerengan, Kategori, Luas.
    popupFields: [
      ...BLOCK_FIELDS,
      ["kelerengan", "Kelerengan (%)"],
      ["kategori", "Kategori"],
      ["luas", "Luas (ha)"],
    ],
  },
  landuse: {
    colorBy: "landuse",
    colors: {
      Sawit: "#86efac",
      Jalan: "#d6d3d1",
      Terjal: "#fca5a5",
      Rawa: "#93c5fd",
    },
    defaultColor: "#c4b5fd",
    weight: 0.6,
    fillOpacity: 0.55,
    popupFields: [
      ...BLOCK_FIELDS,
      ["landuse", "Land Use"],
      ["landuse_class", "Kelas"],
      ["ownership", "Kepemilikan"],
      ["luas", "Luas (ha)"],
    ],
  },
  jalan: {
    colorBy: "kategori",
    colors: {
      "Main Road": "#b45309",
      "Jalan Poros": "#d97706",
      "Collection Road": "#f59e0b",
      "Jalan Bantu": "#facc15",
    },
    defaultColor: "#a16207",
    weight: 3,
    popupFields: [
      ...BLOCK_FIELDS,
      ["kategori", "Kategori"],
      ["lebar", "Lebar (m)"],
      ["panjang", "Panjang (m)"],
      ["ownership", "Kepemilikan"],
    ],
  },
  jembatan: {
    defaultColor: "#0284c7",
    radius: 7,
    popupFields: [
      ...BLOCK_FIELDS,
      ["kategori", "Kategori"],
      ["objectid", "Object ID"],
    ],
  },
  drainase: {
    defaultColor: "#0891b2",
    radius: 5,
    popupFields: [
      ...BLOCK_FIELDS,
      ["nama", "Nama"],
      ["kategori", "Kategori"],
      ["jenis", "Jenis"],
      ["diameter", "Diameter"],
      ["panjang", "Panjang (m)"],
      ["kedalaman", "Kedalaman"],
      ["kondisi", "Kondisi"],
      ["keterangan", "Keterangan"],
    ],
  },
};

const GENERIC_COLORS = [
  "#06b6d4",
  "#ec4899",
  "#14b8a6",
  "#6366f1",
  "#84cc16",
  "#f43f5e",
];

export function getOverlayStyle(code: string, index = 0): OverlayStyle {
  return (
    OVERLAY_STYLES[code] ?? {
      defaultColor: GENERIC_COLORS[index % GENERIC_COLORS.length] as string,
      radius: 5,
      weight: 2,
      fillOpacity: 0.45,
      popupFields: [],
    }
  );
}

export function getOverlayColor(
  style: OverlayStyle,
  properties: Record<string, unknown> | null | undefined,
): string {
  if (!style.colorBy || !style.colors) return style.defaultColor;
  const value = properties?.[style.colorBy];
  return (value != null && style.colors[String(value)]) || style.defaultColor;
}

export function getOverlayLegend(style: OverlayStyle): LegendItem[] {
  if (!style.colors) return [];
  return Object.entries(style.colors).map(([label, color]) => ({
    label,
    color,
  }));
}
