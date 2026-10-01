<script setup lang="ts">
import { onBeforeUnmount, onMounted, shallowRef, toRaw, watch } from "vue";
import "leaflet/dist/leaflet.css";

import type { OverlayLayer } from "~/composables/useMapOverlays";
import type { BlockCollection } from "~/stores/blokProfileStore";
import { BASEMAPS, BUDGET_GAP_COLOR, type BasemapKey, getOverlayColor, readBudgetCategory } from "~/utils/mapLayers";
import {
  blokPopupFromDetail,
  blokPopupFromFeature,
  buildBlokPopupHtml,
  buildBlokPopupSkeletonHtml,
  getBulanPopupLabel,
  getCurrentPopupPeriod,
  periodAvailabilityNotice,
  type BlokPopupData,
} from "~/utils/mapBlokPopup";

type Insets = { top: number; right: number; bottom: number; left: number };
type L = typeof import("leaflet");

const props = defineProps<{
  blocks: BlockCollection | null;
  selectedId: string;
  showBlocks: boolean;
  overlays: OverlayLayer[];
  basemap: BasemapKey;
  opacity: number; // 0..1
  /** Kategori budget yang sedang diwarnai. Kunci: OPTIMUM, GAP I, GAP II, GAP III. */
  budgetColors: Record<string, boolean>;
  insets: Insets;
  requestDetail: (blokId: string, bulan: string, tahun: string) => Promise<Record<string, any>>;
}>();

const emit = defineEmits<{
  (e: "select", blokId: string): void;
  (e: "deselect"): void;
}>();

const container = shallowRef<HTMLElement | null>(null);
let Lf: L | null = null;
let map: import("leaflet").Map | null = null;
let basemapLayers: import("leaflet").TileLayer[] = [];
let blockLayer: import("leaflet").GeoJSON | null = null;
let labelLayer: import("leaflet").LayerGroup | null = null;
let selectedTag: import("leaflet").Marker | null = null;
let pointRenderer: import("leaflet").Canvas | null = null;
const overlayLayers = new Map<string, import("leaflet").GeoJSON>();
const popupLoadSeq = new Map<string, number>();
const popupCache = new Map<string, { bulan: string; tahun: string; popupData: BlokPopupData }>();
let panOnSelect = true;
/** Saat layer batas diganti, popup tertutup karena layer hilang — bukan aksi tutup user. */
let rebuilding = false;

const LABEL_MIN_ZOOM = 14;
const HIDDEN_POPUP_KEYS = new Set(["id", "blok_id", "block_id", "afd_id", "bulan", "tahun", "geometry", "geom"]);
const POPUP_LABELS: Record<string, string> = {
  objectid: "Object ID", tph_id: "ID TPH", kategori: "Kategori", diameter: "Diameter", jarak: "Jarak",
  kode_est: "Estate", kode_afd: "Afdeling", kode_blok: "Blok", kelerengan: "Kelerengan (%)", luas: "Luas (ha)",
  landuse: "Land Use", landuse_class: "Kelas", ownership: "Kepemilikan", lebar: "Lebar (m)", panjang: "Panjang (m)",
  nama: "Nama", jenis: "Jenis", kedalaman: "Kedalaman", kondisi: "Kondisi", keterangan: "Keterangan",
  shape_area: "Luas (m²)", shape_leng: "Keliling (m)",
};

