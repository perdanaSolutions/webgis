import type { BasemapOption, BasemapTile } from "~/utils/mapLayers";

type LeafletNs = typeof import("leaflet");

export type BasemapStatus = "checking" | "blocked" | "ready" | "unavailable";

const REACHABILITY_TIMEOUT_MS = 8000;
const TILE_TIMEOUT_MS = 7000;
export const WMS_TILE_TIMEOUT_MS = 20000;

function wmsTile(option: BasemapOption) {
  return option.tiles.find((tile) => tile.service === "wms") ?? null;
}

export function basemapHost(option: BasemapOption) {
  const tile = wmsTile(option);
  if (!tile) return "";
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

export function basemapAccessMessage(kind: "blocked" | "unavailable", option: BasemapOption) {
  const host = basemapHost(option);
  const layer = wmsTile(option)?.layers || "belum diisi";
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
