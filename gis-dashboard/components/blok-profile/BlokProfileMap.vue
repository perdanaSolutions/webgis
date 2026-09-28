<script setup lang="ts">
import { onBeforeUnmount, onMounted, shallowRef, watch } from "vue";
import "leaflet/dist/leaflet.css";

import type { OverlayLayer } from "~/composables/useMapOverlays";
import type { BlockCollection } from "~/stores/blokProfileStore";
import { BASEMAPS, type BasemapKey, getOverlayColor } from "~/utils/mapLayers";

type Insets = { top: number; right: number; bottom: number; left: number };
type L = typeof import("leaflet");

const props = defineProps<{
  blocks: BlockCollection | null;
  selectedId: string;
  showBlocks: boolean;
  overlays: OverlayLayer[];
  basemap: BasemapKey;
  opacity: number; // 0..1
  insets: Insets;
}>();

const emit = defineEmits<{ (e: "select", blokId: string): void }>();

const container = shallowRef<HTMLElement | null>(null);
let Lf: L | null = null;
let map: import("leaflet").Map | null = null;
let basemapLayers: import("leaflet").TileLayer[] = [];
let blockLayer: import("leaflet").GeoJSON | null = null;
let labelLayer: import("leaflet").LayerGroup | null = null;
let selectedTag: import("leaflet").Marker | null = null;
let pointRenderer: import("leaflet").Canvas | null = null;
const overlayLayers = new Map<string, import("leaflet").GeoJSON>();

const LABEL_MIN_ZOOM = 14;

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

// ------------------------------------------------------------------ basemap
function applyBasemap() {
  if (!Lf || !map) return;
  const option = BASEMAPS.find((b) => b.key === props.basemap) ?? BASEMAPS[0]!;
  basemapLayers.forEach((layer) => layer.removeFrom(map!));
  basemapLayers = option.tiles.map((tile) => Lf!.tileLayer(tile.url, {
    attribution: tile.attribution, maxZoom: tile.maxZoom ?? 19, ...(tile.subdomains ? { subdomains: tile.subdomains } : {}),
  }).addTo(map!));
}

// ------------------------------------------------------------------ batas blok
function blockStyle(id: string) {
  const selected = id === props.selectedId;
  return {
    pane: "bp-blocks",
    color: "#ffffff",
    weight: selected ? 3.5 : 1.2,
    opacity: selected ? 1 : 0.85,
    fillColor: "#ffffff",
    fillOpacity: selected ? 0.06 * props.opacity : 0.02,
  };
}

function renderBlocks(fit: boolean) {
  if (!Lf || !map) return;
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
    style: (f) => blockStyle(String(f?.properties?.blok_id ?? "")),
    onEachFeature: (feature, layer) => {
      const id = String(feature.properties?.blok_id ?? "");
      layer.on("click", () => emit("select", id));
      layer.on("mouseover", () => (layer as any).setStyle?.({ weight: id === props.selectedId ? 3.5 : 2.4, opacity: 1 }));
      layer.on("mouseout", () => (layer as any).setStyle?.(blockStyle(id)));
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
  if (fit) {
    const bounds = blockLayer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { ...padding(), maxZoom: 16 });
  }
  renderSelected();
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
    (layer as any).setStyle?.(blockStyle(id));
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

function overlayPopup(layer: OverlayLayer, p: Record<string, any>) {
  const fields = layer.style.popupFields.length
    ? layer.style.popupFields
    : Object.keys(p).filter((k) => !["id", "blok_id", "bulan", "tahun"].includes(k) && typeof p[k] !== "object").map((k) => [k, k] as [string, string]);
  const rows = fields.filter(([k]) => p[k] !== null && p[k] !== undefined && p[k] !== "")
    .map(([k, label]) => `<tr><td class="bp-k">${escapeHtml(label)}</td><td class="bp-v">${escapeHtml(typeof p[k] === "number" ? fmt(p[k], 2) : p[k])}</td></tr>`).join("");
  const period = p.bulan && p.tahun ? `<span class="bp-period">${p.bulan}-${p.tahun}</span>` : "";
  return `<div class="bp-popup"><div class="bp-popup-title">${escapeHtml(layer.name)}${period}</div><table>${rows}</table></div>`;
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
      }),
      onEachFeature: (f, l) => l.bindPopup(() => overlayPopup(layer, (f.properties ?? {}) as Record<string, any>), {
        className: "bp-popup-wrap", maxWidth: 260,
        autoPanPaddingTopLeft: [props.insets.left + 24, props.insets.top + 24],
        autoPanPaddingBottomRight: [props.insets.right + 24, props.insets.bottom + 24],
      }),
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
  if (br) br.style.marginRight = `${props.insets.right}px`;
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
  applyBasemap();
  setTimeout(applyInsets, 0);
  renderBlocks(true);
  renderOverlays();
});

onBeforeUnmount(() => {
  map?.remove();
  map = null;
  overlayLayers.clear();
});

watch(() => props.blocks, () => renderBlocks(true));
watch(() => props.selectedId, () => renderSelected(true));
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
watch(() => props.basemap, applyBasemap);
watch(() => props.insets, applyInsets, { deep: true });
</script>

<template>
  <div ref="container" class="bp-map h-full w-full" />
</template>

<style>
.bp-map { background: #3f4a3a; }

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
  background: rgba(58, 38, 22, 0.92);
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
  border-top: 3px solid #6b5a48;
  background: rgba(255, 253, 249, 0.92);
  color: #4a3a2c;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px 2px;
  border-radius: 9999px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
}

.bp-popup-wrap .leaflet-popup-content-wrapper { border-radius: 12px; }
.bp-popup-wrap .leaflet-popup-content { margin: 10px 12px; font-size: 12px; }
.bp-popup .bp-popup-title { display: flex; gap: 8px; margin-bottom: 6px; padding-right: 16px; font-size: 13px; font-weight: 700; color: #2b2118; }
.bp-popup .bp-period { margin-left: auto; font-weight: 500; color: #8a7a68; }
.bp-popup table { width: 100%; border-collapse: collapse; }
.bp-popup td { padding: 2px 0; vertical-align: top; }
.bp-popup .bp-k { color: #8a7a68; padding-right: 10px; white-space: nowrap; }
.bp-popup .bp-v { color: #2b2118; font-weight: 600; text-align: right; }
</style>
