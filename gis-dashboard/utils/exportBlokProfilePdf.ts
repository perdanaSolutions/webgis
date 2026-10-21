import { createBasemapTileLayer } from "~/utils/mapBasemap";
import type { BasemapKey } from "~/utils/mapLayers";
import {
  BASEMAPS,
  BUDGET_GAP_COLOR,
  getOverlayColor,
  readBudgetCategory,
  readComparisonBudgetCategory,
  type OverlayStyle,
  type LegendItem,
} from "~/utils/mapLayers";
import { buildPdfLegend, pdfFileName, plainAttribution, rgbOf, type PdfSwatch } from "~/utils/blokProfilePdf";

export type PdfOverlay = {
  code: string;
  name: string;
  geometryType: string;
  style: OverlayStyle;
  legend: LegendItem[];
  data: GeoJSON.FeatureCollection;
};

export type PdfExportInput = {
  scopeLabel: string;
  filterLine: string;
  printedAt: string;
  basemap: BasemapKey;
  showBlocks: boolean;
  showYieldGap: boolean;
  budgetColors: Record<string, boolean>;
  selectedId: string;
  blocks: GeoJSON.FeatureCollection | null;
  overlays: PdfOverlay[];
  sections: HTMLElement[];
  onStatus?: (message: string) => void;
};

type Leaflet = typeof import("leaflet");
type Shot = { image: HTMLImageElement };

const PAGE_W = 297;
const PAGE_H = 210;
const MARGIN = 10;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function escapeHtml(value: unknown) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
}

function geometryKind(type: string) {
  const text = type.toUpperCase();
  if (text.includes("POINT")) return "point";
  if (text.includes("LINE")) return "line";
  return "polygon";
}

function legendFrame(count: number) {
  const columns = count > 8 ? 4 : 3;
  const rows = count ? Math.ceil(count / columns) : 0;
  const legendH = rows * 6;
  const mapY = MARGIN + 19;
  const footerTop = PAGE_H - 8;
  const mapH = Math.max(70, footerTop - mapY - (legendH ? legendH + 2 : 0));
  return { columns, legendH, mapY, mapH, mapW: PAGE_W - MARGIN * 2, footerTop };
}

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Gambar PDF gagal dimuat"));
    image.src = src;
  });
}

async function captureSections(sections: HTMLElement[]) {
  const { toPng } = await import("html-to-image");
  const shots: Shot[] = [];
  for (const section of sections) {
    const width = Math.ceil(section.scrollWidth);
    const height = Math.ceil(section.scrollHeight);
    if (width < 2 || height < 2) continue;
    const dataUrl = await toPng(section, {
      pixelRatio: height > 5000 ? 1.25 : 2,
      backgroundColor: "#f4f6f1",
      width,
      height,
    });
    shots.push({ image: await loadImage(dataUrl) });
  }
  return shots;
}

function layerHasTiles(layer: import("leaflet").TileLayer) {
  const images = layer.getContainer()?.querySelectorAll("img") ?? [];
  return [...images].some((image) => image.complete && image.naturalWidth > 0);
}

async function settleTiles(layers: import("leaflet").TileLayer[]) {
  const pending = layers.filter((layer) => !layerHasTiles(layer));
  if (!pending.length) {
    await sleep(80);
    return;
  }
  await Promise.all(pending.map((layer) => new Promise<void>((resolve) => {
    const timer = window.setTimeout(resolve, 8000);
    layer.once("load", () => {
      window.clearTimeout(timer);
      resolve();
    });
  })));
  await sleep(160);
}

