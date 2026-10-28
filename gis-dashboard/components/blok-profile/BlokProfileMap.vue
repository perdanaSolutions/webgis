<script setup lang="ts">
import { onBeforeUnmount, onMounted, shallowRef, toRaw, watch } from "vue";
import "leaflet/dist/leaflet.css";

import type { OverlayLayer } from "~/composables/useMapOverlays";
import type { BlockCollection } from "~/stores/blokProfileStore";
import {
  applyBasemapZoom,
  createBasemapTileLayer,
  WMS_TILE_TIMEOUT_MS,
  observeBasemapTiles,
  probeWmsReachable,
  type BasemapStatus,
} from "~/utils/mapBasemap";
import { BASEMAPS, BUDGET_GAP_COLOR, type BasemapKey, getOverlayColor, readBudgetCategory, readComparisonBudgetCategory, readPlantingYear } from "~/utils/mapLayers";
import {
  blokPopupFromDetail,
  blokPopupFromFeature,
  buildBlokPopupHtml,
  buildBlokPopupSkeletonHtml,
  comparisonFromProperties,
  getBulanPopupLabel,
  periodAvailabilityNotice,
  type BlokPopupData,
} from "~/utils/mapBlokPopup";
import { viewportPopupMaxWidth } from "~/utils/viewportLayout";
import { areaBubblesVisible, bubbleSize, groupBlocksByArea } from "~/utils/areaBubbles";
import { installSmoothWheelZoom } from "~/utils/smoothWheelZoom";
import { bboxCenter, featuresBBox, roundScaleMeters, scaleStep, zoomForScale } from "~/utils/mapView";

type Insets = { top: number; right: number; bottom: number; left: number };
type L = typeof import("leaflet");

const props = defineProps<{
  blocks: BlockCollection | null;
  selectedId: string;
  showBlocks: boolean;
  /** Garis batas saja. Pewarnaan kategori yield baru dipakai saat ini nyala. */
  showYieldGap: boolean;
  /** Blok diwarnai menurut tahun tanam. Tidak menyala bersamaan dengan yield gap. */
  showPlantingYear: boolean;
  overlays: OverlayLayer[];
  basemap: BasemapKey;
  opacity: number; // 0..1
  /** Kategori budget yang sedang diwarnai. Kunci: OPTIMUM, GAP I, GAP II, GAP III. */
  budgetColors: Record<string, boolean>;
  insets: Insets;
  requestDetail: (blokId: string, bulan: string, tahun: string) => Promise<Record<string, any>>;
  /** Periode awal popup untuk properti blok (bulan produksi yang mewarnai blok). */
  popupPeriod: (properties?: Record<string, any>) => { bulan: string; tahun: string };
  /** Filter Kebun "Semua" di semua level -> tampilkan bubble jumlah blok per area. */
  showAreaBubbles?: boolean;
  /** kode_area -> nama area (dari opsi Filter Kebun). */
  areaNames?: Record<string, string>;
}>();

const emit = defineEmits<{
  (e: "select", blokId: string): void;
  (e: "deselect"): void;
  (e: "basemap-status", status: BasemapStatus): void;
  /** Klik/tap di area peta (termasuk blok) -> induk menutup kartu kiri/kanan. */
  (e: "map-click"): void;
}>();

const container = shallowRef<HTMLElement | null>(null);
let Lf: L | null = null;
let map: import("leaflet").Map | null = null;
let basemapLayers: import("leaflet").TileLayer[] = [];
let basemapToken = 0;
let stopBasemapWatch: (() => void) | null = null;
let blockLayer: import("leaflet").GeoJSON | null = null;
let labelLayer: import("leaflet").LayerGroup | null = null;
let comparisonLayer: import("leaflet").LayerGroup | null = null;
let pointRenderer: import("leaflet").Canvas | null = null;
let polygonRenderer: import("leaflet").Canvas | null = null;
/**
 * Batas blok digambar di Canvas, bukan SVG. Ratusan poligon SVG (masing-masing ratusan titik)
 * diproyeksikan ulang & ditulis ulang ke DOM di setiap zoomend -> scroll/pinch tersendat.
 */
let blockRenderer: import("leaflet").Canvas | null = null;
const overlayLayers = new Map<string, import("leaflet").GeoJSON>();
let slopeLabelLayer: import("leaflet").LayerGroup | null = null;
const popupLoadSeq = new Map<string, number>();
const popupCache = new Map<string, { bulan: string; tahun: string; popupData: BlokPopupData }>();
let panOnSelect = true;
let skipViewAdjust = false;
/** Saat layer batas diganti, popup tertutup karena layer hilang — bukan aksi tutup user. */
let rebuilding = false;

/**
 * Label kode blok tampil bila garis skala menunjukkan "1 km" atau lebih dekat.
 * Dihitung dari jarak nyata per 100 px (bukan level zoom bulat) agar tetap benar pada zoom pecahan.
 * Label Leaflet "1 km" berlaku sampai < 2 km per 100 px.
 */
const LABEL_MAX_SCALE_M = 2000;
/** Batas jumlah label di layar sekaligus (hanya blok di dalam area pandang yang diberi label). */
const LABEL_MAX_ON_SCREEN = 900;
let labelMarkers: import("leaflet").Marker[] = [];
let areaBubbleLayer: import("leaflet").LayerGroup | null = null;
let stopSmoothWheel: (() => void) | null = null;
/** Lebar garis skala (px) — dasar definisi "100 m" dan "500 m". */
const SCALE_PX = 100;
/** Padding simetris saat fit semua blok. */
const FIT_PAD = 24;
/** Skala target terakhir dari tombol +/− (null = zoom bebas oleh user). */
let buttonScale: number | null = null;
let buttonZoom: number | null = null;

/**
 * Pastikan zoom pecahan (skala tepat 100 m / kelipatan 500 m) untuk aksi program/tombol
 * tidak dibulatkan, apa pun nilai zoomSnap peta.
 */
