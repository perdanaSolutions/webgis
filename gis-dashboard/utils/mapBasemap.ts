import type { BasemapOption, BasemapTile } from "~/utils/mapLayers";

type LeafletNs = typeof import("leaflet");

export type BasemapStatus = "checking" | "blocked" | "ready" | "unavailable";

const REACHABILITY_TIMEOUT_MS = 8000;
const TILE_TIMEOUT_MS = 7000;
export const WMS_TILE_TIMEOUT_MS = 20000;

function wmsTile(option: BasemapOption) {
  return option.tiles.find((tile) => tile.service === "wms") ?? null;
}

export type FotoUdaraStatus = {
  configured?: boolean;
  ok?: boolean;
  reason?: string | null;
  message?: string | null;
  layers?: string[];
  bbox?: [number, number, number, number] | null;
};

/** Hasil cek terakhir (status backend) dan alasan gagal ubin terakhir, dipakai isi dialog. */
let lastStatus: FotoUdaraStatus | null = null;
let lastTileProblem: { reason: string; message: string } | null = null;

export function resetBasemapDiagnostics() {
  lastStatus = null;
  lastTileProblem = null;
}

export function setBasemapDiagnostics(status: FotoUdaraStatus | null, tile?: { reason: string; message: string } | null) {
  lastStatus = status;
  if (tile !== undefined) lastTileProblem = tile;
}

function isProxied(tile: BasemapTile | null | undefined) {
  return Boolean(tile?.proxy);
}

function apiClient(): ((url: string, opts?: Record<string, unknown>) => Promise<any>) | null {
  try {
    return (useNuxtApp() as any).$api ?? null;
  } catch {
    return null;
  }
}

export function basemapHost(option: BasemapOption) {
  const tile = wmsTile(option);
  if (!tile) return "";
  if (tile.upstreamHost) return tile.upstreamHost;
  try {
    return new URL(tile.url).host;
  } catch {
    return tile.url;
  }
}

function basemapAccessToken() {
  try {
    const value = useRuntimeConfig().public.tokenBaseMap;
    return typeof value === "string" ? value.trim() : "";
  } catch {
    return "";
  }
}

/** Menempelkan token akses ke URL WMS tanpa menyimpan rahasia di kode. */
export function basemapServiceUrl(tile: BasemapTile, token = basemapAccessToken()) {
  if (!tile.tokenParam || !token) return tile.url;
  try {
    const url = new URL(tile.url);
    url.searchParams.set(tile.tokenParam, token);
    return url.toString();
  } catch {
    return tile.url;
  }
}

export function basemapCapabilitiesUrl(tile: BasemapTile, token = basemapAccessToken()) {
  try {
    const url = new URL(basemapServiceUrl(tile, token));
    url.searchParams.set("service", "WMS");
    url.searchParams.set("version", tile.version || "1.1.1");
    url.searchParams.set("request", "GetCapabilities");
    return url.toString();
  } catch {
    return tile.url;
  }
}

/** `true` bila host menjawab. Gagal koneksi, timeout, atau blokir jaringan mengembalikan `false`. */
export async function probeWmsReachable(option: BasemapOption) {
  const tile = wmsTile(option);
  if (!tile) return true;
  lastTileProblem = null;
  if (isProxied(tile)) {
    // Lewat backend: cek konfigurasi token, layer, dan cakupan sekaligus (tanpa membuka token ke browser).
    const api = apiClient();
    if (!api) return true;
    try {
      lastStatus = await api(tile.url.replace(/\/wms$/, "/status"), { skipServerErrorRedirect: true, timeout: REACHABILITY_TIMEOUT_MS });
      return true;
    } catch {
      lastStatus = null;
      return false;
    }
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REACHABILITY_TIMEOUT_MS);
  try {
    await fetch(basemapCapabilitiesUrl(tile), {
      mode: "no-cors",
      cache: "no-store",
      signal: controller.signal,
    });
    return true;
  } catch (error) {
    const name = error && typeof error === "object" && "name" in error ? String(error.name) : "";
    // Capabilities yang lambat tetap dilanjutkan ke permintaan ubin.
    return name === "AbortError";
  } finally {
    clearTimeout(timer);
  }
}

