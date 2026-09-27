<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import 'leaflet/dist/leaflet.css'

import MapLayerPanel, { type OverlayListItem } from '~/components/map/MapLayerPanel.vue'
import { useMapStore } from '~/stores/mapStore'
import {
  BASEMAPS,
  type BasemapKey,
  DEFAULT_BASEMAP,
  getOverlayColor,
  getOverlayLegend,
  getOverlayStyle,
  type OverlayStyle,
} from '~/utils/mapLayers'
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

const props = withDefaults(defineProps<{
  /** Area peta yang tertutup panel (px) -> dipakai saat zoom-to-fit & posisi kontrol */
  insets?: { top: number, right: number, bottom: number, left: number }
}>(), {
  insets: () => ({ top: 0, right: 0, bottom: 0, left: 0 }),
})

const mapStore = useMapStore()

// Urutan tumpukan: batas blok < poligon tematik < garis < titik
const BLOCK_PANE = 'blocks'
const POLYGON_PANE = 'overlay-polygons'
const LINE_PANE = 'overlay-lines'
const POINT_PANE = 'overlay-points'

const OVERLAY_ORDER = ['sawit', 'tph', 'jalan', 'jembatan', 'landuse', 'slope']
const OVERLAY_LABELS: Record<string, string> = {
  sawit: 'Pokok Sawit',
  tph: 'TPH',
  jalan: 'Jalan',
  jembatan: 'Jembatan',
  landuse: 'Land Use',
  slope: 'Kelerengan (Slope)',
}

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
    pane: BLOCK_PANE,
  }
}

/** Popup digeser (auto-pan) agar tidak tertutup panel filter/profil di sisi peta. */
function popupPanPadding() {
  const inset = props.insets
  return {
    autoPanPaddingTopLeft: [inset.left + 24, inset.top + 24] as [number, number],
    autoPanPaddingBottomRight: [inset.right + 24, inset.bottom + 24] as [number, number],
  }
}

function fitPaddingOptions() {
  const inset = props.insets
  return {
    paddingTopLeft: [inset.left + 32, inset.top + 32] as [number, number],
    paddingBottomRight: [inset.right + 32, inset.bottom + 32] as [number, number],
    maxZoom: 16,
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
      pane: BLOCK_PANE,
      style: (feature) => resolveFeatureStyle(feature as Feature),
      onEachFeature: (feature, leafletLayer) => {
        const popupHtml = buildInitialPopupContent(feature as Feature)
        leafletLayer.bindPopup(popupHtml, {
          maxWidth: 340,
          minWidth: 320,
          ...popupPanPadding(),
          className: 'map-blok-popup-wrapper',
          closeOnClick: false,
          autoClose: true,
        })
        bindPopupInteractions(leafletLayer, feature as Feature)
      },
    })

    geoJsonLayer.value = layer
    if (showBlocks.value)
      geoJsonLayer.value.addTo(map.value)

    const bounds = geoJsonLayer.value.getBounds()

    if (bounds.isValid()) {
      map.value.fitBounds(bounds, fitPaddingOptions())
    }
    else {
      map.value.setView(defaultCenter, defaultZoom)
    }
  }
  finally {
    isLayerUpdating.value = false
  }
}

// ===========================================================================
// PETA DASAR
// ===========================================================================

const BASEMAP_STORAGE_KEY = 'map-basemap'
const basemap = shallowRef<BasemapKey>(DEFAULT_BASEMAP)
let basemapLayers: import('leaflet').TileLayer[] = []

function readSavedBasemap(): BasemapKey {
  try {
    const saved = localStorage.getItem(BASEMAP_STORAGE_KEY) as BasemapKey | null
    return saved && BASEMAPS.some(option => option.key === saved) ? saved : DEFAULT_BASEMAP
  }
  catch {
    return DEFAULT_BASEMAP
  }
}