function freeZoom(run: () => void) {
  if (!map) return;
  const snap = map.options.zoomSnap;
  map.options.zoomSnap = 0;
  try { run(); } finally {
    map.options.zoomSnap = snap;
  }
}
const SLOPE_LABEL_MIN_ZOOM = 12;
/** Garis batas blok tanpa pewarnaan yield: abu-abu terang agar terbaca di citra satelit. */
const BOUNDARY_STROKE = "#d4d4d4";
const HIDDEN_POPUP_KEYS = new Set(["id", "blok_id", "block_id", "afd_id", "bulan", "tahun", "geometry", "geom"]);
const POPUP_LABELS: Record<string, string> = {
  objectid: "Object ID", tph_id: "ID TPH", kategori: "Kategori", diameter: "Diameter", jarak: "Jarak",
  kode_est: "Estate", kode_afd: "Afdeling", kode_blok: "Blok", kelerengan: "Kelerengan (%)", luas: "Luas (ha)",
  landuse: "Land Use", landuse_class: "Kelas", ownership: "Kepemilikan", lebar: "Lebar (m)", panjang: "Panjang (m)",
  nama: "Nama", jenis: "Jenis", kedalaman: "Kedalaman", kondisi: "Kondisi", keterangan: "Keterangan",
  shape_area: "Luas (m²)", shape_leng: "Keliling (m)",
};

// ------------------------------------------------------------------ util
function escapeHtml(value: unknown) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

function fmt(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("id-ID", { maximumFractionDigits: digits }) : "-";
}

function popupPanPadding() {
  return {
    autoPanPaddingTopLeft: [props.insets.left + 24, props.insets.top + 24] as [number, number],
    autoPanPaddingBottomRight: [props.insets.right + 24, props.insets.bottom + 24] as [number, number],
  };
}

function featureBlokId(feature: GeoJSON.Feature) {
  return String(feature.properties?.blok_id ?? "").trim();
}

function isLatLng(value: any): value is import("leaflet").LatLng {
  return !!value && typeof value.lat === "number" && typeof value.lng === "number";
}

/** Ray-cast: klik di dalam batas (bukan hanya di garis) tetap kena, meski isi poligon nyaris transparan. */
function ringContains(ring: import("leaflet").LatLng[], latlng: import("leaflet").LatLng) {
  let inside = false;
  const x = latlng.lng;
  const y = latlng.lat;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const current = ring[i];
    const previous = ring[j];
    if (!current || !previous) continue;
    const xi = current.lng;
    const yi = current.lat;
    const xj = previous.lng;
    const yj = previous.lat;
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polygonContains(rings: any[], latlng: import("leaflet").LatLng) {
  if (!rings.length || !isLatLng(rings[0]?.[0] ?? rings[0])) return false;
  const outer = isLatLng(rings[0]) ? rings : rings[0];
  if (!isLatLng(outer[0]) || !ringContains(outer, latlng)) return false;
  const holes = isLatLng(rings[0]) ? [] : rings.slice(1);
  return !holes.some((hole) => isLatLng(hole?.[0]) && ringContains(hole, latlng));
}

function layerContains(layer: any, latlng: import("leaflet").LatLng) {
  const latlngs = layer.getLatLngs?.();
  if (!latlngs?.length) return false;
  if (isLatLng(latlngs[0])) return ringContains(latlngs, latlng);
  if (isLatLng(latlngs[0][0])) return polygonContains(latlngs, latlng);
  return latlngs.some((polygon: any) => polygonContains(polygon, latlng));
}

function blockAt(latlng: import("leaflet").LatLng) {
  if (!blockLayer || !props.showBlocks) return null;
  let found: any = null;
  blockLayer.eachLayer((layer: any) => {
    if (layerContains(layer, latlng)) found = layer;
  });
  return found;
}

function errorStatus(error: unknown) {
  const err = error as { statusCode?: number; status?: number; response?: { status?: number } };
  return err?.statusCode ?? err?.status ?? err?.response?.status ?? null;
}

// ------------------------------------------------------------------ basemap
function mountBasemap(option: (typeof BASEMAPS)[number]) {
  if (!Lf || !map) return;
  stopBasemapWatch?.();
  stopBasemapWatch = null;
  basemapLayers.forEach((layer) => layer.removeFrom(map!));
  applyBasemapZoom(map, option);
  basemapLayers = option.tiles.map((tile) => {
    const layer = createBasemapTileLayer(Lf!, tile);
    // Ubin baru dimuat setelah gestur zoom berhenti (bukan tiap frame); ubin sekitar disimpan agar pan mulus.
    Object.assign(layer.options, { updateWhenZooming: false, keepBuffer: 4 });
    return layer.addTo(map!);
  });
}

async function applyBasemap() {
  if (!Lf || !map) return;
  const token = ++basemapToken;
  stopBasemapWatch?.();
  stopBasemapWatch = null;
  const option = BASEMAPS.find((b) => b.key === props.basemap) ?? BASEMAPS[0]!;
  const gated = option.tiles.some((tile) => tile.service === "wms");
  if (gated) {
    emit("basemap-status", "checking");
    const reachable = await probeWmsReachable(option);
    if (token !== basemapToken || !map) return;
    if (!reachable) {
      emit("basemap-status", "blocked");
      return;
    }
  }
  mountBasemap(option);
  emit("basemap-status", "ready");
  if (!gated) return;
  stopBasemapWatch = observeBasemapTiles(basemapLayers, () => {
    if (token === basemapToken) emit("basemap-status", "unavailable");
  }, WMS_TILE_TIMEOUT_MS);
}

// ------------------------------------------------------------------ popup blok
type LeafletLayer = import("leaflet").Layer;

function popupOf(layer: LeafletLayer) {
  return (layer as any).getPopup?.() as import("leaflet").Popup | undefined;
}

function protectPopup(layer: LeafletLayer) {
  const element = popupOf(layer)?.getElement?.() as HTMLElement | undefined;
  if (!element || !Lf) return;
  Lf.DomEvent.disableClickPropagation(element);
  Lf.DomEvent.disableScrollPropagation(element);
}

function setPopupHtml(layer: LeafletLayer, html: string) {
  const popup = popupOf(layer);
  if (!popup?.isOpen()) return;
  popup.setContent(html);
  popup.update();
  protectPopup(layer);
  centerPopupOnMobile(layer);
}

function isMobileViewport() {
  return typeof window !== "undefined" && window.matchMedia?.("(max-width: 767px)").matches;
}

/**
 * Mobile: popup Informasi Blok digeser ke tengah layar peta (horizontal & vertikal),
 * bukan sekadar "masuk layar" seperti autoPan bawaan Leaflet.
 */
function centerPopupOnMobile(layer: LeafletLayer) {
  if (!map || !container.value || !isMobileViewport()) return;
  const popup = popupOf(layer);
  const element = popup?.getElement?.() as HTMLElement | undefined;
  if (!popup?.isOpen() || !element) return;
  requestAnimationFrame(() => {
    if (!map || !container.value || !popup.isOpen()) return;
    const box = element.getBoundingClientRect();
    const stage = container.value.getBoundingClientRect();
    const dx = box.left + box.width / 2 - (stage.left + stage.width / 2);
    const dy = box.top + box.height / 2 - (stage.top + stage.height / 2);
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) map.panBy([dx, dy], { animate: true, duration: 0.25 });
  });
}

