<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import 'leaflet/dist/leaflet.css'

import { useMapStore } from '~/stores/mapStore'

type LeafletModule = typeof import('leaflet')
type LeafletMap = import('leaflet').Map
type LeafletGeoJson = import('leaflet').GeoJSON
type FeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, Record<string, any>>
type Feature = GeoJSON.Feature<GeoJSON.Geometry, Record<string, any>>
type FeatureProperties = Record<string, string | number | null | undefined>

const mapStore = useMapStore()

const mapContainer = shallowRef<HTMLElement | null>(null)
const map = shallowRef<LeafletMap | null>(null)
const geoJsonLayer = shallowRef<LeafletGeoJson | null>(null)
const isMapReady = shallowRef(false)
const isLayerUpdating = shallowRef(false)

const defaultCenter: [number, number] = [-6.2088, 106.8456]
const defaultZoom = 6

/**
 * Helper status warna polygon.
 * Digunakan untuk style default layer sementara.
 * Nanti bisa disesuaikan lagi berdasarkan legend/aturan bisnis final.
 */
function getStatusColor(status: string) {
  const normalizedStatus = status.toUpperCase()

  if (normalizedStatus === 'TM')
    return '#2e7d32'

  if (normalizedStatus === 'TBM')
    return '#0288d1'

  if (normalizedStatus === 'TT')
    return '#f57c00'

  return '#455a64'
}

/**
 * Normalisasi properti feature agar konsisten dipakai di popup/style/filter.
 * Tujuan: antisipasi variasi nama field dari sumber geojson yang berbeda.
 */
function normalizeFeatureProperties(feature: Feature) {
  const properties = (feature.properties ?? {}) as FeatureProperties

  const blok = String(properties.Blok ?? properties.Blok_1 ?? properties.Kode_Blok ?? '-')
  const globalId = String(properties.GlobalID ?? properties.id ?? '-')
  const pt = String(properties.PT ?? properties.PT_1 ?? '-')
  const estate = String(properties.Estate ?? properties.Estate_1 ?? '-')
  const afdeling = String(properties.Afdeling ?? properties.Afdeling_1 ?? '-')
  const status = String(properties.Status ?? properties.Status_1 ?? '-')
  const tahunTanam = String(properties.TT ?? properties.TT_1 ?? '-')
  const jenisBibit = String(properties.JenisBibit ?? properties.Bibit ?? '-')
  const luasTanam = Number(properties.LTanam_1 ?? properties.LTanam ?? 0)
  const pokok = Number(properties.Pokok_1 ?? properties.Pokok ?? 0)
  const jalan = Number(properties.Jalan ?? 0)
  const drainase = Number(properties.DrnCanal ?? 0)
    + Number(properties.DrnMD ?? 0)
    + Number(properties.DrnCD ?? 0)
    + Number(properties.DrnFD ?? 0)
  const jembatan = Number(properties.Jembatan ?? 0)

  return {
    blok,
    globalId,
    pt,
    estate,
    afdeling,
    status,
    tahunTanam,
    jenisBibit,
    luasTanam,
    pokok,
    jalan,
    drainase,
    jembatan,
  }
}

/**
 * TEMPORARY FILTER PIPELINE
 * Tempat menaruh rule filter spasial ke depan ketika tombol Apply sudah mengirim filter final.
 * Saat ini belum membatasi data (return true), hanya disiapkan strukturnya.
 */
function shouldIncludeFeature(_normalized: ReturnType<typeof normalizeFeatureProperties>) {
  return true
}

/**
 * Menyiapkan sumber feature collection untuk dirender ke peta.
 * - Prioritas data hasil filter store (kalau sudah tersedia)
 * - Fallback ke empty collection agar peta tetap tampil stabil
 */
function getRenderableFeatureCollection(): FeatureCollection {
  const fromStore = (mapStore as typeof mapStore & {
    filteredGeoJSON?: FeatureCollection
  }).filteredGeoJSON

  if (!fromStore || !Array.isArray(fromStore.features)) {
    return {
      type: 'FeatureCollection',
      features: [],
    }
  }

  const filteredFeatures = fromStore.features.filter((feature) => {
    const normalized = normalizeFeatureProperties(feature as Feature)
    return shouldIncludeFeature(normalized)
  })

  return {
    type: 'FeatureCollection',
    features: filteredFeatures,
  }
}

/**
 * Builder popup HTML berdasarkan properties yang sudah dinormalisasi.
 */