async function renderPrintMap(Lf: Leaflet, input: PdfExportInput, mapH: number, mapW: number) {
  const { toPng } = await import("html-to-image");
  const cssW = 1500;
  const cssH = Math.max(520, Math.round(cssW * (mapH / mapW)));
  const option = BASEMAPS.find((item) => item.key === input.basemap) ?? BASEMAPS[0]!;
  const satellite = input.basemap === "satellite" || input.basemap === "hybrid" || input.basemap === "tpa-sga";
  const background = satellite ? "#243028" : "#e7efe0";
  const host = document.createElement("div");
  host.className = "bp-map bp-print-map";
  host.setAttribute("aria-hidden", "true");
  host.style.cssText = `position:fixed;left:0;top:0;width:${cssW}px;height:${cssH}px;z-index:4400;pointer-events:none;background:${background};`;
  document.body.appendChild(host);

  const map = Lf.map(host, {
    zoomControl: false,
    attributionControl: false,
    fadeAnimation: false,
    zoomAnimation: false,
  }).setView([0.5, 117.5], 6);
  for (const [name, z] of [["bp-polygons", 410], ["bp-blocks", 430], ["bp-lines", 440], ["bp-points", 450], ["bp-labels", 460]] as const) {
    map.createPane(name).style.zIndex = String(z);
  }
  map.getPane("bp-labels")!.style.pointerEvents = "none";
  const pointRenderer = Lf.canvas({ pane: "bp-points", padding: 0.5 });
  Lf.control.scale({ imperial: false, position: "bottomleft", maxWidth: 120 }).addTo(map);

  const north = document.createElement("div");
  north.className = "bp-print-north";
  north.innerHTML = "<span>U</span>";
  host.appendChild(north);

  const basemapLayers = option.tiles.map((tile) => createBasemapTileLayer(Lf, tile, {
    crossOrigin: "anonymous",
  }).addTo(map));

  const drawn: import("leaflet").Layer[] = [];
  function track<T extends import("leaflet").Layer>(layer: T) {
    drawn.push(layer);
    return layer;
  }

  for (const overlay of input.overlays) {
    const kind = geometryKind(overlay.geometryType);
    if (!overlay.data.features?.length) continue;
    if (kind === "line") {
      track(Lf.geoJSON(overlay.data, {
        pane: "bp-lines",
        interactive: false,
        style: () => ({ color: "#ffffff", weight: (overlay.style.weight ?? 3) + 3.2, opacity: 0.95 }),
      }).addTo(map));
      track(Lf.geoJSON(overlay.data, {
        pane: "bp-lines",
        interactive: false,
        style: (feature) => ({
          color: getOverlayColor(overlay.style, feature?.properties as Record<string, unknown> | null),
          weight: Math.max(overlay.style.weight ?? 3, 2.4),
          opacity: 1,
        }),
      }).addTo(map));
      continue;
    }
    if (kind === "point") {
      track(Lf.geoJSON(overlay.data, {
        pane: "bp-points",
        interactive: false,
        pointToLayer: (feature, latlng) => Lf.circleMarker(latlng, {
          renderer: pointRenderer,
          pane: "bp-points",
          radius: Math.max(overlay.style.radius ?? 5, 4),
          color: overlay.code === "sawit" ? "#1f2937" : "#ffffff",
          weight: overlay.code === "sawit" ? 0.6 : 1.4,
          opacity: 1,
          fillColor: getOverlayColor(overlay.style, feature.properties as Record<string, unknown> | null),
          fillOpacity: 1,
          interactive: false,
        }),
      }).addTo(map));
      continue;
    }
    const polygons = track(Lf.geoJSON(overlay.data, {
      pane: "bp-polygons",
      interactive: false,
      style: (feature) => ({
        color: "#ffffff",
        weight: Math.max(overlay.style.weight ?? 1, 1.15),
        opacity: 1,
        fillColor: getOverlayColor(overlay.style, feature?.properties as Record<string, unknown> | null),
        fillOpacity: Math.max(overlay.style.fillOpacity ?? 0.55, 0.72),
      }),
    }).addTo(map));
    if (overlay.code === "slope") addSlopeLabels(Lf, map, polygons);
  }

  const blockFeatures = input.showBlocks ? input.blocks?.features ?? [] : [];
  let blockLayer: import("leaflet").GeoJSON | null = null;
  if (blockFeatures.length && input.blocks) {
    const paint = (feature?: GeoJSON.Feature | null) => blockPaint(feature?.properties, input);
    track(Lf.geoJSON(input.blocks, {
      pane: "bp-blocks",
      interactive: false,
      style: () => ({ color: "#1a2416", weight: 6.4, opacity: 0.92, fill: false }),
    }).addTo(map));
    blockLayer = track(Lf.geoJSON(input.blocks, {
      pane: "bp-blocks",
      interactive: false,
      style: (feature) => paint(feature ?? undefined),
    }).addTo(map));
    if (blockFeatures.length <= 80) addBlockLabels(Lf, map, blockLayer, input);
    addSelectedTag(Lf, map, blockLayer, input.selectedId);
  }

  const bounds = Lf.latLngBounds([]);
  for (const layer of drawn) {
    const layerBounds = (layer as import("leaflet").GeoJSON).getBounds?.();
    if (layerBounds?.isValid()) bounds.extend(layerBounds);
  }

  let basemapDrawn = true;
  try {
    map.invalidateSize();
    if (bounds.isValid()) {
      const moved = new Promise<void>((resolve) => map.once("moveend", () => resolve()));
      map.fitBounds(bounds, { padding: [42, 54], maxZoom: 16 });
      await Promise.race([moved, sleep(1500)]);
    } else {
      const note = document.createElement("div");
      note.className = "bp-print-empty";
      note.textContent = "Belum ada batas blok atau layer aktif pada scope ini.";
      host.appendChild(note);
    }
    await settleTiles(basemapLayers);
    const shoot = () => toPng(host, {
      pixelRatio: 2,
      backgroundColor: background,
      width: cssW,
      height: cssH,
    });
    try {
      return { dataUrl: await shoot(), basemapDrawn };
    } catch {
      basemapDrawn = false;
      basemapLayers.forEach((layer) => layer.remove());
      host.style.background = "#e7efe0";
      await sleep(40);
      return { dataUrl: await shoot(), basemapDrawn };
    }
  } finally {
    map.remove();
    host.remove();
  }
}