function coverageText(bbox: FotoUdaraStatus["bbox"]) {
  if (!bbox) return "";
  const f = (v: number) => v.toLocaleString("id-ID", { maximumFractionDigits: 2 });
  return ` Cakupan foto udara: bujur ${f(bbox[0])}–${f(bbox[2])}, lintang ${f(bbox[1])}–${f(bbox[3])}.`;
}

/** Alasan gagal yang bisa dibaca: token ditolak (401), layer tidak ada, belum dikonfigurasi, di luar cakupan. */
export function fotoUdaraProblem(status: FotoUdaraStatus | null, tile: { reason: string; message: string } | null, layer: string) {
  const reason = tile?.reason ?? (status && status.ok === false ? status.reason : null) ?? null;
  switch (reason) {
    case "unauthorized":
      return "Server foto udara menolak token akses (HTTP 401). Token salah, kedaluwarsa, atau belum diisi di backend (FOTO_UDARA_WMS_TOKEN).";
    case "not_configured":
      return "Token foto udara belum diisi di backend (FOTO_UDARA_WMS_URL / FOTO_UDARA_WMS_TOKEN).";
    case "layer_not_found":
      return `Layer ${layer} tidak ada di GeoServer. ${tile?.message ?? status?.message ?? ""}`.trim();
    case "unreachable":
      return "Server foto udara tidak terjangkau dari backend.";
    case "upstream_error":
    case "bad_request":
      return tile?.message ?? status?.message ?? "Server foto udara mengirim jawaban yang bukan gambar.";
    default:
      return null;
  }
}

export function basemapAccessMessage(kind: "blocked" | "unavailable", option: BasemapOption) {
  const host = basemapHost(option);
  const layer = wmsTile(option)?.layers || "belum diisi";
  if (kind === "unavailable" && isProxied(wmsTile(option))) {
    const problem = fotoUdaraProblem(lastStatus, lastTileProblem, layer);
    return {
      title: "Foto udara belum tampil",
      body: problem
        ? `${option.label} (${host}): ${problem}`
        : `Server ${option.label} (${host}) menjawab, tetapi tidak ada citra di area ini. Geser peta ke area cakupan foto udara.${coverageText(lastStatus?.bbox ?? null)}`,
    };
  }
  if (kind === "blocked") {
    return {
      title: "Foto udara tidak dapat dimuat",
      body: `Jaringan ini tidak mengizinkan akses ke server foto udara ${option.label} (${host}). Setelah akses dibuka, pilih lagi ${option.label}.`,
    };
  }
  return {
    title: "Foto udara belum tampil",
    body: `Server ${option.label} (${host}) terjangkau, tetapi citra tidak dapat digambar. Nama layer yang diminta: ${layer}. Periksa nama layer di GeoServer, atau geser peta ke area cakupan foto udara.`,
  };
}

export function createBasemapTileLayer(
  leaflet: LeafletNs,
  tile: BasemapTile,
  extra?: { crossOrigin?: boolean | string; updateWhenZooming?: boolean },
) {
  const crossOrigin = extra?.crossOrigin;
  const tilePerf = extra?.updateWhenZooming === false ? { updateWhenZooming: false } : {};
  if (tile.service === "wms" && isProxied(tile)) {
    return createProxiedWmsLayer(leaflet, tile, tilePerf);
  }
  if (tile.service === "wms") {
    const factory = leaflet.tileLayer as typeof leaflet.tileLayer & {
      wms: (url: string, options: Record<string, unknown>) => import("leaflet").TileLayer;
    };
    return factory.wms(basemapServiceUrl(tile), {
      layers: tile.layers ?? "",
      styles: "",
      format: tile.format ?? "image/png",
      transparent: tile.transparent ?? false,
      version: tile.version ?? "1.1.1",
      attribution: tile.attribution,
      maxZoom: tile.maxZoom ?? 22,
      uppercase: true,
      ...tilePerf,
      ...(crossOrigin ? { crossOrigin } : {}),
    });
  }
  return leaflet.tileLayer(tile.url, {
    attribution: tile.attribution,
    maxZoom: tile.maxZoom ?? 19,
    ...tilePerf,
    ...(tile.subdomains ? { subdomains: tile.subdomains } : {}),
    ...(crossOrigin ? { crossOrigin } : {}),
  });
}

