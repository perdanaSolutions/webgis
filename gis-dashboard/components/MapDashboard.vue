<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue'
import 'leaflet/dist/leaflet.css'

import { useMapStore } from '~/stores/mapStore'
import {
  buildBlokPopupHtml,
  buildBlokPopupSkeletonHtml,
  getBulanPopupLabel,
  getCurrentPopupPeriod,
  normalizeBlokDetailResponse,
  normalizeBlokPopupData,
  type BlokDetailResponse,
  type BlokPopupData,
} from '~/utils/mapBlokPopup'

type LeafletModule = typeof import('leaflet')
type LeafletMap = import('leaflet').Map
type LeafletGeoJson = import('leaflet').GeoJSON
type LeafletLayer = import('leaflet').Layer
type FeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, Record<string, any>>
type Feature = GeoJSON.Feature<GeoJSON.Geometry, Record<string, any>>
type FeatureProperties = Record<string, string | number | null | undefined>

type PopupCacheEntry = {
  detail: BlokDetailResponse
  bulan: string
  tahun: string
  popupData: BlokPopupData
}

const mapStore = useMapStore()

const mapContainer = shallowRef<HTMLElement | null>(null)
const map = shallowRef<LeafletMap | null>(null)
const geoJsonLayer = shallowRef<LeafletGeoJson | null>(null)
const isMapReady = shallowRef(false)
const isLayerUpdating = shallowRef(false)
const leafletModule = shallowRef<LeafletModule | null>(null)

const popupCacheByBlokId = new Map<string, PopupCacheEntry>()
const loadSequenceByBlokId = new Map<string, number>()

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

function getFeatureBlokId(feature: Feature) {
  const properties = (feature.properties ?? {}) as FeatureProperties
  return String(properties.blok_id ?? properties.global_id ?? '').trim()
}

function getFeatureKodeBlok(feature: Feature) {
  const properties = (feature.properties ?? {}) as FeatureProperties
  return String(properties.kode_blok ?? '').trim()
}

function getErrorStatus(error: unknown): number | null {
  const err = error as {
    statusCode?: number
    status?: number
    response?: { status?: number }
  }

  return err?.statusCode ?? err?.status ?? err?.response?.status ?? null
}

function buildInitialPopupContent(feature: Feature) {
  const period = getCurrentPopupPeriod()
  const popupData = normalizeBlokPopupData(
    (feature.properties ?? {}) as FeatureProperties,
    mapStore.getPopupHierarchyLabels(),
    period,
  )

  return buildBlokPopupHtml(popupData)
}

function getLayerPopup(layer: LeafletLayer) {
  return (layer as any).getPopup?.() as import('leaflet').Popup | undefined
}

function getPopupElement(layer: LeafletLayer) {
  return getLayerPopup(layer)?.getElement?.() as HTMLElement | undefined
}

function protectPopupInteractions(layer: LeafletLayer) {
  const popupElement = getPopupElement(layer)
  const L = leafletModule.value
  if (!popupElement || !L)
    return

  L.DomEvent.disableClickPropagation(popupElement)
  L.DomEvent.disableScrollPropagation(popupElement)
}

function setPopupHtml(layer: LeafletLayer, html: string) {
  const popup = getLayerPopup(layer)
  if (!popup)
    return

  popup.setContent(html)
  popup.update()

  // Pastikan popup tetap terbuka setelah konten diganti (hindari close karena click-through)
  if (map.value && !popup.isOpen()) {
    layer.openPopup()
  }

  protectPopupInteractions(layer)
}

function setPopupLoading(
  layer: LeafletLayer,
  feature: Feature,
  bulan: string,
  tahun: string,
) {
  const skeletonHtml = buildBlokPopupSkeletonHtml({
    bulan,
    tahun,
    blokId: getFeatureBlokId(feature),
    kodeBlok: getFeatureKodeBlok(feature),
  })

  setPopupHtml(layer, skeletonHtml)
}

function renderPopupFromDetail(
  layer: LeafletLayer,
  feature: Feature,
  detail: BlokDetailResponse | null,
  bulan: string,
  tahun: string,
  errorMessage?: string,
) {
  const hierarchy = mapStore.getPopupHierarchyLabels()
  const popupData = detail
    ? normalizeBlokDetailResponse(detail, hierarchy, { bulan, tahun })
    : normalizeBlokPopupData(
      (feature.properties ?? {}) as FeatureProperties,
      hierarchy,
      { bulan, tahun },
    )

  const nextHtml = buildBlokPopupHtml(popupData, { errorMessage })
  setPopupHtml(layer, nextHtml)
  attachPopupHandlers(layer, feature)

  return popupData
}

function restoreCachedPopup(
  layer: LeafletLayer,
  feature: Feature,
  cache: PopupCacheEntry,
  errorMessage: string,
) {
  const nextHtml = buildBlokPopupHtml(cache.popupData, { errorMessage })
  setPopupHtml(layer, nextHtml)
  attachPopupHandlers(layer, feature)
}