function attachPopupApply(layer: LeafletLayer, feature: GeoJSON.Feature) {
  const element = popupOf(layer)?.getElement?.() as HTMLElement | undefined;
  if (!element) return;
  protectPopup(layer);
  const apply = element.querySelector("[data-popup-apply]") as HTMLButtonElement | null;
  if (!apply) return;
  const button = apply.cloneNode(true) as HTMLButtonElement;
  apply.replaceWith(button);
  button.addEventListener("mousedown", (event) => {
    event.preventDefault();
    event.stopPropagation();
  });
  button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    window.setTimeout(() => {
      const bulan = (element.querySelector("[data-popup-bulan]") as HTMLSelectElement | null)?.value;
      const tahun = (element.querySelector("[data-popup-tahun]") as HTMLSelectElement | null)?.value;
      if (bulan && tahun) void loadBlockPopup(layer, feature, bulan, tahun, true);
    }, 0);
  });
}

function showBlockPopup(
  layer: LeafletLayer,
  feature: GeoJSON.Feature,
  data: BlokPopupData,
  errorMessage?: string,
  notice?: string,
) {
  const comparison = comparisonFromProperties((feature.properties ?? {}) as Record<string, any>);
  setPopupHtml(layer, buildBlokPopupHtml(data, { errorMessage, notice, comparison }));
  attachPopupApply(layer, feature);
}

async function loadBlockPopup(
  layer: LeafletLayer,
  feature: GeoJSON.Feature,
  bulan: string,
  tahun: string,
  keepPreviousOn404: boolean,
) {
  const blokId = featureBlokId(feature);
  const fallback = () => blokPopupFromFeature(feature.properties ?? {}, { bulan, tahun });
  if (!blokId) {
    showBlockPopup(layer, feature, fallback(), "blok_id tidak ditemukan pada data peta.");
    return;
  }

  const seq = (popupLoadSeq.get(blokId) ?? 0) + 1;
  popupLoadSeq.set(blokId, seq);
  const previous = popupCache.get(blokId);
  const kode = String(feature.properties?.kode_blok ?? "");
  setPopupHtml(layer, buildBlokPopupSkeletonHtml({ bulan, tahun, blokId, kodeBlok: kode }));

  try {
    const detail = await props.requestDetail(blokId, bulan, tahun);
    if (popupLoadSeq.get(blokId) !== seq) return;
    const popupData = blokPopupFromDetail(detail, { bulan, tahun });
    popupCache.set(blokId, { bulan, tahun, popupData });
    showBlockPopup(layer, feature, popupData, undefined, periodAvailabilityNotice(detail, { bulan, tahun }));
  } catch (error) {
    if (popupLoadSeq.get(blokId) !== seq) return;
    const missing = errorStatus(error) === 404;
    if (keepPreviousOn404 && previous) {
      const message = missing
        ? `Data filter ${getBulanPopupLabel(bulan)} ${tahun} tidak tersedia.`
        : "Gagal memuat detail blok. Data sebelumnya tetap ditampilkan.";
      showBlockPopup(layer, feature, previous.popupData, message);
      return;
    }
    const message = missing
      ? `Data filter ${getBulanPopupLabel(bulan)} ${tahun} tidak tersedia.`
      : "Gagal memuat detail blok. Coba lagi.";
    showBlockPopup(layer, feature, fallback(), message);
  }
}

function bindBlockPopup(layer: LeafletLayer, feature: GeoJSON.Feature) {
  layer.bindPopup(
    () => buildBlokPopupHtml(blokPopupFromFeature((feature.properties ?? {}) as Record<string, any>,
      props.popupPeriod(feature.properties as Record<string, any>))),
    {
      maxWidth: viewportPopupMaxWidth(360),
      minWidth: Math.min(280, viewportPopupMaxWidth(360)),
      className: "map-blok-popup-wrapper",
      closeOnClick: false,
      autoClose: true,
      autoPan: !isMobileViewport(),
      keepInView: !isMobileViewport(),
      ...popupPanPadding(),
    },
  );
  layer.on("popupopen", () => {
    protectPopup(layer);
    centerPopupOnMobile(layer);
    const current = props.popupPeriod(feature.properties as Record<string, any>);
    void loadBlockPopup(layer, feature, current.bulan, current.tahun, false);
  });
  layer.on("popupclose", () => {
    if (rebuilding) return;
    window.setTimeout(() => {
      if (anyBlockPopupOpen()) return;
      emit("deselect");
    }, 0);
  });
  layer.on("add", () => {
    const path = (layer as any)._path as SVGPathElement | undefined;
    path?.setAttribute("pointer-events", "all");
    paintBlock(layer, feature);
  });
}

function openClickedBlock(layer: any, latlng: import("leaflet").LatLng) {
  const feature = layer.feature as GeoJSON.Feature | undefined;
  const id = feature ? featureBlokId(feature) : "";
  emit("map-click");
  if (id && id !== props.selectedId) {
    panOnSelect = false;
    emit("select", id);
  }
  layer.openPopup(latlng);
}

// ------------------------------------------------------------------ batas blok
function featureProperties(feature: { properties?: Record<string, any> | null } | null | undefined) {
  const properties = feature?.properties;
  if (!properties) return {};
  return toRaw(properties);
}

/** Warna isi blok: tahun tanam atau kategori yield gap, tergantung layer yang menyala. */
function blockFill(properties: Record<string, any> | null | undefined) {
  if (props.showPlantingYear) return readPlantingYear(properties)?.color ?? null;
  if (!props.showYieldGap) return null;
  const category = readBudgetCategory(properties);
  if (!category || props.budgetColors?.[category] === false) return null;
  return BUDGET_GAP_COLOR[category] ?? null;
}