function featureToPopupHtml(feature: Feature) {
  const normalized = normalizeFeatureProperties(feature)

  return `
    <div style="min-width: 260px;">
      <h3 style="margin:0 0 8px;font-size:16px;font-weight:700;">Blok ${normalized.blok}</h3>
      <div style="font-size:13px;line-height:1.4;">
        <div><strong>Global ID:</strong> ${normalized.globalId}</div>
        <div><strong>PT:</strong> ${normalized.pt}</div>
        <div><strong>Estate:</strong> ${normalized.estate}</div>
        <div><strong>Afdeling:</strong> ${normalized.afdeling}</div>
        <div><strong>Status Tanam:</strong> ${normalized.status}</div>
        <div><strong>Tahun Tanam:</strong> ${normalized.tahunTanam}</div>
        <div><strong>Jenis Bibit:</strong> ${normalized.jenisBibit}</div>
        <hr style="margin:8px 0;">
        <div><strong>Luas Tanam:</strong> ${normalized.luasTanam.toFixed(2)} ha</div>
        <div><strong>Total Pokok:</strong> ${normalized.pokok.toLocaleString('id-ID')}</div>
        <div><strong>Jalan:</strong> ${normalized.jalan.toFixed(2)}</div>
        <div><strong>Drainase:</strong> ${normalized.drainase.toFixed(2)}</div>
        <div><strong>Jembatan:</strong> ${normalized.jembatan.toLocaleString('id-ID')}</div>
      </div>
    </div>
  `
}

/**
 * Resolver style polygon.
 * Dipisah agar mudah dimodifikasi saat logic style berbasis filter ditambahkan.
 */
function resolveFeatureStyle(feature?: Feature) {
  const normalized = feature
    ? normalizeFeatureProperties(feature)
    : {
      status: '',
    }

  return {
    color: '#1e293b',
    weight: 1,
    fillColor: getStatusColor(normalized.status),
    fillOpacity: 0.45,
  }
}

/**
 * Menggambar ulang layer geojson di peta.
 * Dipanggil saat map ready + data berubah.
 */
function updateGeoJSONLayer(L: LeafletModule) {
  if (!map.value || !isMapReady.value || isLayerUpdating.value)
    return

  isLayerUpdating.value = true

  try {
    if (geoJsonLayer.value) {
      geoJsonLayer.value.removeFrom(map.value)
      geoJsonLayer.value = null
    }

    const featureCollection = getRenderableFeatureCollection()

    const layer = L.geoJSON(featureCollection, {
      style: (feature) => resolveFeatureStyle(feature as Feature),
      onEachFeature: (feature, leafletLayer) => {
        leafletLayer.bindPopup(featureToPopupHtml(feature as Feature))
      },
    })

    geoJsonLayer.value = layer
    geoJsonLayer.value.addTo(map.value)

    const bounds = geoJsonLayer.value.getBounds()

    if (bounds.isValid()) {
      map.value.fitBounds(bounds, {
        padding: [20, 20],
        maxZoom: 15,
      })
    } else {
      map.value.setView(defaultCenter, defaultZoom)
    }
  } finally {
    isLayerUpdating.value = false
  }
}

/**
 * Init map dasar (tile + view default).
 */
async function initializeMap() {
  const L = await import('leaflet')

  if (!mapContainer.value)
    return

  map.value = L.map(mapContainer.value).setView(defaultCenter, defaultZoom)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map.value)

  isMapReady.value = true

  // Memastikan Leaflet menghitung ukuran container dengan benar setelah render.
  setTimeout(() => {
    map.value?.invalidateSize()
  }, 0)

  updateGeoJSONLayer(L)
}

const featureCount = computed(() => {
  const data = getRenderableFeatureCollection()
  return data.features.length
})

onMounted(async () => {
  // Untuk kebutuhan saat ini, load data tetap dipanggil agar ketika data siap, layer bisa langsung render.
  // Nantinya bisa dipicu penuh oleh tombol Apply jika flow final sudah aktif.
  void mapStore.loadGeoJSONData()

  await initializeMap()
})

onBeforeUnmount(() => {
  if (geoJsonLayer.value && map.value) {
    geoJsonLayer.value.removeFrom(map.value)
    geoJsonLayer.value = null
  }

  if (map.value) {
    map.value.remove()
    map.value = null
  }

  isMapReady.value = false
})

watch(
  () => (mapStore as typeof mapStore & {
    filteredGeoJSON?: FeatureCollection
  }).filteredGeoJSON,
  async () => {
    if (!isMapReady.value)
      return

    const L = await import('leaflet')
    updateGeoJSONLayer(L)
  },
  { deep: true },
)
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="mapContainer" class="h-full w-full" />

    <div class="absolute bottom-4 right-4 z-[1000] rounded-lg bg-white/90 px-3 py-2 text-sm shadow-md">
      Menampilkan <strong>{{ featureCount }}</strong> blok
    </div>
  </div>
</template>