async function loadBlokDetail(
  layer: LeafletLayer,
  feature: Feature,
  bulan: string,
  tahun: string,
  options?: { keepPreviousOn404?: boolean },
) {
  const blokId = getFeatureBlokId(feature)
  if (!blokId) {
    renderPopupFromDetail(
      layer,
      feature,
      null,
      bulan,
      tahun,
      'blok_id tidak ditemukan pada data peta.',
    )
    return
  }

  const nextSequence = (loadSequenceByBlokId.get(blokId) ?? 0) + 1
  loadSequenceByBlokId.set(blokId, nextSequence)

  const previousCache = popupCacheByBlokId.get(blokId)
  setPopupLoading(layer, feature, bulan, tahun)

  try {
    const detail = await mapStore.fetchBlokPopupData({
      blokId,
      bulan,
      tahun,
    }) as BlokDetailResponse | null

    if (loadSequenceByBlokId.get(blokId) !== nextSequence)
      return

    const popupData = renderPopupFromDetail(
      layer,
      feature,
      detail,
      bulan,
      tahun,
    )

    if (detail) {
      popupCacheByBlokId.set(blokId, {
        detail,
        bulan,
        tahun,
        popupData,
      })
    }
  }
  catch (error) {
    if (loadSequenceByBlokId.get(blokId) !== nextSequence)
      return

    const status = getErrorStatus(error)
    const keepPrevious = options?.keepPreviousOn404 !== false

    if (status === 404 && keepPrevious && previousCache) {
      const alertMessage = `Data filter ${getBulanPopupLabel(bulan)} ${tahun} tidak tersedia.`
      restoreCachedPopup(layer, feature, previousCache, alertMessage)
      // window.alert(alertMessage)
      return
    }

    if (status === 404) {
      renderPopupFromDetail(
        layer,
        feature,
        null,
        bulan,
        tahun,
        `Data filter ${getBulanPopupLabel(bulan)} ${tahun} tidak tersedia.`,
      )
      return
    }

    if (previousCache && options?.keepPreviousOn404) {
      restoreCachedPopup(
        layer,
        feature,
        previousCache,
        'Gagal memuat detail blok. Data sebelumnya tetap ditampilkan.',
      )
      return
    }

    renderPopupFromDetail(
      layer,
      feature,
      null,
      bulan,
      tahun,
      'Gagal memuat detail blok. Coba lagi.',
    )
  }
}

async function handlePopupApply(layer: LeafletLayer, feature: Feature) {
  const popupElement = getPopupElement(layer)
  if (!popupElement)
    return

  const bulanSelect = popupElement.querySelector('[data-popup-bulan]') as HTMLSelectElement | null
  const tahunSelect = popupElement.querySelector('[data-popup-tahun]') as HTMLSelectElement | null

  if (!bulanSelect || !tahunSelect)
    return

  await loadBlokDetail(layer, feature, bulanSelect.value, tahunSelect.value, {
    keepPreviousOn404: true,
  })
}

function attachPopupHandlers(layer: LeafletLayer, feature: Feature) {
  const popupElement = getPopupElement(layer)
  if (!popupElement)
    return

  protectPopupInteractions(layer)

  const applyButton = popupElement.querySelector('[data-popup-apply]') as HTMLButtonElement | null
  if (!applyButton)
    return

  const clonedButton = applyButton.cloneNode(true) as HTMLButtonElement
  applyButton.replaceWith(clonedButton)

  const onApply = (event: Event) => {
    event.preventDefault()
    event.stopPropagation()
    if (typeof (event as any).stopImmediatePropagation === 'function') {
      ; (event as any).stopImmediatePropagation()
    }

    // Defer ganti konten supaya click tidak "jatuh" ke map dan menutup popup
    window.setTimeout(() => {
      void handlePopupApply(layer, feature)
    }, 0)
  }

  clonedButton.addEventListener('mousedown', (event) => {
    event.preventDefault()
    event.stopPropagation()
  })
  clonedButton.addEventListener('click', onApply)
}

function bindPopupInteractions(layer: LeafletLayer, feature: Feature) {
  layer.off('popupopen')

  layer.on('popupopen', () => {
    protectPopupInteractions(layer)
    const period = getCurrentPopupPeriod()
    void loadBlokDetail(layer, feature, period.bulan, period.tahun, {
      keepPreviousOn404: false,
    })
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
        const popupHtml = buildInitialPopupContent(feature as Feature)
        leafletLayer.bindPopup(popupHtml, {
          maxWidth: 340,
          minWidth: 320,
          autoPanPadding: [24, 24],
          className: 'map-blok-popup-wrapper',
          closeOnClick: false,
          autoClose: true,
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
    }
    else {
      map.value.setView(defaultCenter, defaultZoom)
    }
  }
  finally {
    isLayerUpdating.value = false
  }
}

async function initializeMap() {
  const L = await import('leaflet')
  leafletModule.value = L

  if (!mapContainer.value)
    return

  map.value = L.map(mapContainer.value, {
    closePopupOnClick: false,
  }).setView(defaultCenter, defaultZoom)

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
  popupCacheByBlokId.clear()
  loadSequenceByBlokId.clear()
})

watch(
  () => mapStore.filteredGeoJSON,
  async () => {
    if (!isMapReady.value)
      return

    const L = leafletModule.value ?? await import('leaflet')
    leafletModule.value = L
    updateGeoJSONLayer(L)
  },
  { deep: true },
)
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="mapContainer" class="h-full w-full" />

    <div v-if="mapStore.loadingGeoJSON"
      class="absolute inset-0 z-[1100] flex items-center justify-center bg-surface-70 backdrop-blur-[1px]">
      <div class="flex flex-col items-center gap-3 rounded-xl bg-surface px-5 py-4 shadow-lg">
        <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-blue-primary border-t-transparent" />
        <p class="text-13 font-medium text-slate">
          Memuat data peta...
        </p>
      </div>
    </div>

    <div class="absolute bottom-4 right-4 z-[1000] rounded-lg bg-surface-90 px-3 py-2 text-size-sm shadow-md">
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

@keyframes map-blok-skeleton-shine {
  0% {
    background-position: 200% 0;
  }

  100% {
    background-position: -200% 0;
  }
}
</style>