/** Warna titik pembanding. Kosong bila yield gap mati atau kategori itu disembunyikan. */
function comparisonMarkerColor(properties: Record<string, any> | null | undefined) {
  if (!props.showYieldGap) return null;
  const category = readComparisonBudgetCategory(properties);
  if (!category || props.budgetColors?.[category] === false) return null;
  return BUDGET_GAP_COLOR[category] ?? null;
}

function blockAnchor(layer: any): import("leaflet").LatLng | null {
  const point = polygonLabelLngLat(layer?.feature?.geometry);
  if (point && Lf) return Lf.latLng(point[1], point[0]);
  const bounds = layer.getBounds?.() as import("leaflet").LatLngBounds | undefined;
  if (!bounds?.isValid()) return null;
  return bounds.getCenter();
}

function blockStyle(feature: { properties?: Record<string, any> | null } | null | undefined) {
  const properties = featureProperties(feature);
  const selected = String(properties.blok_id ?? "") === props.selectedId;
  const fill = blockFill(properties);
  const opacity = props.opacity > 0 ? props.opacity : 1;
  if (!fill) {
    return {
      pane: "bp-blocks",
      color: selected ? "#ffffff" : BOUNDARY_STROKE,
      weight: selected ? 3.6 : 2.6,
      opacity: 1,
      fill: true,
      fillColor: BOUNDARY_STROKE,
      fillOpacity: 0,
      lineJoin: "round" as const,
      lineCap: "round" as const,
    };
  }
  return {
    pane: "bp-blocks",
    color: "#ffffff",
    weight: selected ? 3.5 : 1.4,
    opacity: 1,
    fill: true,
    fillColor: fill,
    fillOpacity: (selected ? 0.78 : 0.62) * opacity,
    lineJoin: "round" as const,
    lineCap: "round" as const,
  };
}

function paintBlock(layer: any, feature: { properties?: Record<string, any> | null } | null | undefined) {
  const style = blockStyle(feature);
  layer?.setStyle?.(style);
  const path = layer?._path as SVGElement | undefined;
  if (!path) return;
  const fill = blockFill(featureProperties(feature));
  if (fill) {
    path.style.setProperty("fill", fill, "important");
    path.style.setProperty("fill-opacity", String(style.fillOpacity), "important");
  } else {
    path.style.removeProperty("fill");
    path.style.removeProperty("fill-opacity");
  }
}

function anyBlockPopupOpen() {
  let open = false;
  blockLayer?.eachLayer((layer: any) => {
    if (layer.getPopup?.()?.isOpen?.()) open = true;
  });
  return open;
}

/** Layer blok terpilih (filter blok spesifik / klik peta). */
function selectedLayer(): any {
  if (!props.selectedId || !blockLayer) return null;
  return blockLayer.getLayers().find((l: any) => String(l.feature?.properties?.blok_id) === props.selectedId) ?? null;
}

/** Jarak (meter) yang diwakili garis skala 100 px pada zoom sekarang — sama dengan cara Leaflet menghitung skala. */
function currentScaleMeters() {
  if (!map) return 0;
  const y = map.getSize().y / 2;
  return map.distance(map.containerPointToLatLng([0, y]), map.containerPointToLatLng([SCALE_PX, y]));
}

/** Zoom yang membuat garis skala bernilai `meters` di titik `center`. */
function zoomAtScale(center: import("leaflet").LatLng, meters: number) {
  if (!map) return 0;
  const z0 = map.getZoom();
  // Ukur pada zoom sekarang di lintang target, lalu skala ∝ 2^-zoom.
  const p = map.project(center, z0);
  const a = map.unproject(p.subtract([SCALE_PX / 2, 0]), z0);
  const b = map.unproject(p.add([SCALE_PX / 2, 0]), z0);
  const now = map.distance(a, b);
  const z = zoomForScale(z0, now, meters * 1.0005);
  return Math.max(map.getMinZoom(), Math.min(map.getMaxZoom(), z));
}

/**
 * Fit presisi ke bbox (barat–timur, selatan–utara): tengah bbox sebenarnya, zoom dipilih dari lebar & tinggi
 * bbox terhadap ukuran peta saat ini (desktop/mobile), padding simetris. Kartu kiri/kanan tidak ikut dihitung.
 */
function fitBox(box: import("~/utils/mapView").BBox) {
  if (!map || !Lf) return;
  const c = bboxCenter(box);
  const bounds = Lf.latLngBounds([box.south, box.west], [box.north, box.east]);
  const zoom = Math.min(map.getBoundsZoom(bounds, false, Lf.point(FIT_PAD * 2, FIT_PAD * 2)), map.getMaxZoom());
  buttonScale = null;
  freeZoom(() => map!.setView(Lf!.latLng(c.lat, c.lng), zoom, { animate: true }));
}

/** Blok spesifik: sama dengan level filter lain — fit bbox blok itu (bukan skala statis 100 m). */
function focusBlock(layer: any) {
  const box = featuresBBox([layer?.feature]);
  if (!box) return false;
  fitBox(box);
  return true;
}

/**
 * Tengah presisi: bbox barat–timur & selatan–utara SEMUA blok yang tampil, tengahnya dihitung sendiri,
 * zoom dipilih agar lebar dan tinggi bbox muat. Padding simetris dan tidak dipengaruhi kartu kiri/kanan.
 */
function fitVisibleBlocks() {
  if (!map || !Lf || !blockLayer) return;
  const chosen = selectedLayer();
  if (chosen && focusBlock(chosen)) return;
  const box = featuresBBox(props.blocks?.features ?? []);
  if (box) fitBox(box);
}

function renderBlocks(fit: boolean) {
  if (!Lf || !map) return;
  rebuilding = true;
  try {
    blockLayer?.removeFrom(map);
    labelLayer?.removeFrom(map);
    comparisonLayer?.removeFrom(map);
    blockLayer = null;
    labelLayer = null;
    comparisonLayer = null;
    const features = props.blocks?.features ?? [];
    if (!features.length) {
      renderSelected();
      return;
    }

    blockLayer = Lf.geoJSON(props.blocks!, {
      pane: "bp-blocks",
      ...(blockRenderer ? { renderer: blockRenderer } : {}),
      style: (f) => blockStyle(f),
      onEachFeature: (feature, layer) => {
        const id = String(feature.properties?.blok_id ?? "");
        bindBlockPopup(layer, feature);
        layer.on("click", (event) => {
          Lf?.DomEvent.stop(event);
          openClickedBlock(layer, event.latlng);
        });
        layer.on("mouseover", () => (layer as any).setStyle?.({ weight: id === props.selectedId ? 3.5 : 2.4, opacity: 1 }));
        layer.on("mouseout", () => paintBlock(layer, feature));
      },
    });

    if (props.showBlocks) blockLayer.addTo(map);
    renderBlockMarks();
    renderAreaBubbles();
    if (fit) fitVisibleBlocks();
    renderSelected();
  } finally {
    rebuilding = false;
  }
}

