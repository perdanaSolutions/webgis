import { afterEach, describe, expect, it } from "vitest"

import {
  MAP_CACHE_SCHEMA,
  MAP_PWA_CACHE,
  fetchMapCached,
  installMapCacheSchema,
  isMapSpatialUrl,
  isOfflineFetchError,
  normalizeMapUrl,
  readMapResponse,
  saveMapResponse,
} from "./mapCacheSchema"

class MemoryCache {
  private readonly store = new Map<string, Response>()

  async match(request: Request) {
    const hit = this.store.get(request.url)
    return hit ? hit.clone() : undefined
  }

  async put(request: Request, response: Response) {
    this.store.set(request.url, response.clone())
  }

  async delete(request: Request) {
    this.store.delete(request.url)
  }
}

const buckets = new Map<string, MemoryCache>()

function installMemoryCaches() {
  buckets.clear()
  Object.defineProperty(globalThis, "caches", {
    configurable: true,
    value: {
      open: async (name: string) => {
        let bucket = buckets.get(name)
        if (!bucket) {
          bucket = new MemoryCache()
          buckets.set(name, bucket)
        }
        return bucket
      },
      keys: async () => [...buckets.keys()],
      delete: async (name: string) => buckets.delete(name),
    },
  })
}

describe("skema cache peta", () => {
  afterEach(() => {
    Reflect.deleteProperty(globalThis, "caches")
  })

  it("memakai versi skema yang sama dengan Redis", () => {
    expect(MAP_CACHE_SCHEMA).toBe("1")
    expect(MAP_PWA_CACHE).toBe("gis-map-pwa-v1-api")
  })

  it("mengenali URL baca spatial dan mengurutkan query", () => {
    expect(isMapSpatialUrl("http://localhost:8000/api/v1/spatial/geojson?tahun=2026")).toBe(true)
    expect(isMapSpatialUrl("http://localhost:8000/api/v1/menus/")).toBe(false)
    expect(normalizeMapUrl("http://localhost:8000/api/v1/spatial/geojson?b=2&a=1&kosong=")).toBe(
      "http://localhost:8000/api/v1/spatial/geojson?a=1&b=2",
    )
  })

  it("menyimpan JSON per user dan membacanya saat jaringan gagal", async () => {
    installMemoryCaches()
    const url = "http://localhost:8000/api/v1/spatial/geojson?tahun=2026"
    let online = true
    const data = await fetchMapCached("user-1", url, async () => {
      if (!online) throw new TypeError("Failed to fetch")
      return { type: "FeatureCollection", features: [{ id: 1 }] }
    })
    expect(data.features).toHaveLength(1)

    online = false
    const offline = await fetchMapCached("user-1", url, async () => {
      throw new TypeError("Failed to fetch")
    })
    expect(offline).toEqual(data)

    await expect(fetchMapCached("user-2", url, async () => {
      throw new TypeError("Failed to fetch")
    })).rejects.toThrow("Failed to fetch")
  })

  it("tidak memakai salinan lama untuk 401", async () => {
    installMemoryCaches()
    const url = "http://localhost:8000/api/v1/spatial/blok/detail?blok_id=1"
    await saveMapResponse("user-1", url, { nama: "lama" })
    await expect(fetchMapCached("user-1", url, async () => {
      const error = new Error("unauthorized") as Error & { response: { status: number } }
      error.response = { status: 401 }
      throw error
    })).rejects.toThrow("unauthorized")
    expect(isOfflineFetchError({ response: { status: 404 } })).toBe(false)
    expect(isOfflineFetchError(new TypeError("Failed to fetch"))).toBe(true)
  })

  it("membuang cache skema lama saat halaman peta dipasang", async () => {
    installMemoryCaches()
    buckets.set("gis-map-pwa-v0-api", new MemoryCache())
    buckets.set(MAP_PWA_CACHE, new MemoryCache())
    await installMapCacheSchema()
    expect(await caches.keys()).toEqual([MAP_PWA_CACHE])
    expect(await readMapResponse("user-1", "http://localhost:8000/api/v1/menus/")).toBeNull()
  })
})