// ------------------------------------------------------------------ util
function padding() {
  const i = props.insets;
  return { paddingTopLeft: [i.left + 24, i.top + 24] as [number, number], paddingBottomRight: [i.right + 24, i.bottom + 24] as [number, number] };
}

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
function applyBasemap() {
  if (!Lf || !map) return;
  const option = BASEMAPS.find((b) => b.key === props.basemap) ?? BASEMAPS[0]!;
  basemapLayers.forEach((layer) => layer.removeFrom(map!));
  basemapLayers = option.tiles.map((tile) => Lf!.tileLayer(tile.url, {
    attribution: tile.attribution, maxZoom: tile.maxZoom ?? 19, ...(tile.subdomains ? { subdomains: tile.subdomains } : {}),
  }).addTo(map!));
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
  setPopupHtml(layer, buildBlokPopupHtml(data, { errorMessage, notice }));
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
    () => buildBlokPopupHtml(blokPopupFromFeature((feature.properties ?? {}) as Record<string, any>, getCurrentPopupPeriod())),
    {
      maxWidth: 340,
      minWidth: 320,
      maxHeight: 460,
      className: "map-blok-popup-wrapper",
      closeOnClick: false,
      autoClose: true,
      autoPan: true,
      keepInView: true,
      ...popupPanPadding(),
    },
  );
  layer.on("popupopen", () => {
    protectPopup(layer);
    const current = getCurrentPopupPeriod();
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

function budgetFill(properties: Record<string, any> | null | undefined) {
  const category = readBudgetCategory(properties);
  if (!category || props.budgetColors?.[category] === false) return null;
  return BUDGET_GAP_COLOR[category] ?? null;
}

function blockStyle(feature: { properties?: Record<string, any> | null } | null | undefined) {
  const properties = featureProperties(feature);
  const selected = String(properties.blok_id ?? "") === props.selectedId;
  const fill = budgetFill(properties);
  const opacity = props.opacity > 0 ? props.opacity : 1;
  return {
    pane: "bp-blocks",
    color: "#ffffff",
    weight: selected ? 3.5 : 1.4,
    opacity: 1,
    fill: true,
    fillColor: fill ?? "#ffffff",
    fillOpacity: fill ? (selected ? 0.78 : 0.62) * opacity : selected ? 0.06 * opacity : 0.02,
  };
}

function paintBlock(layer: any, feature: { properties?: Record<string, any> | null } | null | undefined) {
  const style = blockStyle(feature);
  layer?.setStyle?.(style);
  const path = layer?._path as SVGElement | undefined;
  if (!path) return;
  const fill = budgetFill(featureProperties(feature));
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

function fitVisibleBlocks() {
  if (!map || !blockLayer) return;
  const bounds = blockLayer.getBounds();
  if (bounds.isValid()) map.fitBounds(bounds, { ...padding(), maxZoom: 16 });
}

function renderBlocks(fit: boolean) {
  if (!Lf || !map) return;
  rebuilding = true;
  try {
    blockLayer?.removeFrom(map);
    labelLayer?.removeFrom(map);
    blockLayer = null;
    labelLayer = null;
    const features = props.blocks?.features ?? [];
    if (!features.length) {
      renderSelected();
      return;
    }

    blockLayer = Lf.geoJSON(props.blocks!, {
      pane: "bp-blocks",
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

    // Label kode di pojok kiri atas setiap blok (seperti peta kerja kebun).
    labelLayer = Lf.layerGroup();
    blockLayer.eachLayer((layer) => {
      const feature = (layer as any).feature as GeoJSON.Feature;
      const bounds = (layer as any).getBounds?.() as import("leaflet").LatLngBounds | undefined;
      if (!bounds) return;
      Lf!.marker(bounds.getNorthWest(), {
        pane: "bp-labels",
        interactive: false,
        icon: Lf!.divIcon({ className: "bp-block-label", html: escapeHtml(feature.properties?.kode_blok), iconSize: undefined as any, iconAnchor: [-8, -8] }),
      }).addTo(labelLayer!);
    });

    if (props.showBlocks) {
      blockLayer.addTo(map);
      updateLabelVisibility();
    }
    if (fit) fitVisibleBlocks();
    renderSelected();
  } finally {
    rebuilding = false;
  }
}

function updateLabelVisibility() {
  if (!map || !labelLayer) return;
  const visible = props.showBlocks && map.getZoom() >= LABEL_MIN_ZOOM && (props.blocks?.features.length ?? 0) <= 600;
  if (visible && !map.hasLayer(labelLayer)) labelLayer.addTo(map);
  if (!visible && map.hasLayer(labelLayer)) labelLayer.removeFrom(map);
}

function renderSelected(pan = false) {
  if (!Lf || !map) return;
  selectedTag?.removeFrom(map);
  selectedTag = null;
  blockLayer?.eachLayer((layer) => {
    const feature = (layer as any).feature as GeoJSON.Feature;
    const id = String(feature.properties?.blok_id ?? "");
    paintBlock(layer, feature);
    if (id !== props.selectedId) return;
    (layer as any).bringToFront?.();
    const bounds = (layer as any).getBounds() as import("leaflet").LatLngBounds;
    const luas = feature.properties?.areal_statement?.luas_tanam;
    selectedTag = Lf!.marker(bounds.getCenter(), {
      pane: "bp-labels",
      interactive: false,
      icon: Lf!.divIcon({
        className: "bp-selected-tag",
        html: `<div class="bp-tag-inner"><span class="bp-pin" aria-hidden="true"></span>${escapeHtml(feature.properties?.kode_blok)}${luas ? ` · ${fmt(luas)} Ha` : ""}</div>`,
        iconSize: [0, 0],
      }),
    }).addTo(map!);
    if (pan) map!.fitBounds(bounds, { ...padding(), maxZoom: Math.max(map!.getZoom(), 15) });
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

function renderOverlays() {
  if (!Lf || !map) return;
  const wanted = new Set(props.overlays.filter((l) => l.enabled && l.data).map((l) => l.code));
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
    const pane = overlayPane(layer.geometryType);
    const isLine = layer.geometryType.toUpperCase().includes("LINE");
    const geo = Lf.geoJSON(layer.data, {
      pane,
      style: (f) => ({
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
          maxWidth: 300,
          autoClose: true,
          ...popupPanPadding(),
        });
      },
    });
    (geo as any)._bpData = layer.data;
    geo.addTo(map);
    overlayLayers.set(layer.code, geo);
  }
}

function applyOverlayOpacity(geo: import("leaflet").GeoJSON, layer: OverlayLayer) {
  geo.eachLayer((l: any) => l.setStyle?.({
    opacity: props.opacity,
    fillOpacity: (l instanceof Lf!.CircleMarker ? 1 : (layer.style.fillOpacity ?? 0.55)) * props.opacity,
  }));
}

// ------------------------------------------------------------------ kontrol
function zoomIn() { map?.zoomIn(); }
function zoomOut() { map?.zoomOut(); }
function fitScope() {
  if (!map) return;
  const target = props.selectedId
    ? (blockLayer?.getLayers().find((l: any) => String(l.feature?.properties?.blok_id) === props.selectedId) as any)?.getBounds?.()
    : blockLayer?.getBounds();
  if (target?.isValid()) map.fitBounds(target, { ...padding(), maxZoom: 16 });
}

function applyInsets() {
  if (!container.value) return;
  const bl = container.value.querySelector(".leaflet-bottom.leaflet-left") as HTMLElement | null;
  // Skala ditaruh tepat di atas bar ringkasan, sejajar tepi kirinya.
  if (bl) { bl.style.marginLeft = `${props.insets.left + 14}px`; bl.style.marginBottom = `${props.insets.bottom + 4}px`; }
  const br = container.value.querySelector(".leaflet-bottom.leaflet-right") as HTMLElement | null;
  if (br) {
    br.style.left = "0px";
    br.style.right = "auto";
    br.style.marginRight = "0px";
    br.style.marginLeft = `${props.insets.left + 108}px`;
    br.style.marginBottom = `${props.insets.bottom + 4}px`;
  }
  map?.invalidateSize();
}

defineExpose({ zoomIn, zoomOut, fitScope });

// ------------------------------------------------------------------ siklus hidup
onMounted(async () => {
  Lf = await import("leaflet");
  if (!container.value) return;
  map = Lf.map(container.value, { zoomControl: false, closePopupOnClick: true }).setView([1.2, 117.5], 7);
  for (const [name, z] of [["bp-blocks", 410], ["bp-polygons", 420], ["bp-lines", 430], ["bp-points", 440], ["bp-labels", 450]] as const) {
    map.createPane(name).style.zIndex = String(z);
  }
  map.getPane("bp-labels")!.style.pointerEvents = "none";
  pointRenderer = Lf.canvas({ pane: "bp-points", padding: 0.5 });
  Lf.control.scale({ position: "bottomleft", imperial: false, maxWidth: 120 }).addTo(map);
  map.on("zoomend", updateLabelVisibility);
  map.on("click", (event) => {
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
  map?.remove();
  map = null;
  overlayLayers.clear();
});

watch(() => props.blocks, () => renderBlocks(true));
watch(() => props.selectedId, (id, previous) => {
  const pan = panOnSelect && !!id;
  panOnSelect = true;
  renderSelected(pan);
  if (!id && previous) fitVisibleBlocks();
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
watch(() => props.budgetColors, () => renderSelected(), { deep: true });
watch(() => props.basemap, applyBasemap);
watch(() => props.insets, applyInsets, { deep: true });
</script>

<template>
  <div ref="container" class="bp-map h-full w-full" />
</template>

<style>
.bp-map { background: #3f4a3a; }
.bp-map .leaflet-bp-blocks-pane path { pointer-events: all !important; }

.bp-block-label {
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.75), 0 0 6px rgba(0, 0, 0, 0.35);
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
.bp-popup-wrap .leaflet-popup-content { margin: 0; width: 280px !important; max-height: 70vh; overflow: auto; }
.bp-popup { padding: 12px 12px 10px; color: #1f2937; }
.bp-popup .bp-popup-title { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding-right: 16px; font-size: 13px; font-weight: 700; color: #111827; }
.bp-popup .bp-dot { width: 10px; height: 10px; border-radius: 9999px; flex-shrink: 0; }
.bp-popup .bp-period { margin-left: auto; font-size: 11px; font-weight: 500; color: #6b7280; }
.bp-popup .bp-detail-row { display: grid; grid-template-columns: 108px 10px minmax(0, 1fr); gap: 0; align-items: start; font-size: 12px; line-height: 1.45; }
.bp-popup .bp-detail-row span:first-child,
.bp-popup .bp-detail-row span:nth-child(2) { color: #6b7280; }
.bp-popup .bp-detail-row span:last-child { color: #111827; font-weight: 600; word-break: break-word; }
.bp-popup .bp-empty { margin: 0; font-size: 12px; color: #6b7280; }

.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-content-wrapper { border-radius: 10px; padding: 0; overflow: hidden; }
.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-content { margin: 0; width: 320px !important; max-height: 72vh; overflow: auto; }
.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-tip { background: #fff; }

@keyframes map-blok-skeleton-shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