function applyBasemap(key: BasemapKey) {
  const L = leafletModule.value
  if (!L || !map.value)
    return
  const option = BASEMAPS.find(item => item.key === key) ?? BASEMAPS[0]!
  basemapLayers.forEach(layer => layer.removeFrom(map.value!))
  basemapLayers = option.tiles.map(tile => L.tileLayer(tile.url, {
    attribution: tile.attribution,
    maxZoom: tile.maxZoom ?? 19,
    ...(tile.subdomains ? { subdomains: tile.subdomains } : {}),
  }).addTo(map.value!))
  basemap.value = option.key
  try {
    localStorage.setItem(BASEMAP_STORAGE_KEY, option.key)
  }
  catch {
    // penyimpanan lokal tidak tersedia (mode privat) -> abaikan
  }
}

// ===========================================================================
// LAYER DATA TAMBAHAN (dari katalog backend)
// ===========================================================================

type CatalogItem = {
  kode: string
  nama: string
  geometry_type: string
  handler_type: string
  endpoints: Record<string, string> | null
}

type OverlayState = OverlayListItem & { endpoint: string, style: OverlayStyle }

const overlays = ref<OverlayState[]>([])
const overlayLayers = new Map<string, import('leaflet').Layer>()
const overlaySequence = new Map<string, number>()
let pointRenderer: import('leaflet').Canvas | null = null

const overlayPanelItems = computed<OverlayListItem[]>(() => overlays.value.map(({ endpoint: _e, style: _s, ...item }) => item))

function getApiBaseUrl() {
  return useRuntimeConfig().public.apiBaseUrlPython as string
}

function overlayRank(code: string) {
  const index = OVERLAY_ORDER.indexOf(code)
  return index < 0 ? OVERLAY_ORDER.length : index // layer dinamis baru di akhir
}

async function loadCatalog() {
  try {
    const { $api } = useNuxtApp()
    const catalog = await $api<CatalogItem[]>(`${getApiBaseUrl()}/v1/spatial/geo/catalog`)
    overlays.value = (Array.isArray(catalog) ? catalog : [])
      .filter(item => item.kode !== 'blok' && item.endpoints?.geojson)
      .map((item, index) => {
        const style = getOverlayStyle(item.kode, index)
        return {
          code: item.kode,
          name: OVERLAY_LABELS[item.kode] ?? item.nama,
          geometryType: item.geometry_type,
          color: style.defaultColor,
          enabled: false,
          loading: false,
          count: null,
          period: '',
          error: '',
          legend: getOverlayLegend(style),
          endpoint: item.endpoints!.geojson!,
          style,
        }
      })
      .sort((a, b) => overlayRank(a.code) - overlayRank(b.code))
  }
  catch {
    overlays.value = []
  }
}

function overlayQuery() {
  const filters = mapStore.filters
  const query = new URLSearchParams()
  if (filters.pt) query.set('kode_pt', filters.pt)
  if (filters.estate) query.set('kode_est', filters.estate)
  if (filters.afdeling) query.set('kode_afd', filters.afdeling)
  if (filters.blok) {
    query.set('kode_blok', filters.blok)
    query.set('blok_id', filters.blok) // endpoint layer dinamis memakai nama ini
  }
  return query.toString()
}

function escapeHtml(value: unknown) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&#39;' }[ch]!))
}

function formatValue(value: unknown) {
  if (typeof value === 'number')
    return Number.isInteger(value) ? String(value) : value.toLocaleString('id-ID', { maximumFractionDigits: 2 })
  return escapeHtml(value)
}

function buildOverlayPopup(overlay: OverlayState, properties: Record<string, unknown>) {
  const fields = overlay.style.popupFields.length
    ? overlay.style.popupFields
    : Object.keys(properties)
        .filter(key => !['id', 'blok_id', 'bulan', 'tahun'].includes(key) && typeof properties[key] !== 'object')
        .map(key => [key, key.replace(/_/g, ' ')] as [string, string])
  const rows = fields
    .filter(([key]) => properties[key] !== null && properties[key] !== undefined && properties[key] !== '')
    .map(([key, label]) => `<tr><td class="ovl-k">${escapeHtml(label)}</td><td class="ovl-v">${formatValue(properties[key])}</td></tr>`)
    .join('')
  const period = properties.bulan && properties.tahun ? `<span class="ovl-period">${properties.bulan}-${properties.tahun}</span>` : ''
  return `<div class="ovl-popup"><div class="ovl-title"><span class="ovl-dot" style="background:${overlay.color}"></span>${escapeHtml(overlay.name)}${period}</div><table>${rows}</table></div>`
}