function renderBlockMarks() {
  if (!Lf || !map || !blockLayer) return;
  labelLayer?.removeFrom(map);
  comparisonLayer?.removeFrom(map);
  labelLayer = Lf.layerGroup();
  labelMarkers = [];
  comparisonLayer = Lf.layerGroup();

  blockLayer.eachLayer((layer) => {
    const feature = (layer as any).feature as GeoJSON.Feature;
    const bounds = (layer as any).getBounds?.() as import("leaflet").LatLngBounds | undefined;
    if (!bounds?.isValid()) return;
    const properties = featureProperties(feature);
    const color = comparisonMarkerColor(properties);
    const center = blockAnchor(layer) ?? bounds.getCenter();
    const kode = escapeHtml(feature.properties?.kode_blok);
    const selected = String(properties.blok_id ?? "") === props.selectedId;

    if (color) {
      Lf!.circleMarker(center, {
        pane: "bp-labels",
        radius: 7,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillColor: color,
        fillOpacity: 1,
        interactive: false,
      }).addTo(comparisonLayer!);
    }

    void selected; // blok terpilih memakai label putih biasa (permintaan t116u), tanpa tag hijau.
    labelMarkers.push(Lf!.marker(center, {
      pane: "bp-labels",
      interactive: false,
      icon: Lf!.divIcon({
        className: "bp-block-label",
        html: `<span class="bp-block-label-text ${color ? "is-below" : "is-center"}">${kode}</span>`,
        iconSize: [0, 0],
      }),
    }));
  });

  updateLabelVisibility();
}

