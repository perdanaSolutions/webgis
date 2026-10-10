/**
 * Skema cache modul peta (`pages/map`).
 *
 * Versi ini harus sama dengan `MAP_CACHE_SCHEMA` di
 * `backend_fastapi/app/core/map_cache.py`. Naikkan keduanya bila bentuk JSON berubah.
 *
 * Redis (server): setiap GET di bawah `/api/v1/spatial` disimpan middleware.
 * Kunci = versi skema + id user dari JWT + path + query. Umur mengikuti
 * `REDIS_MAP_TTL_SECONDS`. Tulisan yang mengubah data peta menaikkan versi
 * Redis sehingga salinan lama tidak terpakai.
 *
 * PWA (perangkat): respons GET yang sama disimpan di Cache Storage, dipisah
 * per user, supaya halaman peta tetap bisa dibuka tanpa jaringan. Service
 * worker menyimpan dokumen `/map` dan ubin peta dasar.
 */

export const MAP_CACHE_SCHEMA = "1"

const PREFIX = `gis-map-pwa-v${MAP_CACHE_SCHEMA}`

/** Respons JSON API peta, per user. */
export const MAP_PWA_CACHE = `${PREFIX}-api`
/** Dokumen HTML `/map` agar rute bisa dibuka offline. */
export const MAP_PAGE_CACHE = `${PREFIX}-page`
/** Ubin basemap (OSM, Esri, OpenTopoMap). */
export const MAP_TILE_CACHE = `${PREFIX}-tiles`

export const MAP_PWA_CACHES = [MAP_PWA_CACHE, MAP_PAGE_CACHE, MAP_TILE_CACHE] as const

/** Salinan di perangkat bertahan lebih lama dari TTL Redis supaya kerja lapangan tetap jalan. */
export const MAP_PWA_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

/** Host ubin yang dipakai `BASEMAPS` di utils/mapLayers.ts. */
export const MAP_TILE_URL = /^https:\/\/([abc]\.tile\.openstreetmap\.org|server\.arcgisonline\.com|[abc]\.tile\.opentopomap\.org)\//

/** Dokumen halaman peta saja: `https://host/map`. */
export const MAP_PAGE_URL = /^https?:\/\/[^/?#]+\/map\/?(?:\?[^#]*)?$/

type Envelope<T> = { savedAt: number; data: T }

function cacheAvailable() {
  return typeof caches !== "undefined"
}

/** Path API baca peta: `/api/v1/spatial/...` (hierarki, GeoJSON, detail, histori, katalog, layer). */
export function isMapSpatialUrl(url: string) {
  try {
    const path = new URL(url, "http://localhost").pathname
    return path.includes("/spatial/") || path.endsWith("/spatial")
  } catch {
    return false
  }
}

/** Query diurutkan dan nilai kosong dibuang, sama seperti kunci Redis. */
export function normalizeMapUrl(url: string) {
  const parsed = new URL(url, "http://localhost")
  const pairs = [...parsed.searchParams.entries()].filter(([, value]) => value !== "")
  pairs.sort((a, b) => (a[0] === b[0] ? a[1].localeCompare(b[1]) : a[0].localeCompare(b[0])))
  const query = new URLSearchParams(pairs).toString()
  return `${parsed.origin}${parsed.pathname}${query ? `?${query}` : ""}`
}

function cacheRequest(userId: string, url: string) {
  const key = `${MAP_CACHE_SCHEMA}\n${userId}\n${normalizeMapUrl(url)}`
  return new Request(`https://map-cache.local/${encodeURIComponent(key)}`)
}

/** Buang salinan skema lama. Panggil sekali saat halaman peta dibuka. */
export async function installMapCacheSchema() {
  if (!cacheAvailable()) return
  const keys = await caches.keys()
  await Promise.all(
    keys
      .filter((name) => name.startsWith("gis-map-pwa-") && !MAP_PWA_CACHES.includes(name as (typeof MAP_PWA_CACHES)[number]))
      .map((name) => caches.delete(name)),
  )
}

export async function saveMapResponse(userId: string, url: string, data: unknown) {
  if (!cacheAvailable() || !userId || !isMapSpatialUrl(url)) return
  try {
    const cache = await caches.open(MAP_PWA_CACHE)
    const body = JSON.stringify({ savedAt: Date.now(), data } satisfies Envelope<unknown>)
    await cache.put(
      cacheRequest(userId, url),
      new Response(body, { headers: { "content-type": "application/json" } }),
    )
  } catch {
    /* kuota penuh atau penyimpanan ditolak */
  }
}

export async function readMapResponse<T>(userId: string, url: string): Promise<{ data: T } | null> {
  if (!cacheAvailable() || !userId || !isMapSpatialUrl(url)) return null
  try {
    const cache = await caches.open(MAP_PWA_CACHE)
    const request = cacheRequest(userId, url)
    const hit = await cache.match(request)
    if (!hit) return null
    const payload = await hit.json() as Envelope<T>
    if (!payload || typeof payload.savedAt !== "number" || !("data" in payload)) return null
    if (Date.now() - payload.savedAt > MAP_PWA_MAX_AGE_MS) {
      await cache.delete(request)
      return null
    }
    return { data: payload.data }
  } catch {
    return null
  }
}

/** Jaringan putus, atau server tidak menjawab. 401/403/404 tidak memakai salinan lama. */
export function isOfflineFetchError(error: unknown) {
  if (typeof navigator !== "undefined" && navigator.onLine === false) return true
  const status = (error as { response?: { status?: number }; statusCode?: number } | null)?.response?.status
    ?? (error as { statusCode?: number } | null)?.statusCode
  if (status == null) return true
  return status >= 500
}

/**
 * Ambil dari jaringan, simpan untuk offline, dan pakai salinan perangkat
 * hanya bila jaringan gagal.
 */
export async function fetchMapCached<T>(userId: string, url: string, request: () => Promise<T>): Promise<T> {
  try {
    const data = await request()
    await saveMapResponse(userId, url, data)
    return data
  } catch (error) {
    if (!isOfflineFetchError(error)) throw error
    const cached = await readMapResponse<T>(userId, url)
    if (!cached) throw error
    return cached.data
  }
}