function buildOverlayLayer(L: LeafletModule, overlay: OverlayState, data: FeatureCollection) {
  const style = overlay.style
  const pane = overlay.geometryType.includes('POINT') ? POINT_PANE : overlay.geometryType.includes('LINE') ? LINE_PANE : POLYGON_PANE
  return L.geoJSON(data, {
    pane,
    style: feature => ({
      color: overlay.geometryType.includes('LINE') ? getOverlayColor(style, feature?.properties) : '#1e293b',
      weight: style.weight ?? 1,
      fillColor: getOverlayColor(style, feature?.properties),
      fillOpacity: style.fillOpacity ?? 0.5,
      opacity: 0.95,
    }),
    pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
      renderer: pointRenderer ?? undefined,
      pane: POINT_PANE,
      radius: style.radius ?? 5,
      color: overlay.code === 'jembatan' ? '#0c4a6e' : '#ffffff',
      weight: overlay.code === 'sawit' ? 0.4 : 1.2,
      fillColor: getOverlayColor(style, feature.properties),
      fillOpacity: 0.95,
    }),
    onEachFeature: (feature, layer) => {
      layer.bindPopup(() => buildOverlayPopup(overlay, (feature.properties ?? {}) as Record<string, unknown>), {
        className: 'map-overlay-popup',
        maxWidth: 280,
        ...popupPanPadding(),
      })
    },
  })
}

async function loadOverlay(overlay: OverlayState) {
  const L = leafletModule.value
  if (!L || !map.value)
    return
  const sequence = (overlaySequence.get(overlay.code) ?? 0) + 1
  overlaySequence.set(overlay.code, sequence)
  overlay.loading = true
  overlay.error = ''
  try {
    const { $api } = useNuxtApp()
    const query = overlayQuery()
    const data = await $api<FeatureCollection>(`${getApiBaseUrl()}/v1/spatial${overlay.endpoint}${query ? `?${query}` : ''}`)
    if (overlaySequence.get(overlay.code) !== sequence || !overlay.enabled)
      return
    removeOverlayLayer(overlay.code)
    const features = Array.isArray(data?.features) ? data.features : []
    const layer = buildOverlayLayer(L, overlay, { type: 'FeatureCollection', features })
    layer.addTo(map.value)
    overlayLayers.set(overlay.code, layer)
    overlay.count = features.length
    const first = features[0]?.properties as Record<string, unknown> | undefined
    overlay.period = first?.bulan && first?.tahun ? `${getBulanPopupLabel(String(first.bulan))} ${first.tahun}` : ''
  }
  catch (error) {
    if (overlaySequence.get(overlay.code) !== sequence)
      return
    overlay.count = null
    overlay.error = getErrorStatus(error) === 403 ? 'Tidak punya akses ke layer ini.' : 'Gagal memuat layer.'
  }
  finally {
    if (overlaySequence.get(overlay.code) === sequence)
      overlay.loading = false
  }
}

function removeOverlayLayer(code: string) {
  const existing = overlayLayers.get(code)
  if (existing && map.value)
    existing.removeFrom(map.value)
  overlayLayers.delete(code)
}

function toggleOverlay(code: string) {
  const overlay = overlays.value.find(item => item.code === code)
  if (!overlay)
    return
  overlay.enabled = !overlay.enabled
  if (overlay.enabled) {
    void loadOverlay(overlay)
  }
  else {
    overlaySequence.set(code, (overlaySequence.get(code) ?? 0) + 1) // batalkan request yang sedang jalan
    overlay.loading = false
    removeOverlayLayer(code)
  }
}

function reloadEnabledOverlays() {
  overlays.value.filter(item => item.enabled).forEach(item => void loadOverlay(item))
}

const showBlocks = shallowRef(true)

function toggleBlocks() {
  showBlocks.value = !showBlocks.value
  if (!map.value || !geoJsonLayer.value)
    return
  if (showBlocks.value)
    geoJsonLayer.value.addTo(map.value)
  else
    geoJsonLayer.value.removeFrom(map.value)
}

// ===========================================================================
// INISIALISASI
// ===========================================================================

