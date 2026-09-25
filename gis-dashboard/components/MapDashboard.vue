<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
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
type LeafletTileLayer = import('leaflet').TileLayer
type FeatureCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, Record<string, any>>
type Feature = GeoJSON.Feature<GeoJSON.Geometry, Record<string, any>>
type FeatureProperties = Record<string, string | number | null | undefined>

type PopupCacheEntry = {
  detail: BlokDetailResponse
  bulan: string
  tahun: string
  popupData: BlokPopupData
}

type BasemapMode = {
  id: string
  label: string
  group: string
  url: string
  attribution: string
  maxZoom?: number
  subdomains?: string | string[]
}

const BASEMAP_MODES: BasemapMode[] = [
  {
    id: 'osm',
    label: 'OpenStreetMap',
    group: 'Street',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  },
  {
    id: 'osm-hot',
    label: 'OSM HOT',
    group: 'Street',
    url: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team',
    maxZoom: 19,
  },
  {
    id: 'esri-street',
    label: 'Esri Street',
    group: 'Street',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  },
  {
    id: 'esri-gray',
    label: 'Esri Gray',
    group: 'Light / Dark',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 16,
  },
  {
    id: 'esri-imagery',
    label: 'Esri Satellite',
    group: 'Satellite / Terrain',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  },
  {
    id: 'esri-topo',
    label: 'Esri Topo',
    group: 'Satellite / Terrain',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  },
  {
    id: 'opentopomap',
    label: 'OpenTopoMap',
    group: 'Satellite / Terrain',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: 'Map data: &copy; OpenStreetMap, SRTM | Map style: &copy; OpenTopoMap',
    maxZoom: 17,
  },
  {
    id: 'cyclosm',
    label: 'CyclOSM',
    group: 'Special',
    url: 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors | CyclOSM',
    maxZoom: 20,
  },
]

const mapStore = useMapStore()

const emit = defineEmits<{
  mapClick: []
}>()

const mapContainer = shallowRef<HTMLElement | null>(null)
const map = shallowRef<LeafletMap | null>(null)
const geoJsonLayer = shallowRef<LeafletGeoJson | null>(null)
const baseTileLayer = shallowRef<LeafletTileLayer | null>(null)
const isMapReady = shallowRef(false)
const isLayerUpdating = shallowRef(false)
const leafletModule = shallowRef<LeafletModule | null>(null)
const isBasemapMenuOpen = ref(false)
const selectedBasemapId = ref('osm')

const popupCacheByBlokId = new Map<string, PopupCacheEntry>()
const loadSequenceByBlokId = new Map<string, number>()

const defaultCenter: [number, number] = [-6.2088, 106.8456]
const defaultZoom = 6

const selectedBasemap = computed(
  () => BASEMAP_MODES.find((item) => item.id === selectedBasemapId.value) ?? BASEMAP_MODES[0],
)

const basemapGroups = computed(() => {
  const groups: Array<{ name: string; items: BasemapMode[] }> = []
  for (const mode of BASEMAP_MODES) {
    const existing = groups.find((group) => group.name === mode.group)
    if (existing) {
      existing.items.push(mode)
    }
    else {
      groups.push({ name: mode.group, items: [mode] })
    }
  }
  return groups
})

function createTileLayer(L: LeafletModule, mode: BasemapMode) {
  return L.tileLayer(mode.url, {
    attribution: mode.attribution,
    maxZoom: mode.maxZoom ?? 19,
    ...(mode.subdomains ? { subdomains: mode.subdomains } : {}),
  })
}

function applyBasemap(modeId: string) {
  const L = leafletModule.value
  if (!L || !map.value)
    return

  const mode = BASEMAP_MODES.find((item) => item.id === modeId) ?? BASEMAP_MODES[0]
  if (!mode)
    return

  selectedBasemapId.value = mode.id

  if (baseTileLayer.value) {
    map.value.removeLayer(baseTileLayer.value)
    baseTileLayer.value = null
  }

  const nextLayer = createTileLayer(L, mode)
  nextLayer.addTo(map.value)
  nextLayer.bringToBack()
  baseTileLayer.value = nextLayer
  isBasemapMenuOpen.value = false
}

function toggleBasemapMenu() {
  isBasemapMenuOpen.value = !isBasemapMenuOpen.value
}

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
  layer.off('click')

  layer.on('click', () => {
    emit('mapClick')
  })

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

  map.value.on('click', () => {
    emit('mapClick')
  })

  const initialMode = BASEMAP_MODES.find((item) => item.id === selectedBasemapId.value) ?? BASEMAP_MODES[0]
  if (initialMode) {
    baseTileLayer.value = createTileLayer(L, initialMode)
    baseTileLayer.value.addTo(map.value)
  }

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

  if (baseTileLayer.value && map.value) {
    map.value.removeLayer(baseTileLayer.value)
    baseTileLayer.value = null
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

    <!-- Basemap mode switcher -->
    <div class="absolute bottom-4 left-3 z-[1000] sm:left-4">
      <div class="relative">
        <button
          type="button"
          class="inline-flex h-10 items-center gap-2 rounded-xl border border-map-light bg-surface-90 px-3 text-13 font-semibold text-slate shadow-md backdrop-blur-md hover-bg-hover-slate"
          :aria-expanded="isBasemapMenuOpen"
          aria-label="Ganti mode tampilan peta"
          @click="toggleBasemapMenu">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          <span class="max-w-[9rem] truncate">{{ selectedBasemap?.label }}</span>
          <span class="text-12 text-gray-muted">{{ isBasemapMenuOpen ? '▴' : '▾' }}</span>
        </button>

        <div
          v-if="isBasemapMenuOpen"
          class="absolute bottom-full left-0 mb-2 w-72 max-h-[min(70vh,28rem)] overflow-y-auto rounded-xl border border-map-light bg-surface shadow-xl">
          <div class="sticky top-0 z-10 border-b border-map-light bg-surface px-3 py-2">
            <p class="text-11 font-semibold uppercase tracking-wide text-gray-muted">
              Mode Tampilan Peta
            </p>
            <p class="text-11 text-gray-muted">
              {{ BASEMAP_MODES.length }} mode tersedia
            </p>
          </div>
          <div class="space-y-2 p-2">
            <section v-for="group in basemapGroups" :key="group.name">
              <p class="mb-0.5 px-2 text-11 font-semibold uppercase tracking-wide text-gray-muted">
                {{ group.name }}
              </p>
              <div class="space-y-0.5">
                <button
                  v-for="mode in group.items"
                  :key="mode.id"
                  type="button"
                  class="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-13 transition-colors"
                  :class="selectedBasemapId === mode.id
                    ? 'bg-blue-primary text-on-brand'
                    : 'text-slate hover-bg-hover-slate'"
                  @click="applyBasemap(mode.id)">
                  <span class="font-medium">{{ mode.label }}</span>
                  <span v-if="selectedBasemapId === mode.id" class="text-12">✓</span>
                </button>
              </div>
            </section>
          </div>
        </div>
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