function blockPaint(properties: GeoJSON.GeoJsonProperties | null | undefined, input: PdfExportInput): import("leaflet").PathOptions {
  const selected = String(properties?.blok_id ?? "") === input.selectedId && !!input.selectedId;
  let fill: string | null = null;
  if (input.showYieldGap) {
    const category = readBudgetCategory(properties as Record<string, any> | null);
    if (category && input.budgetColors[category] !== false) fill = BUDGET_GAP_COLOR[category] ?? null;
  }
  if (!fill) {
    return { color: selected ? "#ffffff" : "#f7f7f7", weight: selected ? 4.2 : 3, opacity: 1, fill: false };
  }
  return {
    color: "#ffffff",
    weight: selected ? 4 : 2.2,
    opacity: 1,
    fill: true,
    fillColor: fill,
    fillOpacity: 0.8,
  };
}

function addBlockLabels(
  Lf: Leaflet,
  map: import("leaflet").Map,
  blocks: import("leaflet").GeoJSON,
  input: PdfExportInput,
) {
  const labels = Lf.layerGroup();
  const markers = Lf.layerGroup();
  blocks.eachLayer((layer) => {
    const feature = (layer as import("leaflet").GeoJSON & { feature?: GeoJSON.Feature }).feature;
    const bounds = (layer as { getBounds?: () => import("leaflet").LatLngBounds }).getBounds?.();
    if (!bounds?.isValid()) return;
    const properties = feature?.properties as Record<string, any> | null | undefined;
    const category = input.showYieldGap ? readComparisonBudgetCategory(properties) : "";
    const compared = Boolean(category);
    const color = category && input.budgetColors[category] !== false ? BUDGET_GAP_COLOR[category] ?? null : null;
    let center = bounds.getCenter();
    try {
      center = (layer as { getCenter?: () => import("leaflet").LatLng }).getCenter?.() ?? center;
    } catch {
      /* Pusat poligon belum siap. */
    }
    const kode = escapeHtml(feature?.properties?.kode_blok);
    if (color) {
      Lf.circleMarker(center, {
        pane: "bp-labels",
        radius: 7,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillColor: color,
        fillOpacity: 1,
        interactive: false,
      }).addTo(markers);
    }
    if (compared) {
      Lf.marker(center, {
        pane: "bp-labels",
        interactive: false,
        icon: Lf.divIcon({
          className: "bp-block-label",
          html: `<span class="bp-block-label-text ${color ? "is-below" : "is-center"}">${kode}</span>`,
          iconSize: [0, 0],
        }),
      }).addTo(labels);
      return;
    }
    Lf.marker(bounds.getNorthWest(), {
      pane: "bp-labels",
      interactive: false,
      icon: Lf.divIcon({
        className: "bp-block-label",
        html: kode,
        iconAnchor: [-8, -8],
      }),
    }).addTo(labels);
  });
  markers.addTo(map);
  labels.addTo(map);
}

