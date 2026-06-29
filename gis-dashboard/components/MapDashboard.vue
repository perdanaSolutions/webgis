<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import 'leaflet/dist/leaflet.css'

import { useMapStore } from '~/stores/mapStore'

type LeafletModule = typeof import('leaflet')

const mapStore = useMapStore()

const mapContainer = shallowRef<HTMLElement | null>(null)
const map = shallowRef<import('leaflet').Map | null>(null)
const geoJsonLayer = shallowRef<import('leaflet').GeoJSON | null>(null)
const isMapReady = shallowRef(false)
const defaultCenter: [number, number] = [-6.2088, 106.8456]
const defaultZoom = 6

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

function featureToPopupHtml(feature: GeoJSON.Feature) {
  const properties = (feature.properties ?? {}) as Record<string, string | number | null | undefined>

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

  return `
    <div style="min-width: 260px;">
      <h3 style="margin:0 0 8px;font-size:16px;font-weight:700;">Blok ${blok}</h3>
      <div style="font-size:13px;line-height:1.4;">
        <div><strong>Global ID:</strong> ${globalId}</div>
        <div><strong>PT:</strong> ${pt}</div>
        <div><strong>Estate:</strong> ${estate}</div>
        <div><strong>Afdeling:</strong> ${afdeling}</div>
        <div><strong>Status Tanam:</strong> ${status}</div>
        <div><strong>Tahun Tanam:</strong> ${tahunTanam}</div>
        <div><strong>Jenis Bibit:</strong> ${jenisBibit}</div>
        <hr style="margin:8px 0;">
        <div><strong>Luas Tanam:</strong> ${luasTanam.toFixed(2)} ha</div>
        <div><strong>Total Pokok:</strong> ${pokok.toLocaleString('id-ID')}</div>
        <div><strong>Jalan:</strong> ${jalan.toFixed(2)}</div>
        <div><strong>Drainase:</strong> ${drainase.toFixed(2)}</div>
        <div><strong>Jembatan:</strong> ${jembatan.toLocaleString('id-ID')}</div>
      </div>
    </div>
  `
}

function updateGeoJSONLayer(L: LeafletModule) {
  if (!map.value || !isMapReady.value)
    return

  if (geoJsonLayer.value) {
    geoJsonLayer.value.removeFrom(map.value)
    geoJsonLayer.value = null
  }

  const featureCollection = mapStore.filteredGeoJSON
  const layer = L.geoJSON(featureCollection, {
    style: (feature) => {
      const properties = (feature?.properties ?? {}) as Record<string, string | number | null | undefined>
      const status = String(properties.Status ?? properties.Status_1 ?? '')

      return {
        color: '#1e293b',
        weight: 1,
        fillColor: getStatusColor(status),
        fillOpacity: 0.45,
      }
    },
    onEachFeature: (feature, leafletLayer) => {
      leafletLayer.bindPopup(featureToPopupHtml(feature))
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
  }
}

const featureCount = computed(() => mapStore.filteredFeatures.length)

onMounted(async () => {
  const L = await import('leaflet')

  mapStore.loadGeoJSONData()

  if (!mapContainer.value)
    return

  map.value = L.map(mapContainer.value).setView(defaultCenter, defaultZoom)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map.value)

  isMapReady.value = true
  updateGeoJSONLayer(L)
})

watch(
  () => mapStore.filteredGeoJSON,
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
    <div
      ref="mapContainer"
      class="h-full w-full"
    />

    <div class="absolute bottom-4 right-4 z-[1000] rounded-lg bg-white/90 px-3 py-2 text-sm shadow-md">
      Menampilkan <strong>{{ featureCount }}</strong> blok
    </div>
  </div>
</template>