/** Bubble jumlah blok per area: dihitung sekali per data GeoJSON, bukan setiap zoom. */
function renderAreaBubbles() {
  if (!Lf || !map) return;
  areaBubbleLayer?.removeFrom(map);
  areaBubbleLayer = null;
  if (!props.showAreaBubbles || !props.blocks?.features?.length) return;
  areaBubbleLayer = Lf.layerGroup();
  for (const b of groupBlocksByArea(props.blocks.features)) {
    const size = bubbleSize(b.count);
    const areaName = props.areaNames?.[b.kodeArea] || b.kodeArea || "-";
    const marker = Lf.marker([b.lat, b.lng], {
      pane: "bp-bubbles",
      keyboard: true,
      title: `${areaName}: ${b.count} blok`,
      icon: Lf.divIcon({
        className: "bp-area-bubble",
        html: `<span style="width:${size}px;height:${size}px">${b.count.toLocaleString("id-ID")}</span>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
      }),
    });
    marker.bindPopup(
      `<div class="bp-popup"><div class="bp-popup-title"><span class="bp-dot" style="background:#e07b2a"></span>Jumlah Blok per Area</div>`
      + `<div class="bp-detail-row"><span>Nama PT</span><span>:</span><span>${escapeHtml(b.namaPt || "-")}</span></div>`
      + `<div class="bp-detail-row"><span>Area</span><span>:</span><span>${escapeHtml(areaName)}</span></div>`
      + `<div class="bp-detail-row"><span>Total blok</span><span>:</span><span>${b.count.toLocaleString("id-ID")}</span></div></div>`,
      { className: "bp-popup-wrap", maxWidth: viewportPopupMaxWidth(280), autoPan: !isMobileViewport(), ...popupPanPadding() },
    );
    // Klik bubble = klik di peta: kartu kiri/kanan ditutup agar popup terlihat (terutama di mobile).
    marker.on("click", () => emit("map-click"));
    marker.on("popupopen", () => centerPopupOnMobile(marker));
    marker.addTo(areaBubbleLayer);
  }
  syncAreaBubbles();
}

function syncAreaBubbles() {
  if (!map || !areaBubbleLayer) return;
  syncMarkLayer(areaBubbleLayer, areaBubblesVisible(currentScaleMeters()));
}

/**
 * Pekerjaan setelah zoom/pan (culling label, visibilitas label/bubble/slope) dijadwalkan sekali per frame
 * dan dilewati bila zoom & area pandang tidak berubah — tidak dijalankan di tengah gestur.
 */
let viewWorkRaf = 0;
let lastViewKey = "";
function scheduleViewWork() {
  if (viewWorkRaf) return;
  viewWorkRaf = requestAnimationFrame(() => {
    viewWorkRaf = 0;
    if (!map) return;
    const b = map.getBounds();
    const key = `${map.getZoom().toFixed(4)}|${b.toBBoxString()}`;
    if (key === lastViewKey) return;
    lastViewKey = key;
    updateLabelVisibility();
    if (labelLayer && map.hasLayer(labelLayer)) cullLabels();
    updateSlopeLabelVisibility();
    syncAreaBubbles();
  });
}

function syncMarkLayer(layer: import("leaflet").LayerGroup | null, visible: boolean) {
  if (!map || !layer) return;
  if (visible && !map.hasLayer(layer)) layer.addTo(map);
  if (!visible && map.hasLayer(layer)) layer.removeFrom(map);
}

/** Label hanya untuk blok di area pandang (+ sedikit margin) -> ringan meski ribuan blok. */
function cullLabels() {
  if (!map || !labelLayer) return;
  const bounds = map.getBounds().pad(0.15);
  const group = labelLayer;
  let shown = 0;
  for (const marker of labelMarkers) {
    const inside = shown < LABEL_MAX_ON_SCREEN && bounds.contains(marker.getLatLng());
    if (inside) shown += 1;
    const has = group.hasLayer(marker);
    if (inside && !has) group.addLayer(marker);
    else if (!inside && has) group.removeLayer(marker);
  }
}

function updateLabelVisibility() {
  if (!map || !labelLayer) return;
  const fewEnough = (props.blocks?.features.length ?? 0) <= 600;
  const labelsVisible = props.showBlocks && currentScaleMeters() < LABEL_MAX_SCALE_M;
  // Saat pertama tampil saja; selama pan/zoom, culling dikerjakan sekali di moveend.
  if (labelsVisible && !map.hasLayer(labelLayer)) cullLabels();
  syncMarkLayer(labelLayer, labelsVisible);
  syncMarkLayer(comparisonLayer, props.showBlocks && props.showYieldGap && fewEnough);
}

function renderSelected(pan = false) {
  if (!Lf || !map) return;
  blockLayer?.eachLayer((layer) => {
    const feature = (layer as any).feature as GeoJSON.Feature;
    const id = String(feature.properties?.blok_id ?? "");
    paintBlock(layer, feature);
    if (id !== props.selectedId) return;
    (layer as any).bringToFront?.();
    // Tidak ada tag hijau lagi: blok terpilih memakai label putih biasa dari renderBlockMarks.
    if (pan) focusBlock(layer);
  });
}

// ------------------------------------------------------------------ layer data
function overlayPane(type: string) {
  const t = type.toUpperCase();
  return t.includes("POINT") ? "bp-points" : t.includes("LINE") ? "bp-lines" : "bp-polygons";
}

function overlayFields(layer: OverlayLayer, properties: Record<string, any>): Array<[string, string]> {
  const named = layer.style.popupFields.filter(([key]) => {
    const value = properties[key];
    return value !== null && value !== undefined && value !== "";
  });
  if (named.length) return named;
  return Object.keys(properties)
    .filter((key) => !HIDDEN_POPUP_KEYS.has(key) && properties[key] !== null && properties[key] !== undefined && properties[key] !== "" && typeof properties[key] !== "object")
    .map((key) => [key, POPUP_LABELS[key] ?? key.replace(/_/g, " ")]);
}

function overlayPopup(layer: OverlayLayer, properties: Record<string, any>) {
  const rows = overlayFields(layer, properties)
    .map(([key, label]) => {
      const raw = properties[key];
      const value = typeof raw === "number" ? fmt(raw, 2) : raw;
      return `<div class="bp-detail-row"><span>${escapeHtml(label)}</span><span>:</span><span>${escapeHtml(value)}</span></div>`;
    })
    .join("");
  const period = properties.bulan && properties.tahun
    ? `<span class="bp-period">${escapeHtml(getBulanPopupLabel(String(properties.bulan)))} ${escapeHtml(properties.tahun)}</span>`
    : "";
  const body = rows || `<p class="bp-empty">Tidak ada atribut pada fitur ini.</p>`;
  return `<div class="bp-popup"><div class="bp-popup-title"><span class="bp-dot" style="background:${escapeHtml(layer.style.defaultColor)}"></span>${escapeHtml(layer.name)}${period}</div>${body}</div>`;
}

function slopeClassLabel(value: string) {
  const text = value.trim().replace(/%/g, "");
  return text ? `${text}%` : "";
}

function clearSlopeLabels() {
  slopeLabelLayer?.removeFrom(map!);
  slopeLabelLayer = null;
}

/** Satu label per blok, di tengah kumpulan poligon slope blok itu. */
function renderSlopeLabels(geo: import("leaflet").GeoJSON) {
  if (!Lf || !map) return;
  clearSlopeLabels();
  const groups = new Map<string, { kode: string; classes: Set<string>; lat: number; lng: number; n: number }>();
  geo.eachLayer((layer: any) => {
    const feature = layer.feature as GeoJSON.Feature | undefined;
    const properties = (feature?.properties ?? {}) as Record<string, any>;
    const kode = String(properties.kode_blok ?? "").trim();
    const id = String(properties.blok_id ?? `${properties.kode_est ?? ""}|${properties.kode_afd ?? ""}|${kode}`);
    const bounds = layer.getBounds?.() as import("leaflet").LatLngBounds | undefined;
    if (!bounds?.isValid?.()) return;
    const center = bounds.getCenter();
    const kelas = String(properties.kelerengan ?? "").trim();
    const current = groups.get(id);
    if (!current) {
      groups.set(id, { kode, classes: new Set(kelas ? [kelas] : []), lat: center.lat, lng: center.lng, n: 1 });
      return;
    }
    current.n += 1;
    current.lat += center.lat;
    current.lng += center.lng;
    if (kelas) current.classes.add(kelas);
  });

  slopeLabelLayer = Lf.layerGroup();
  groups.forEach((group) => {
    const classes = [...group.classes];
    const kelas = classes.length === 1 ? slopeClassLabel(classes[0] ?? "") : "";
    const title = ["Slope", group.kode, kelas].filter(Boolean).join(" · ");
    Lf!.marker([group.lat / group.n, group.lng / group.n], {
      pane: "bp-labels",
      interactive: false,
      icon: Lf!.divIcon({
        className: "bp-slope-label",
        html: `<div class="bp-slope-pill">${escapeHtml(title)}</div>`,
        iconSize: [0, 0],
      }),
    }).addTo(slopeLabelLayer!);
  });
  updateSlopeLabelVisibility();
}

function updateSlopeLabelVisibility() {
  if (!map || !slopeLabelLayer) return;
  const count = slopeLabelLayer.getLayers().length;
  const zoom = map.getZoom();
  const visible = count > 0 && (count <= 80 || zoom >= SLOPE_LABEL_MIN_ZOOM);
  if (visible && !map.hasLayer(slopeLabelLayer)) slopeLabelLayer.addTo(map);
  if (!visible && map.hasLayer(slopeLabelLayer)) slopeLabelLayer.removeFrom(map);
}

function renderOverlays() {
  if (!Lf || !map) return;
  const wanted = new Set(props.overlays.filter((l) => l.enabled && l.data).map((l) => l.code));
  if (!wanted.has("slope")) clearSlopeLabels();
  overlayLayers.forEach((layer, code) => {
    if (!wanted.has(code)) {
      layer.removeFrom(map!);
      overlayLayers.delete(code);
    }
  });
  for (const layer of props.overlays) {
    if (!layer.enabled || !layer.data) continue;
    const existing = overlayLayers.get(layer.code);
    if (existing && (existing as any)._bpData === layer.data) {
      applyOverlayOpacity(existing, layer);
      continue;
    }
    existing?.removeFrom(map);
    if (layer.code === "slope") clearSlopeLabels();
    const pane = overlayPane(layer.geometryType);
    const isLine = layer.geometryType.toUpperCase().includes("LINE");
    const geo = Lf.geoJSON(layer.data, {
      pane,
      style: (f) => ({
        ...(pane === "bp-polygons" && polygonRenderer ? { renderer: polygonRenderer } : {}),
        color: isLine ? getOverlayColor(layer.style, f?.properties) : "#ffffff",
        weight: layer.style.weight ?? 1,
        opacity: props.opacity,
        fillColor: getOverlayColor(layer.style, f?.properties),
        fillOpacity: (layer.style.fillOpacity ?? 0.55) * props.opacity,
        bubblingMouseEvents: false,
      }),
      pointToLayer: (f, latlng) => Lf!.circleMarker(latlng, {
        renderer: pointRenderer ?? undefined,
        pane: "bp-points",
        radius: layer.style.radius ?? 5,
        color: layer.code === "sawit" ? "#1f2937" : "#ffffff",
        weight: layer.code === "sawit" ? 0.3 : 1.2,
        opacity: props.opacity,
        fillColor: getOverlayColor(layer.style, f.properties),
        fillOpacity: props.opacity,
        interactive: true,
        bubblingMouseEvents: false,
      }),
      onEachFeature: (f, l) => {
        l.on("click", (event) => Lf?.DomEvent.stopPropagation(event));
        l.bindPopup(() => overlayPopup(layer, (f.properties ?? {}) as Record<string, any>), {
          className: "bp-popup-wrap",
          maxWidth: viewportPopupMaxWidth(280),
          autoClose: true,
          ...popupPanPadding(),
        });
      },
    });
    (geo as any)._bpData = layer.data;
    geo.addTo(map);
    overlayLayers.set(layer.code, geo);
    if (layer.code === "slope") renderSlopeLabels(geo);
  }
}

function applyOverlayOpacity(geo: import("leaflet").GeoJSON, layer: OverlayLayer) {
  geo.eachLayer((l: any) => l.setStyle?.({
    opacity: props.opacity,
    fillOpacity: (l instanceof Lf!.CircleMarker ? 1 : (layer.style.fillOpacity ?? 0.55)) * props.opacity,
  }));
}

// ------------------------------------------------------------------ kontrol
/** Tombol zoom: garis skala bergeser satu anak tangga 500 m (100 m ↔ 500 m ↔ 1 km ↔ 1,5 km …), animasi halus. */
function stepZoom(direction: "in" | "out") {
  if (!map) return;
  const target = scaleStep(currentScaleMeters(), direction);
  const zoom = zoomAtScale(map.getCenter(), target);
  buttonScale = target;
  buttonZoom = zoom;
  freeZoom(() => map!.setZoom(zoom, { animate: true }));
}
function zoomIn() { stepZoom("in"); }
function zoomOut() { stepZoom("out"); }
function suppressNextPan() { skipViewAdjust = true; }
function releasePanSkip() { skipViewAdjust = false; }
function fitScope() {
  fitVisibleBlocks();
}

function placeCornerControls() {
  if (!container.value || !map) return;
  map.attributionControl?.setPosition("bottomleft");
  const bl = container.value.querySelector(".leaflet-bottom.leaflet-left") as HTMLElement | null;
  const scale = bl?.querySelector(".leaflet-control-scale");
  if (bl && scale) bl.insertBefore(scale, bl.firstChild);
  if (bl) {
    // Kartu kiri/kanan menimpa peta: skala km tetap di pojok kiri bawah.
    bl.style.marginLeft = "12px";
    bl.style.marginBottom = "12px";
  }
  const br = container.value.querySelector(".leaflet-bottom.leaflet-right") as HTMLElement | null;
  if (br) {
    br.style.left = "";
    br.style.right = "";
    br.style.marginLeft = "";
    br.style.marginRight = "";
    br.style.marginBottom = "";
  }
}

function applyInsets() {
  placeCornerControls();
  map?.invalidateSize();
}

function invalidateSize() {
  map?.invalidateSize({ animate: false });
}

defineExpose({ zoomIn, zoomOut, fitScope, suppressNextPan, releasePanSkip, invalidateSize });

// ------------------------------------------------------------------ siklus hidup
onMounted(async () => {
  Lf = await import("leaflet");
  if (!container.value) return;
  // zoomSnap 0: scroll/trackpad/pinch bebas mengikuti gerakan user (tanpa pembulatan level zoom),
  // juga tidak ada "lompatan" scroll pertama setelah zoom pecahan dari tombol +/−.
  map = Lf.map(container.value, { zoomControl: false, closePopupOnClick: true, zoomSnap: 0 }).setView([1.2, 117.5], 7);
  for (const [name, z] of [["bp-blocks", 410], ["bp-polygons", 420], ["bp-lines", 430], ["bp-points", 440], ["bp-labels", 450], ["bp-bubbles", 460]] as const) {
    map.createPane(name).style.zIndex = String(z);
  }
  map.getPane("bp-labels")!.style.pointerEvents = "none";
  pointRenderer = Lf.canvas({ pane: "bp-points", padding: 0.5 });
  polygonRenderer = Lf.canvas({ pane: "bp-polygons", padding: 0.5 });
  blockRenderer = Lf.canvas({ pane: "bp-blocks", padding: 0.5, tolerance: 2 }); // ribuan poligon landuse/slope: SVG terlalu berat
  map.attributionControl?.setPosition("bottomleft");
  const scale = Lf.control.scale({ position: "bottomleft", imperial: false, maxWidth: SCALE_PX });
  const leafletRound = (scale as any)._getRoundNum.bind(scale);
  // Label kelipatan 500 m HANYA setelah tombol +/−; zoom bebas memakai pembulatan bawaan Leaflet.
  (scale as any)._getRoundNum = (n: number) => (buttonScale !== null ? roundScaleMeters(n, leafletRound) : leafletRound(n));
  scale.addTo(map);
  // zoomstart animasi Leaflet terpicu di frame berikutnya (setelah flag program di-reset), jadi
  // penanda skala tombol dicek di zoomend: zoom akhir harus sama dengan zoom hasil tombol.
  // Ratusan label teks (dengan bayangan) yang ikut dianimasikan tiap langkah zoom adalah penyebab
  // scroll/pinch tersendat (terukur: long task 200–1000 ms). Label disembunyikan selama zoom berlangsung
  // dan muncul lagi 150 ms setelah zoom berhenti.
  const labelPane = map.getPane("bp-labels")!;
  let labelTimer: ReturnType<typeof setTimeout> | null = null;
  map.on("zoomstart", () => {
    if (labelTimer) clearTimeout(labelTimer);
    labelPane.classList.add("is-zooming");
  });
  map.on("zoomend", () => {
    if (labelTimer) clearTimeout(labelTimer);
    labelTimer = setTimeout(() => labelPane.classList.remove("is-zooming"), 150);
  });
  map.on("zoomend", () => {
    if (buttonScale !== null && (buttonZoom === null || Math.abs(map!.getZoom() - buttonZoom) > 1e-6)) buttonScale = null;
  });
  map.on("moveend", scheduleViewWork);
  // Wheel/trackpad/pinch-trackpad halus (rAF), menggantikan scrollWheelZoom bawaan (debounce 40 ms + animasi per langkah).
  stopSmoothWheel = installSmoothWheelZoom(map, Lf);
  map.on("click", (event) => {
    emit("map-click");
    const layer = blockAt(event.latlng);
    if (!layer) return;
    openClickedBlock(layer, event.latlng);
  });
  applyBasemap();
  setTimeout(applyInsets, 0);
  renderBlocks(true);
  renderOverlays();
});

onBeforeUnmount(() => {
  rebuilding = true;
  basemapToken += 1;
  stopBasemapWatch?.();
  stopSmoothWheel?.();
  if (viewWorkRaf) cancelAnimationFrame(viewWorkRaf);
  map?.remove();
  map = null;
  overlayLayers.clear();
  slopeLabelLayer = null;
});

watch(() => props.blocks, () => renderBlocks(true));
watch(() => props.selectedId, (id, previous) => {
  const adjust = !skipViewAdjust;
  skipViewAdjust = false;
  const pan = adjust && panOnSelect && !!id;
  panOnSelect = true;
  renderBlockMarks();
  renderSelected(pan);
  if (adjust && !id && previous) fitVisibleBlocks();
});
watch(() => props.showBlocks, () => {
  if (!map || !blockLayer) return;
  if (props.showBlocks) blockLayer.addTo(map); else blockLayer.removeFrom(map);
  updateLabelVisibility();
});
watch(() => props.overlays.map((l) => [l.code, l.enabled, l.data]), renderOverlays);
watch(() => props.opacity, () => {
  overlayLayers.forEach((geo, code) => {
    const layer = props.overlays.find((l) => l.code === code);
    if (layer) applyOverlayOpacity(geo, layer);
  });
  renderSelected();
});
watch(() => props.budgetColors, () => {
  renderBlockMarks();
  renderSelected();
}, { deep: true });
watch(() => [props.showYieldGap, props.showPlantingYear], () => {
  renderBlockMarks();
  renderSelected();
});
watch(() => props.basemap, applyBasemap);
watch(() => [props.showAreaBubbles, props.areaNames], renderAreaBubbles);
watch(() => props.insets, applyInsets, { deep: true });
</script>

<template>
  <div ref="container" class="bp-map h-full w-full" />
</template>

<style>
.bp-map {
  background: #3f4a3a;
  /* Gestur di atas peta milik peta: halaman/induk tidak ikut scroll, tidak ada pull-to-refresh. */
  touch-action: none;
  overscroll-behavior: contain;
}
.bp-area-bubble { background: none; border: none; }
.bp-area-bubble span {
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #fff;
  border-radius: 9999px;
  background: rgba(224, 123, 42, 0.92);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
  cursor: pointer;
}
.bp-area-bubble:hover span, .bp-area-bubble:focus span { background: #c9661c; }
.bp-map .leaflet-bp-blocks-pane path { pointer-events: all !important; }

.bp-map .leaflet-bp-labels-pane.is-zooming { display: none; }
.bp-block-label {
  background: none;
  border: none;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.85);
}
.bp-block-label-text.is-center,
.bp-block-label-text.is-below {
  display: inline-block;
  width: max-content;
}
.bp-block-label-text.is-center { transform: translate(-50%, -50%); }
.bp-block-label-text.is-below { transform: translate(-50%, 10px); }

.bp-slope-label {
  background: none;
  border: none;
}
.bp-slope-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 9999px;
  background: rgba(31, 42, 24, 0.92);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.01em;
  white-space: nowrap;
  transform: translate(-50%, -50%);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
}

/* Leaflet memosisikan marker lewat transform elemen luar -> geser di elemen dalam. */
.bp-selected-tag { background: none; border: none; }
.bp-selected-tag .bp-tag-inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 10px;
  background: rgba(63, 87, 40, 0.92);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  transform: translate(-50%, -50%);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
}

.bp-selected-tag .bp-pin {
  width: 10px;
  height: 10px;
  border: 2px solid #fff;
  border-radius: 9999px 9999px 9999px 0;
  transform: rotate(-45deg);
}

.bp-map .leaflet-control-scale-line {
  border: none;
  border-top: 3px solid #55604c;
  background: rgba(255, 253, 249, 0.92);
  color: #24301c;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px 2px;
  border-radius: 9999px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
}

.bp-popup-wrap .leaflet-popup-content-wrapper { border-radius: 10px; padding: 0; }
.bp-popup-wrap .leaflet-popup-content {
  margin: 0;
}
.bp-popup { padding: 12px 12px 10px; color: #1f2937; }
.bp-popup .bp-popup-title { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding-right: 16px; font-size: 13px; font-weight: 700; color: #111827; }
.bp-popup .bp-dot { width: 10px; height: 10px; border-radius: 9999px; flex-shrink: 0; }
.bp-popup .bp-period { margin-left: auto; font-size: 11px; font-weight: 500; color: #6b7280; }
.bp-popup .bp-detail-row { display: grid; grid-template-columns: 108px 10px minmax(0, 1fr); gap: 0; align-items: start; font-size: 12px; line-height: 1.45; }
.bp-popup .bp-detail-row span:first-child,
.bp-popup .bp-detail-row span:nth-child(2) { color: #6b7280; }
.bp-popup .bp-detail-row span:last-child { color: #111827; font-weight: 600; word-break: break-word; }
.bp-popup .bp-empty { margin: 0; font-size: 12px; color: #6b7280; }

.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-content-wrapper { border-radius: 10px; padding: 0; overflow: visible; }
.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-content {
  margin: 0;
}
.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-tip { background: #fff; }

@keyframes map-blok-skeleton-shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