/**
 * WMS lewat proxy backend: <img> tidak bisa membawa header Authorization, jadi ubin diambil dengan $api
 * (JWT user) sebagai blob lalu dipasang sebagai object URL. Alasan gagal (JSON {reason}) disimpan untuk dialog.
 */
function createProxiedWmsLayer(leaflet: LeafletNs, tile: BasemapTile, tilePerf: Record<string, unknown>) {
  const Wms = (leaflet.TileLayer as any).WMS;
  const Proxied = Wms.extend({
    createTile(coords: any, done: (err: unknown, tile: HTMLElement) => void) {
      const img = document.createElement("img");
      img.alt = "";
      img.setAttribute("role", "presentation");
      const api = apiClient();
      const url = this.getTileUrl(coords);
      if (!api) {
        queueMicrotask(() => done(new Error("api tidak tersedia"), img));
        return img;
      }
      api(url, { responseType: "blob", skipServerErrorRedirect: true, headers: { accept: "image/*" } })
        .then((blob: Blob) => {
          const objectUrl = URL.createObjectURL(blob);
          img.onload = () => { URL.revokeObjectURL(objectUrl); done(null, img); };
          img.onerror = () => { URL.revokeObjectURL(objectUrl); done(new Error("gambar rusak"), img); };
          img.src = objectUrl;
        })
        .catch((error: any) => {
          const data = error?.data ?? error?.response?._data;
          if (data && typeof data === "object" && data.reason) {
            lastTileProblem = { reason: String(data.reason), message: String(data.message ?? "") };
          }
          done(error, img);
        });
      return img;
    },
  });
  return new Proxied(tile.url, {
    layers: tile.layers ?? "",
    styles: "",
    format: tile.format ?? "image/png",
    transparent: tile.transparent ?? false,
    version: tile.version ?? "1.1.1",
    attribution: tile.attribution,
    maxZoom: tile.maxZoom ?? 22,
    uppercase: true,
    ...tilePerf,
  }) as import("leaflet").TileLayer;
}

export function applyBasemapZoom(map: import("leaflet").Map, option: BasemapOption) {
  const maxZoom = Math.max(...option.tiles.map((tile) => tile.maxZoom ?? 19));
  map.setMaxZoom(maxZoom);
  if (map.getZoom() > maxZoom) map.setZoom(maxZoom);
}

/** Memanggil `onFailed` bila tidak ada ubin yang berhasil dimuat. */
export function observeBasemapTiles(
  layers: import("leaflet").TileLayer[],
  onFailed: () => void,
  timeoutMs = TILE_TIMEOUT_MS,
) {
  let loaded = 0;
  let errors = 0;
  let settled = false;
  const finish = (failed: boolean) => {
    if (settled) return;
    settled = true;
    window.clearTimeout(timer);
    if (failed) onFailed();
  };
  const timer = window.setTimeout(() => finish(loaded === 0), timeoutMs);
  for (const layer of layers) {
    layer.on("tileload", () => {
      loaded += 1;
      finish(false);
    });
    layer.on("tileerror", () => {
      errors += 1;
      if (loaded === 0 && errors >= 3) finish(true);
    });
  }
  return () => finish(false);
}
