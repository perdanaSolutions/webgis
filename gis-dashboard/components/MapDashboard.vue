<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import 'leaflet/dist/leaflet.css'

import { useMapStore } from '~/stores/mapStore'
import {
  buildBlokPopupHtml,
  normalizeBlokPopupData,
} from '~/utils/mapBlokPopup'

type LeafletModule = typeof import('leaflet')
type LeafletMap = import('leaflet').Map
type LeafletGeoJson = import('leaflet').GeoJSON
type LeafletLayer = import('leaflet').Layer
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

function getStatusFromFeature(feature: Feature) {
  const properties = (feature.properties ?? {}) as FeatureProperties
  return String(
    properties.status_tanam
    ?? properties.Status
    ?? properties.Status_1
    ?? '',
  )
}

function shouldIncludeFeature(_feature: Feature) {
  return true
}

function getRenderableFeatureCollection(): FeatureCollection {
  const fromStore = mapStore.filteredGeoJSON

  if (!fromStore || !Array.isArray(fromStore.features)) {
    return {
      type: 'FeatureCollection',
      features: [],
    }
  }

  const filteredFeatures = fromStore.features.filter((feature) => {
    return shouldIncludeFeature(feature as Feature)
  })

  return {
    type: 'FeatureCollection',
    features: filteredFeatures,
  }
}

function buildPopupContent(
  feature: Feature,
  overrides?: { bulan?: string; tahun?: string },
  loading = false,
) {
  const popupData = normalizeBlokPopupData(
    (feature.properties ?? {}) as FeatureProperties,
    mapStore.getPopupHierarchyLabels(),
    overrides,
  )

  return buildBlokPopupHtml(popupData, { loading })
}

function getPopupElement(layer: LeafletLayer) {
  const popup = (layer as any).getPopup?.()
  return popup?.getElement?.() as HTMLElement | undefined
}

async function handlePopupApply(layer: LeafletLayer, feature: Feature) {
  const popupElement = getPopupElement(layer)
  if (!popupElement)
    return

  const bulanSelect = popupElement.querySelector('[data-popup-bulan]') as HTMLSelectElement | null
  const tahunSelect = popupElement.querySelector('[data-popup-tahun]') as HTMLSelectElement | null
  const applyButton = popupElement.querySelector('[data-popup-apply]') as HTMLButtonElement | null

  if (!bulanSelect || !tahunSelect || !applyButton)
    return

  const bulan = bulanSelect.value
  const tahun = tahunSelect.value
  const properties = (feature.properties ?? {}) as FeatureProperties
  const kodeBlok = String(properties.kode_blok ?? '')

  applyButton.disabled = true
  applyButton.textContent = 'Memuat...'

  try {
    const updatedFeature = await mapStore.fetchBlokPopupData({
      kodePt: mapStore.selectedPt || undefined,
      kodeEst: mapStore.selectedEstate || undefined,
      kodeAfd: mapStore.selectedAfdeling || undefined,
      kodeBlok,
      bulan,
      tahun,
    })

    const nextFeature = updatedFeature ?? feature
    const nextHtml = buildPopupContent(nextFeature, { bulan, tahun })

    ;(layer as any).setPopupContent?.(nextHtml)
    attachPopupApplyHandler(layer, nextFeature as Feature)
  } catch {
    applyButton.disabled = false
    applyButton.textContent = 'Apply'
  }
}

function attachPopupApplyHandler(layer: LeafletLayer, feature: Feature) {
  const popupElement = getPopupElement(layer)
  if (!popupElement)
    return

  const applyButton = popupElement.querySelector('[data-popup-apply]') as HTMLButtonElement | null
  if (!applyButton)
    return

  const clonedButton = applyButton.cloneNode(true) as HTMLButtonElement
  applyButton.replaceWith(clonedButton)

  clonedButton.addEventListener('click', () => {
    void handlePopupApply(layer, feature)
  })
}

function bindPopupInteractions(layer: LeafletLayer, feature: Feature) {
  layer.off('popupopen')

  layer.on('popupopen', () => {
    attachPopupApplyHandler(layer, feature)
  })
}

function resolveFeatureStyle(feature?: Feature) {
  const status = feature ? getStatusFromFeature(feature) : ''

  return {
    color: '#1e293b',
    weight: 1,
    fillColor: getStatusColor(status),
    fillOpacity: 0.45,
  }
}

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
        const popupHtml = buildPopupContent(feature as Feature)
        leafletLayer.bindPopup(popupHtml, {
          maxWidth: 340,
          minWidth: 320,
          autoPanPadding: [24, 24],
          className: 'map-blok-popup-wrapper',
        })
        bindPopupInteractions(leafletLayer, feature as Feature)
      },
    })

    geoJsonLayer.value = layer
    geoJsonLayer.value.addTo(map.value)

    const bounds = geoJsonLayer.value.getBounds()

    if (bounds.isValid()) {
      map.value.fitBounds(bounds, {
        padding: [32, 32],
        maxZoom: 16,
      })
    } else {
      map.value.setView(defaultCenter, defaultZoom)
    }
  } finally {
    isLayerUpdating.value = false
  }
}

async function initializeMap() {
  const L = await import('leaflet')

  if (!mapContainer.value)
    return

  map.value = L.map(mapContainer.value).setView(defaultCenter, defaultZoom)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map.value)

  isMapReady.value = true

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
    <div ref="mapContainer" class="h-full w-full" />

    <div
      v-if="mapStore.loadingGeoJSON"
      class="absolute inset-0 z-[1100] flex items-center justify-center bg-white/70 backdrop-blur-[1px]"
    >
      <div class="flex flex-col items-center gap-3 rounded-xl bg-white px-5 py-4 shadow-lg">
        <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-[#2B7FFF] border-t-transparent" />
        <p class="text-[13px] font-medium text-[#334155]">
          Memuat data peta...
        </p>
      </div>
    </div>

    <div class="absolute bottom-4 right-4 z-[1000] rounded-lg bg-white/90 px-3 py-2 text-sm shadow-md">
      Menampilkan <strong>{{ featureCount }}</strong> blok
    </div>
  </div>
</template>

<style>
.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-content-wrapper {
  border-radius: 10px;
  padding: 0;
  overflow: hidden;
}

.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-content {
  margin: 0;
  width: 320px !important;
  max-width: 320px;
  max-height: 72vh;
  overflow-y: auto;
  overflow-x: hidden;
}

.leaflet-popup.map-blok-popup-wrapper .leaflet-popup-tip {
  background: #fff;
}
</style>