function addSelectedTag(Lf: Leaflet, map: import("leaflet").Map, blocks: import("leaflet").GeoJSON, selectedId: string) {
  if (!selectedId) return;
  blocks.eachLayer((layer) => {
    const feature = (layer as { feature?: GeoJSON.Feature }).feature;
    if (String(feature?.properties?.blok_id ?? "") !== selectedId) return;
    const bounds = (layer as { getBounds?: () => import("leaflet").LatLngBounds }).getBounds?.();
    if (!bounds?.isValid()) return;
    (layer as { bringToFront?: () => void }).bringToFront?.();
    const luas = feature?.properties?.areal_statement?.luas_tanam;
    const luasText = Number.isFinite(Number(luas)) && Number(luas) !== 0
      ? ` · ${Number(luas).toLocaleString("id-ID", { maximumFractionDigits: 1 })} Ha`
      : "";
    Lf.marker(bounds.getCenter(), {
      pane: "bp-labels",
      interactive: false,
      icon: Lf.divIcon({
        className: "bp-selected-tag",
        html: `<div class="bp-tag-inner"><span class="bp-pin" aria-hidden="true"></span>${escapeHtml(feature?.properties?.kode_blok)}${escapeHtml(luasText)}</div>`,
        iconSize: [0, 0],
      }),
    }).addTo(map);
  });
}

function addSlopeLabels(Lf: Leaflet, map: import("leaflet").Map, geo: import("leaflet").GeoJSON) {
  const groups = new Map<string, { kode: string; kelas: Set<string>; lat: number; lng: number; n: number }>();
  geo.eachLayer((layer) => {
    const feature = (layer as { feature?: GeoJSON.Feature }).feature;
    const properties = (feature?.properties ?? {}) as Record<string, any>;
    const kode = String(properties.kode_blok ?? "").trim();
    const id = String(properties.blok_id ?? kode);
    const bounds = (layer as { getBounds?: () => import("leaflet").LatLngBounds }).getBounds?.();
    if (!bounds?.isValid()) return;
    const center = bounds.getCenter();
    const current = groups.get(id) ?? { kode, kelas: new Set<string>(), lat: 0, lng: 0, n: 0 };
    current.n += 1;
    current.lat += center.lat;
    current.lng += center.lng;
    const kelas = String(properties.kelerengan ?? "").trim().replace(/%/g, "");
    if (kelas) current.kelas.add(kelas);
    groups.set(id, current);
  });
  if (!groups.size || groups.size > 60) return;
  const labels = Lf.layerGroup();
  groups.forEach((group) => {
    const kelas = group.kelas.size === 1 ? `${[...group.kelas][0]}%` : "";
    const title = ["Slope", group.kode, kelas].filter(Boolean).join(" · ");
    Lf.marker([group.lat / group.n, group.lng / group.n], {
      pane: "bp-labels",
      interactive: false,
      icon: Lf.divIcon({
        className: "bp-slope-label",
        html: `<div class="bp-slope-pill">${escapeHtml(title)}</div>`,
        iconSize: [0, 0],
      }),
    }).addTo(labels);
  });
  labels.addTo(map);
}

function drawLegend(pdf: import("jspdf").jsPDF, swatches: PdfSwatch[], x: number, y: number, width: number, columns: number) {
  if (!swatches.length) return;
  const colW = width / columns;
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  swatches.forEach((swatch, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const left = x + column * colW;
    const top = y + row * 6;
    const [red, green, blue] = rgbOf(swatch.color);
    pdf.setFillColor(red, green, blue);
    pdf.setDrawColor(31, 42, 24);
    pdf.setLineWidth(0.15);
    pdf.rect(left, top, 3.2, 3.2, "FD");
    pdf.setTextColor(31, 42, 24);
    const label = pdf.splitTextToSize(swatch.label, colW - 6)[0] ?? swatch.label;
    pdf.text(String(label), left + 4.4, top + 2.6);
  });
}