function createPanes() {
  if (!map.value)
    return
  const panes: Array<[string, number]> = [[BLOCK_PANE, 410], [POLYGON_PANE, 420], [LINE_PANE, 430], [POINT_PANE, 440]]
  for (const [name, zIndex] of panes) {
    const pane = map.value.createPane(name)
    pane.style.zIndex = String(zIndex)
  }
}

function applyInsets() {
  // Atribusi peta harus tetap terlihat walau sudut kanan bawah tertutup panel profil.
  const corner = mapContainer.value?.querySelector('.leaflet-bottom.leaflet-right') as HTMLElement | null
  if (corner)
    corner.style.marginRight = `${props.insets.right}px`
  map.value?.invalidateSize()
}

async function initializeMap() {
  const L = await import('leaflet')
  leafletModule.value = L

  if (!mapContainer.value)
    return

  map.value = L.map(mapContainer.value, {
    closePopupOnClick: false,
    preferCanvas: false,
  }).setView(defaultCenter, defaultZoom)

  createPanes()
  pointRenderer = L.canvas({ pane: POINT_PANE, padding: 0.5 })
  applyBasemap(readSavedBasemap())
  L.control.scale({ position: 'bottomright', imperial: false }).addTo(map.value)

  isMapReady.value = true

  setTimeout(() => {
    applyInsets()
  }, 0)

  updateGeoJSONLayer(L)
  await loadCatalog()
}

const featureCount = computed(() => {
  const data = getRenderableFeatureCollection()
  return data.features.length
})

const visibleCenterStyle = computed(() => ({
  left: `calc(${props.insets.left}px + (100% - ${props.insets.left + props.insets.right}px) / 2)`,
}))

onMounted(async () => {
  await initializeMap()
})

onBeforeUnmount(() => {
  if (geoJsonLayer.value && map.value) {
    geoJsonLayer.value.removeFrom(map.value)
    geoJsonLayer.value = null
  }
  overlayLayers.forEach((_, code) => removeOverlayLayer(code))

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
    reloadEnabledOverlays()
  },
  { deep: true },
)

watch(() => props.insets, () => applyInsets(), { deep: true })
</script>

<template>
  <div class="relative h-full w-full">
    <div ref="mapContainer" class="h-full w-full" />

    <div class="pointer-events-none absolute top-3 z-[1000]" :style="{ right: `${insets.right + 12}px` }">
      <MapLayerPanel :basemap="basemap" :overlays="overlayPanelItems" :block-count="featureCount"
        :show-blocks="showBlocks" @update:basemap="applyBasemap" @toggle-overlay="toggleOverlay"
        @toggle-blocks="toggleBlocks" />
    </div>

    <div v-if="mapStore.loadingGeoJSON"
      class="absolute inset-0 z-[1100] flex items-center justify-center bg-surface-70 backdrop-blur-[1px]">
      <div class="flex flex-col items-center gap-3 rounded-xl bg-surface px-5 py-4 shadow-lg">
        <div class="h-8 w-8 animate-spin rounded-full border-[3px] border-blue-primary border-t-transparent" />
        <p class="text-13 font-medium text-slate">
          Memuat data peta...
        </p>
      </div>
    </div>

    <div class="absolute bottom-4 z-[1000] -translate-x-1/2 rounded-lg bg-surface-90 px-3 py-2 text-size-sm shadow-md"
      :style="visibleCenterStyle">
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

.leaflet-popup.map-overlay-popup .leaflet-popup-content-wrapper {
  border-radius: 10px;
}

.leaflet-popup.map-overlay-popup .leaflet-popup-content {
  margin: 10px 12px;
  font-size: 12px;
}

.ovl-popup .ovl-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #1f2937;
  padding-right: 18px; /* ruang untuk tombol tutup popup */
}

.ovl-popup .ovl-dot {
  width: 10px;
  height: 10px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.ovl-popup .ovl-period {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  color: #6b7280;
}

.ovl-popup table {
  width: 100%;
  border-collapse: collapse;
}

.ovl-popup td {
  padding: 2px 0;
  vertical-align: top;
}

.ovl-popup .ovl-k {
  color: #6b7280;
  padding-right: 10px;
  white-space: nowrap;
}

.ovl-popup .ovl-v {
  color: #111827;
  font-weight: 600;
  text-align: right;
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