/** Satu kartu = satu halaman. Gambar diperkecil utuh bila lebih tinggi dari kertas, tidak dipotong. */
function placeCardPages(pdf: import("jspdf").jsPDF, shots: Shot[], input: PdfExportInput) {
  const bottom = PAGE_H - 12;
  const maxW = PAGE_W - MARGIN * 2;
  const headerBottom = MARGIN + 14;
  const maxH = bottom - headerBottom;
  for (const shot of shots) {
    pdf.addPage("a4", "landscape");
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(31, 42, 24);
    const title = pdf.splitTextToSize(input.scopeLabel || "Blok Profile", maxW - 28)[0] ?? "";
    pdf.text(String(title), MARGIN, MARGIN + 4);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    pdf.setTextColor(85, 96, 76);
    const filter = pdf.splitTextToSize(input.filterLine, maxW)[0] ?? "";
    pdf.text(String(filter), MARGIN, MARGIN + 9);

    const aspect = shot.image.naturalWidth / shot.image.naturalHeight;
    let width = maxW;
    let height = width / aspect;
    if (height > maxH) {
      height = maxH;
      width = height * aspect;
    }
    const x = MARGIN + (maxW - width) / 2;
    pdf.addImage(shot.image, "PNG", x, headerBottom, width, height, undefined, "FAST");
  }
}

export async function exportBlokProfilePdf(input: PdfExportInput) {
  const swatches = buildPdfLegend({
    showBlocks: input.showBlocks,
    showYieldGap: input.showYieldGap,
    budgetColors: input.budgetColors,
    overlays: input.overlays,
  });
  const frame = legendFrame(swatches.length);
  input.onStatus?.("Menggambar peta dan informasi…");
  const Lf = await import("leaflet");
  const [mapShot, shots] = await Promise.all([
    renderPrintMap(Lf, input, frame.mapH, frame.mapW),
    captureSections(input.sections),
  ]);

  input.onStatus?.("Menyusun PDF…");
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4", compress: true });
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(15);
  pdf.setTextColor(31, 42, 24);
  const title = pdf.splitTextToSize(input.scopeLabel || "Blok Profile", 200).slice(0, 1);
  pdf.text(title, MARGIN, MARGIN + 5);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  pdf.setTextColor(110, 120, 102);
  pdf.text(input.printedAt, PAGE_W - MARGIN, MARGIN + 5, { align: "right" });
  pdf.setTextColor(85, 96, 76);
  const filter = pdf.splitTextToSize(input.filterLine, PAGE_W - MARGIN * 2).slice(0, 2);
  pdf.text(filter, MARGIN, MARGIN + 11);

  pdf.addImage(mapShot.dataUrl, "PNG", MARGIN, frame.mapY, frame.mapW, frame.mapH, undefined, "FAST");
  if (swatches.length) drawLegend(pdf, swatches, MARGIN, frame.mapY + frame.mapH + 2, frame.mapW, frame.columns);

  const option = BASEMAPS.find((item) => item.key === input.basemap) ?? BASEMAPS[0]!;
  const credit = option.tiles.map((tile) => plainAttribution(tile.attribution)).filter(Boolean).join(" · ");
  const footer = mapShot.basemapDrawn
    ? credit
    : "Basemap tidak dapat dicetak. Batas layer tetap digambar.";
  pdf.setFontSize(7);
  pdf.setTextColor(110, 120, 102);
  const footerLine = pdf.splitTextToSize(footer, PAGE_W - MARGIN * 2 - 24)[0] ?? "";
  if (footerLine) pdf.text(String(footerLine), MARGIN, frame.footerTop + 3);

  placeCardPages(pdf, shots, input);

  const total = pdf.getNumberOfPages();
  for (let page = 1; page <= total; page += 1) {
    pdf.setPage(page);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    pdf.setTextColor(110, 120, 102);
    pdf.text(`${page} / ${total}`, PAGE_W - MARGIN, PAGE_H - 5, { align: "right" });
  }

  input.onStatus?.("Mengunduh PDF…");
  pdf.save(pdfFileName(input.scopeLabel));
}
