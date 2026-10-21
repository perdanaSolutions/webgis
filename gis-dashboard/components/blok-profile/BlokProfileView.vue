<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";

import "~/assets/css/blok-profile.css";
import AreaStatementCard from "~/components/blok-profile/AreaStatementCard.vue";
import BlockInfoCard from "~/components/blok-profile/BlockInfoCard.vue";
import BlokProfileMap from "~/components/blok-profile/BlokProfileMap.vue";
import BlokProfilePrintSheet from "~/components/blok-profile/BlokProfilePrintSheet.vue";
import FilterPanel from "~/components/blok-profile/FilterPanel.vue";
import ProductionChartCard from "~/components/blok-profile/ProductionChartCard.vue";
import ProductionGapCard from "~/components/blok-profile/ProductionGapCard.vue";
import RotationCard from "~/components/blok-profile/RotationCard.vue";
import SlopeInfoCard from "~/components/blok-profile/SlopeInfoCard.vue";
import Header from "~/components/Header.vue";
import { useMapOverlays } from "~/composables/useMapOverlays";
import { useAuthStore } from "~/stores/authStore";
import { useBlokProfileStore } from "~/stores/blokProfileStore";
import { dashboardStore } from "~/stores/dashboardStore";
import BasemapAccessDialog from "~/components/map/BasemapAccessDialog.vue";
import { basemapAccessMessage, basemapHost, type BasemapStatus } from "~/utils/mapBasemap";
import { BASEMAPS, BUDGET_GAP_LAYERS, type BasemapKey, type BudgetGapKey, SLOPE_RAMP } from "~/utils/mapLayers";
import { exportBlokProfilePdf } from "~/utils/exportBlokProfilePdf";
import { installMapCacheSchema } from "~/utils/mapCacheSchema";
import { isAccessTokenExpired } from "~/utils/authSession";

defineOptions({ name: "BlokProfileView" });

const authStore = useAuthStore();
const dashboardService = dashboardStore();
const store = useBlokProfileStore();
const route = useRoute();

const overlays = useMapOverlays(computed(() => ({ ...store.scopeParams })));
const layers = overlays.layers;

const mapRef = shallowRef<InstanceType<typeof BlokProfileMap> | null>(null);
const printSheetRef = ref<{ sections: () => HTMLElement[] } | null>(null);
const loaderRef = ref<HTMLElement | null>(null);
const exporting = ref(false);
const exportStatus = ref("Menyiapkan peta…");
const exportError = ref("");
let exportOverflow = "";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

// ------------------------------------------------------------------ header
const activeModule = computed(() =>
  dashboardService.flatModuleItems.find((item) => item.to && (route.path === item.to || route.path.startsWith(`${item.to}/`))) ?? null,
);
const headerBrandTitle = computed(() => dashboardService.dashboardConfig.brandTitle);
const headerBrandSubtitle = computed(() => activeModule.value?.description || dashboardService.dashboardConfig.brandSubtitle);
const pageTitle = computed(() => activeModule.value?.title || "Blok Profile");

// ------------------------------------------------------------------ preferensi tampilan
const BASEMAP_KEY = "blok-profile-basemap";
const basemap = ref<BasemapKey>("satellite");
let acceptedBasemap: BasemapKey = "satellite";
let basemapRevert = false;
const basemapNotice = ref<{ title: string; body: string; pending: boolean } | null>(null);

function onBasemapStatus(status: BasemapStatus) {
  const option = BASEMAPS.find((item) => item.key === basemap.value);
  if (status === "ready") {
    acceptedBasemap = basemap.value;
    if (basemapRevert) {
      basemapRevert = false;
      return;
    }
    basemapNotice.value = null;
    return;
  }
  if (!option) return;
  if (status === "checking") {
    basemapNotice.value = {
      title: "Memeriksa foto udara",
      body: `Sedang memeriksa apakah jaringan mengizinkan akses ke server ${option.label} (${basemapHost(option)}).`,
      pending: true,
    };
    return;
  }
  if (status === "blocked") {
    basemapNotice.value = { ...basemapAccessMessage("blocked", option), pending: false };
    if (basemap.value !== acceptedBasemap) {
      basemapRevert = true;
      basemap.value = acceptedBasemap;
    }
    return;
  }
  basemapNotice.value = { ...basemapAccessMessage("unavailable", option), pending: false };
  acceptedBasemap = basemap.value;
}
const opacity = ref(80);
const showBlocks = ref(true);
const showYieldGap = ref(false);
const yieldComparisonOn = computed(() => Boolean(store.bulanComparison && store.tahunComparison));
const budgetColors = ref<Record<BudgetGapKey, boolean>>({
  OPTIMUM: true,
  "GAP I": true,
  "GAP II": true,
  "GAP III": true,
});

type LeftKey = "filter" | "layer" | "basemap";
type RightKey = "info" | "produksi" | "slope" | "area" | "rotasi";

const activeLeft = ref<LeftKey | null>(null);
const activeRight = ref<RightKey | null>(null);

watch(basemap, (value) => {
  try { localStorage.setItem(BASEMAP_KEY, value); } catch { /* mode privat */ }
});

// ------------------------------------------------------------------ tata letak
const isDesktop = ref(false);
const isMobile = ref(false);
const online = ref(true);
const stageRef = ref<HTMLElement | null>(null);
const stageW = ref(0);

let mqDesktop: MediaQueryList | null = null;
let mqMobile: MediaQueryList | null = null;
let stageObserver: ResizeObserver | null = null;

const LEFT_W = 340;
const RIGHT_W = 380;
const EDGE = 12;

function measureStage() {
  stageW.value = stageRef.value?.clientWidth ?? window.innerWidth;
}

function syncLayout() {
  const wasMobile = isMobile.value;
  isDesktop.value = !!mqDesktop?.matches;
  isMobile.value = !!mqMobile?.matches;
  measureStage();
  if (isMobile.value && !wasMobile && activeLeft.value && activeRight.value) activeRight.value = null;
}

function openLeft(key: LeftKey) {
  activeLeft.value = activeLeft.value === key ? null : key;
  if (activeLeft.value && !isDesktop.value) activeRight.value = null;
}

function openRight(key: RightKey) {
  activeRight.value = activeRight.value === key ? null : key;
  if (activeRight.value && !isDesktop.value) activeLeft.value = null;
}

function closePanels() {
  activeLeft.value = null;
  activeRight.value = null;
}

const isFullscreen = ref(false);
const pseudoFullscreen = ref(false);

type FullscreenDocument = Document & {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => Promise<void> | void;
};

type FullscreenHost = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void> | void;
};

function nativeFullscreenElement() {
  const doc = document as FullscreenDocument;
  return document.fullscreenElement ?? doc.webkitFullscreenElement ?? null;
}

function refreshMapSize() {
  nextTick(() => {
    measureStage();
    mapRef.value?.invalidateSize();
    window.setTimeout(() => mapRef.value?.invalidateSize(), 80);
  });
}

function onFullscreenChange() {
  const native = nativeFullscreenElement() === stageRef.value;
  if (!native) pseudoFullscreen.value = false;
  isFullscreen.value = native || pseudoFullscreen.value;
  refreshMapSize();
}

async function enterFullscreen() {
  const el = stageRef.value as FullscreenHost | null;
  if (!el) return;
  try {
    if (typeof el.requestFullscreen === "function") {
      await el.requestFullscreen();
      return;
    }
    if (typeof el.webkitRequestFullscreen === "function") {
      await el.webkitRequestFullscreen();
      return;
    }
  } catch {
    /* API ditolak browser — sembunyikan header dan perbesar area peta */
  }
  pseudoFullscreen.value = true;
  isFullscreen.value = true;
  refreshMapSize();
}

async function exitFullscreen() {
  pseudoFullscreen.value = false;
  const doc = document as FullscreenDocument;
  try {
    if (nativeFullscreenElement()) {
      if (document.exitFullscreen) await document.exitFullscreen();
      else await doc.webkitExitFullscreen?.();
      return;
    }
  } catch {
    /* lanjut menutup mode cadangan */
  }
  isFullscreen.value = false;
  refreshMapSize();
}

async function toggleFullscreen() {
  if (isFullscreen.value) await exitFullscreen();
  else await enterFullscreen();
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== "Escape") return;
  if (pseudoFullscreen.value) {
    event.preventDefault();
    void exitFullscreen();
    return;
  }
  if (nativeFullscreenElement() === stageRef.value) return;
  closePanels();
}

function syncOnline() {
  online.value = navigator.onLine;
}

function panelWidth(max: number) {
  if (isMobile.value) return Math.max(0, stageW.value - EDGE * 2);
  return Math.min(max, Math.max(0, stageW.value - EDGE * 2));
}

/** Bagian peta yang tertutup panel -> dipakai untuk zoom-to-fit. Kontrol pojok tidak memakai bar ringkasan. */
const mapInsets = computed(() => {
  const bottom = 16;
  const pill = isMobile.value ? 0 : 200;
  const left = activeLeft.value ? EDGE + panelWidth(LEFT_W) + pill : 16;
  const right = activeRight.value ? EDGE + panelWidth(RIGHT_W) + pill : 72;
  return { top: 16, left, right, bottom };
});

const emptyFeatures: GeoJSON.Feature[] = [];
const slopeLayer = computed(() => layers.value.find((layer) => layer.code === "slope") ?? null);
const slopeLayerOn = computed(() => Boolean(slopeLayer.value?.enabled));

watch(slopeLayerOn, (on) => {
  if (!on && activeRight.value === "slope") activeRight.value = null;
});

// ------------------------------------------------------------------ aksi
function onSelectBlock(id: string) {
  if (!id || store.blokId === id) return;
  void store.selectBlock(id, "map");
}

function onDeselectBlock() {
  const before = store.blokId;
  mapRef.value?.suppressNextPan();
  store.restoreLastSearch();
  if (store.blokId === before) mapRef.value?.releasePanSkip();
}

function resetMapLayers() {
  showBlocks.value = true;
  showYieldGap.value = false;
  overlays.disableAll();
}

async function onResetFilters() {
  resetMapLayers();
  await store.reset();
}

const pdfFilterLine = computed(() => {
  const filter = store.summary.filter;
  const ownership = store.ownershipOptions.find((item) => item.value === store.ownership)?.label || "Semua";
  const ytdEnd = store.tahun === String(new Date().getFullYear()) ? new Date().getMonth() : 11;
  const month = store.bulan
    ? MONTHS[Number(store.bulan) - 1] ?? store.bulan
    : store.yearToDate
      ? `Jan s/d ${MONTHS[ytdEnd]}`
      : "Semua bulan";
  const year = store.tahun || String(new Date().getFullYear());
  return `Grup ${filter.grup} · PT ${filter.pt} · Estate ${filter.estate} · Afdeling ${filter.afdeling} · Blok ${filter.blok} · ${ownership} · ${month} ${year}`;
});

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitForExportData() {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    const slope = layers.value.find((layer) => layer.code === "slope");
    const busy = layers.value.some((layer) => layer.enabled && layer.loading)
      || store.loadingBlocks
      || (!!store.blokId && store.loadingDetail)
      || (store.canViewProduction && store.loadingProduction)
      || (store.canViewAreaStatement && store.loadingAreaStatement)
      || (store.canViewRotation && store.loadingRotation)
      || Boolean(slope?.enabled && slope.loading);
    if (!busy) return;
    await sleep(150);
  }
}

function closeExportError() {
  document.documentElement.style.overflow = exportOverflow;
  exportError.value = "";
  exporting.value = false;
}

function onExportKeydown(event: KeyboardEvent) {
  if (!exporting.value) return;
  if (exportError.value) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeExportError();
    }
    return;
  }
  event.preventDefault();
  event.stopPropagation();
}

async function downloadPdf() {
  if (exporting.value) return;
  exporting.value = true;
  exportError.value = "";
  exportStatus.value = "Menunggu data peta…";
  exportOverflow = document.documentElement.style.overflow;
  document.documentElement.style.overflow = "hidden";
  await nextTick();
  loaderRef.value?.focus();
  try {
    await waitForExportData();
    await nextTick();
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    exportStatus.value = "Menggambar peta dan informasi…";
    await exportBlokProfilePdf({
      scopeLabel: store.scopeLabel,
      filterLine: pdfFilterLine.value,
      printedAt: new Date().toLocaleString("id-ID"),
      basemap: basemap.value,
      showBlocks: showBlocks.value,
      showYieldGap: showYieldGap.value,
      budgetColors: { ...budgetColors.value },
      selectedId: store.blokId,
      blocks: showBlocks.value ? store.visibleBlocks : null,
      overlays: layers.value.filter((layer) => layer.enabled && layer.data).map((layer) => ({
        code: layer.code,
        name: layer.name,
        geometryType: layer.geometryType,
        style: layer.style,
        legend: layer.legend,
        data: layer.data!,
      })),
      sections: printSheetRef.value?.sections() ?? [],
      onStatus: (message) => { exportStatus.value = message; },
    });
  } catch (error) {
    console.error(error);
    exportError.value = "PDF gagal dibuat. Periksa koneksi, lalu coba lagi.";
  } finally {
    if (!exportError.value) {
      document.documentElement.style.overflow = exportOverflow;
      exporting.value = false;
    }
  }
}

onMounted(async () => {
  void installMapCacheSchema();
  syncOnline();
  window.addEventListener("online", syncOnline);
  window.addEventListener("offline", syncOnline);
  store.resetFilters();
  mqDesktop = window.matchMedia("(min-width: 1280px)");
  mqMobile = window.matchMedia("(max-width: 767px)");
  syncLayout();
  mqDesktop.addEventListener("change", syncLayout);
  mqMobile.addEventListener("change", syncLayout);
  window.addEventListener("keydown", onKeydown);
  window.addEventListener("keydown", onExportKeydown, true);
  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("webkitfullscreenchange", onFullscreenChange);
  if (stageRef.value && typeof ResizeObserver !== "undefined") {
    stageObserver = new ResizeObserver(() => syncLayout());
    stageObserver.observe(stageRef.value);
  }
  try {
    const saved = localStorage.getItem(BASEMAP_KEY) as BasemapKey | null;
    if (saved && BASEMAPS.some((b) => b.key === saved)) basemap.value = saved;
  } catch { /* abaikan */ }

  if (!authStore.token || isAccessTokenExpired(authStore.token)) {
    window.location.replace("/login");
    return;
  }
  const session = await authStore.ensureSession();
  if (!session) {
    window.location.replace("/login");
    return;
  }
  if (!dashboardService.moduleItems.length) void dashboardService.initDataMenu();
  await Promise.all([store.init(), overlays.loadCatalog()]);
});

onBeforeUnmount(() => {
  if (exporting.value) document.documentElement.style.overflow = exportOverflow;
  mqDesktop?.removeEventListener("change", syncLayout);
  mqMobile?.removeEventListener("change", syncLayout);
  window.removeEventListener("keydown", onKeydown);
  window.removeEventListener("keydown", onExportKeydown, true);
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  document.removeEventListener("webkitfullscreenchange", onFullscreenChange);
  if (nativeFullscreenElement() === stageRef.value) void document.exitFullscreen?.();
  window.removeEventListener("online", syncOnline);
  window.removeEventListener("offline", syncOnline);
  stageObserver?.disconnect();
});
</script>

<template>
  <main class="bp-map-shell flex min-h-0 flex-col overflow-hidden bg-[#f4f6f1] text-14 text-[#1f2a18]">
    <div v-show="!isFullscreen" class="contents">
      <Header :brand-title="headerBrandTitle" :brand-subtitle="headerBrandSubtitle" />

      <!-- PAGE HEADER -->
      <div
        class="bp-map-chrome flex shrink-0 items-center justify-between gap-2 border-b border-[#d5dcc8] bg-white px-3 py-1.5 sm:px-4 lg:px-6">
        <div class="min-w-0">
          <nav class="hidden text-11 leading-none text-[#6e7866] sm:block" aria-label="Breadcrumb">
            <NuxtLink to="/dashboard" class="hover:underline">Beranda</NuxtLink>
            <span class="mx-1">/</span>
            <span>{{ pageTitle }}</span>
          </nav>
          <div class="flex min-w-0 items-baseline gap-x-2 sm:mt-0.5">
            <h1 class="truncate text-base font-bold leading-none tracking-tight text-[#1f2a18] sm:text-lg">{{ pageTitle
            }}
            </h1>
            <p class="hidden min-w-0 truncate text-12 leading-none text-[#6e7866] md:block">Tampilan peta layar penuh ·
              scope: {{ store.scopeLabel }}</p>
          </div>
        </div>
        <div class="flex shrink-0 items-center gap-1.5">
          <button type="button" class="bp-btn max-sm:w-9 max-sm:justify-center max-sm:px-0"
            title="Unduh peta dan informasi panel sebagai PDF" aria-label="Unduh peta" :disabled="exporting"
            :aria-busy="exporting" @click="downloadPdf">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8"
              aria-hidden="true">
              <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" />
            </svg>
            <span class="hidden sm:inline">Unduh Peta</span>
          </button>
          <NuxtLink to="/document" class="bp-btn bp-btn-primary max-sm:w-9 max-sm:justify-center max-sm:px-0"
            aria-label="Tambah blok">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"
              aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
            <span class="hidden sm:inline">Tambah Blok</span>
          </NuxtLink>
        </div>
      </div>
    </div>

    <div id="bp-map-stage" ref="stageRef" class="bp-stage relative min-h-0 flex-1 overflow-hidden">
      <!-- PETA -->
      <section class="absolute inset-0 z-0">
        <BlokProfileMap ref="mapRef" :blocks="store.visibleBlocks" :selected-id="store.blokId" :show-blocks="showBlocks"
          :show-yield-gap="showYieldGap" :overlays="layers" :basemap="basemap" :opacity="opacity / 100"
          :budget-colors="budgetColors" :insets="mapInsets" :request-detail="store.loadPopupDetail"
          :popup-period="store.popupPeriod" @select="onSelectBlock" @deselect="onDeselectBlock"
          @basemap-status="onBasemapStatus" />

        <div v-if="store.statusNotice"
          class="pointer-events-none absolute left-1/2 top-4 z-[1200] flex max-w-[calc(100%-6rem)] -translate-x-1/2 items-center gap-2 truncate rounded-full px-4 py-2 text-13 font-medium shadow-lg"
          :class="{
            'bg-white/95 text-[#1f2a18]': store.statusNotice.kind === 'loading',
            'bg-[#e8f5df] text-[#3f6b24]': store.statusNotice.kind === 'success',
            'bg-[#fdecea] text-[#b42318]': store.statusNotice.kind === 'error',
          }" role="status" aria-live="polite">
          <span v-if="store.statusNotice.kind === 'loading'"
            class="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-[#638840] border-t-transparent"
            aria-hidden="true" />
          <span class="truncate">{{ store.statusNotice.message }}</span>
        </div>
        <div v-else-if="!online"
          class="pointer-events-none absolute left-1/2 top-4 z-[1200] max-w-[calc(100%-6rem)] -translate-x-1/2 truncate rounded-full bg-white/95 px-4 py-2 text-13 shadow-lg"
          role="status">
          Tanpa jaringan. Menampilkan data peta terakhir yang tersimpan di perangkat ini.
        </div>
        <div v-else-if="!store.blockFeatures.length && store.area && !store.loadingBlocks"
          class="pointer-events-none absolute left-1/2 top-4 z-[1200] max-w-[calc(100%-6rem)] -translate-x-1/2 truncate rounded-full bg-white/95 px-4 py-2 text-13 shadow-lg">
          Belum ada batas blok untuk scope ini.
        </div>

        <!-- Legenda + zoom: pojok kanan bawah -->
        <div v-show="!(isMobile && (activeLeft || activeRight))"
          class="bp-controls absolute z-[1350] flex max-w-[calc(100%-8rem)] flex-col items-end gap-2 sm:flex-row sm:items-end">
          <div v-if="showYieldGap" class="bp-card px-3 py-2 sm:px-4 sm:py-3">
            <p class="mb-2 text-11 font-bold uppercase tracking-[0.1em] text-[#6e7866]">Yield Gap</p>
            <p v-if="yieldComparisonOn" class="mb-2 max-w-56 text-11 leading-snug text-[#6e7866]">
              Isi blok mengikuti periode. Titik di tengah mengikuti pembanding.
            </p>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <span v-for="item in BUDGET_GAP_LAYERS" :key="item.key"
                class="inline-flex items-center gap-2 text-12 text-[#1f2a18] sm:text-13">
                <span class="h-3 w-3 rounded-[3px] ring-1 ring-black/10" :style="{ background: item.color }" />{{
                  item.label }}
              </span>
            </div>
          </div>
          <div v-if="slopeLayerOn" class="bp-card px-3 py-2 sm:px-4 sm:py-3">
            <p class="mb-2 text-11 font-bold uppercase tracking-[0.1em] text-[#6e7866]">Kelas Kemiringan</p>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <span v-for="(color, range) in SLOPE_RAMP" :key="range"
                class="inline-flex items-center gap-2 text-12 text-[#1f2a18] sm:text-13">
                <span class="h-3 w-3 rounded-[3px] ring-1 ring-black/10" :style="{ background: color }" />{{ range }}%
              </span>
            </div>
          </div>
          <div class="flex flex-col items-end gap-2">
            <button type="button"
              class="bp-card flex h-11 w-11 items-center justify-center !rounded-2xl hover:bg-[#eef3e7] sm:h-12 sm:w-12"
              :aria-label="isFullscreen ? 'Keluar layar penuh' : 'Layar penuh'"
              :title="isFullscreen ? 'Keluar layar penuh' : 'Layar penuh'" :aria-pressed="isFullscreen"
              @click="toggleFullscreen">
              <svg v-if="!isFullscreen" viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor"
                stroke-width="2" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 9V4h5M15 4h5v5M4 15v5h5M20 15v5h-5" />
              </svg>
              <svg v-else viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"
                aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
              </svg>
            </button>
            <div class="bp-card flex overflow-hidden !rounded-2xl">
              <button type="button"
                class="flex h-11 w-11 items-center justify-center hover:bg-[#eef3e7] sm:h-12 sm:w-12"
                aria-label="Perbesar" @click="mapRef?.zoomIn()">
                <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
              <button type="button"
                class="flex h-11 w-11 items-center justify-center border-x border-[#d5dcc8] hover:bg-[#eef3e7] sm:h-12 sm:w-12"
                aria-label="Perkecil" @click="mapRef?.zoomOut()">
                <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M5 12h14" />
                </svg>
              </button>
              <button type="button"
                class="flex h-11 w-11 items-center justify-center hover:bg-[#eef3e7] sm:h-12 sm:w-12"
                aria-label="Fokus ke scope / blok terpilih" @click="mapRef?.fitScope()">
                <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>

      <button v-show="!isDesktop && (activeLeft || activeRight)" type="button"
        class="absolute inset-0 z-[1250] bg-[#1f2a18]/20" aria-label="Tutup panel" @click="closePanels" />

      <!-- TOMBOL COLLAPSE KIRI -->
      <aside v-show="!(isMobile && activeRight)" class="bp-rail bp-rail-left" :class="activeLeft && 'is-open'">
        <div class="bp-rail-pills" role="toolbar" aria-label="Panel kiri">
          <button type="button" class="bp-collapse-btn" :class="activeLeft === 'filter' && 'is-active'"
            :aria-expanded="activeLeft === 'filter'" aria-controls="bp-panel-filter" @click="openLeft('filter')">
            <span>Filter Kebun</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" d="M4 7h10M18 7h2M4 12h4M12 12h8M4 17h12M20 17h0" />
              <circle cx="16" cy="7" r="2" />
              <circle cx="10" cy="12" r="2" />
              <circle cx="18" cy="17" r="2" />
            </svg>
          </button>
          <button type="button" class="bp-collapse-btn" :class="activeLeft === 'layer' && 'is-active'"
            :aria-expanded="activeLeft === 'layer'" aria-controls="bp-panel-layer" @click="openLeft('layer')">
            <span>Layer Data</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linejoin="round" d="m12 3 8 4.5-8 4.5-8-4.5L12 3Zm-8 9 8 4.5 8-4.5M4 16.5 12 21l8-4.5" />
            </svg>
          </button>
          <button type="button" class="bp-collapse-btn" :class="activeLeft === 'basemap' && 'is-active'"
            :aria-expanded="activeLeft === 'basemap'" aria-controls="bp-panel-basemap" @click="openLeft('basemap')">
            <span>Base Map</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linejoin="round" d="m4 6 5-2 6 3 5-2v14l-5 2-6-3-5 2V6Zm5-2v14m6-11v14" />
            </svg>
          </button>
        </div>
        <div v-if="activeLeft" :id="`bp-panel-${activeLeft}`" class="bp-collapse-panel">
          <FilterPanel :section="activeLeft" :group-options="store.groupOptions" :area-options="store.areaOptions"
            :pt-options="store.ptOptions" :estate-options="store.estateOptions"
            :afdeling-options="store.afdelingOptions" :blok-options="store.blokOptions"
            :ownership-options="store.ownershipOptions" :grup="store.grup" :area="store.area" :pt="store.pt"
            :estate="store.estate" :afdeling="store.afdeling" :blok-id="store.blokId" :ownership="store.ownership"
            :bulan="store.bulan" :tahun="store.tahun" :year-to-date="store.yearToDate"
            :bulan-comparison="store.bulanComparison" :tahun-comparison="store.tahunComparison"
            :scope-level="store.scopeLevel" :block-count="store.blockFeatures.length"
            :loading="store.loadingOptions || store.applying || store.loadingBlocks" :layers="layers"
            :show-blocks="showBlocks" :show-yield-gap="showYieldGap" :basemap="basemap" :opacity="opacity"
            :allow-all="store.allowAllScope" :filter-generation="store.filterGeneration" @update:grup="store.setGrup"
            @update:area="store.setArea" @update:pt="store.setPt" @update:estate="store.setEstate"
            @update:afdeling="store.setAfdeling" @update:blok="store.setBlok" @update:ownership="store.setOwnership"
            @update:bulan="store.setBulan" @update:tahun="store.setTahun" @update:year-to-date="store.setYearToDate"
            @update:bulan-comparison="store.setBulanComparison" @update:tahun-comparison="store.setTahunComparison"
            @reset="onResetFilters" @toggle-layer="overlays.toggle" @toggle-blocks="showBlocks = !showBlocks"
            @toggle-yield-gap="showYieldGap = !showYieldGap" @update:basemap="basemap = $event"
            @update:opacity="opacity = $event" />
        </div>
      </aside>

      <!-- TOMBOL COLLAPSE KANAN -->
      <aside v-show="!(isMobile && activeLeft)" class="bp-rail bp-rail-right" :class="activeRight && 'is-open'">
        <div class="bp-rail-pills" role="toolbar" aria-label="Panel kanan">
          <button type="button" class="bp-collapse-btn" :class="activeRight === 'info' && 'is-active'"
            :aria-expanded="activeRight === 'info'" aria-controls="bp-panel-info" @click="openRight('info')">
            <span>Informasi Blok</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <path d="M8 8h8M8 12h8M8 16h5" />
            </svg>
          </button>
          <button v-if="store.canViewProduction" type="button" class="bp-collapse-btn"
            :class="activeRight === 'produksi' && 'is-active'" :aria-expanded="activeRight === 'produksi'"
            aria-controls="bp-panel-produksi" @click="openRight('produksi')">
            <span>Produksi</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" d="M4 19V5M4 19h16" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 15v-3M12 15V8M16 15v-5" />
            </svg>
          </button>
          <button v-if="slopeLayerOn" type="button" class="bp-collapse-btn"
            :class="activeRight === 'slope' && 'is-active'" :aria-expanded="activeRight === 'slope'"
            aria-controls="bp-panel-slope" @click="openRight('slope')">
            <span>Slope Kemiringan</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linejoin="round" d="m3 18 7-9 4 5 7-8" />
              <path stroke-linecap="round" d="M3 21h18" />
            </svg>
          </button>
          <button v-if="store.canViewAreaStatement" type="button" class="bp-collapse-btn"
            :class="activeRight === 'area' && 'is-active'" :aria-expanded="activeRight === 'area'"
            aria-controls="bp-panel-area" @click="openRight('area')">
            <span>Areal Statement</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <path d="M8 8h8M8 12h8M8 16h4" />
              <path d="M4 8h2M4 12h2M4 16h2" />
            </svg>
          </button>
          <button v-if="store.canViewRotation" type="button" class="bp-collapse-btn"
            :class="activeRight === 'rotasi' && 'is-active'" :aria-expanded="activeRight === 'rotasi'"
            aria-controls="bp-panel-rotasi" @click="openRight('rotasi')">
            <span>Rotasi</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20 12a8 8 0 1 1-2.3-5.7L20 8" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M20 4v4h-4" />
            </svg>
          </button>
        </div>

        <div v-if="activeRight === 'info'" id="bp-panel-info" class="bp-collapse-panel">
          <BlockInfoCard :summary="store.summary" :detail="store.detail" :loading="store.loadingDetail" />
        </div>
        <div v-else-if="activeRight === 'produksi'" id="bp-panel-produksi" class="bp-collapse-panel bp-collapse-stack">
          <ProductionChartCard :years="store.productionYears" :loading="store.loadingProduction" />
          <ProductionGapCard :budget="store.productionGapBudget" :sensus="store.productionGapSensus"
            :loading="store.loadingProduction" />
        </div>
        <div v-else-if="activeRight === 'slope' && slopeLayerOn" id="bp-panel-slope" class="bp-collapse-panel">
          <SlopeInfoCard :features="slopeLayer?.data?.features ?? emptyFeatures" :loading="Boolean(slopeLayer?.loading)"
            :error="slopeLayer?.error ?? ''" :period="slopeLayer?.period ?? ''" />
        </div>
        <div v-else-if="activeRight === 'area'" id="bp-panel-area" class="bp-collapse-panel bp-collapse-stack">
          <AreaStatementCard :data="store.areaStatementView" :loading="store.loadingAreaStatement" />
        </div>
        <div v-else-if="activeRight === 'rotasi'" id="bp-panel-rotasi" class="bp-collapse-panel">
          <RotationCard :data="store.rotationView" :loading="store.loadingRotation" />
        </div>
      </aside>
    </div>

    <Teleport to="body">
      <BasemapAccessDialog :open="Boolean(basemapNotice)" :title="basemapNotice?.title ?? ''"
        :body="basemapNotice?.body ?? ''" :pending="basemapNotice?.pending" @close="basemapNotice = null" />
      <BlokProfilePrintSheet v-if="exporting" ref="printSheetRef" :scope-label="store.scopeLabel"
        :filter-line="pdfFilterLine" :summary="store.summary" :detail="store.detail"
        :loading-detail="store.loadingDetail" :can-view-production="store.canViewProduction"
        :production-years="store.productionYears" :production-loading="store.loadingProduction"
        :production-gap-budget="store.productionGapBudget" :production-gap-sensus="store.productionGapSensus"
        :slope-on="slopeLayerOn" :slope-features="slopeLayer?.data?.features ?? emptyFeatures"
        :slope-loading="Boolean(slopeLayer?.loading)" :slope-error="slopeLayer?.error ?? ''"
        :slope-period="slopeLayer?.period ?? ''" :can-view-area="store.canViewAreaStatement"
        :area-statement="store.areaStatementView" :area-loading="store.loadingAreaStatement"
        :can-view-rotation="store.canViewRotation" :rotation="store.rotationView"
        :rotation-loading="store.loadingRotation" />

      <div v-if="exporting" ref="loaderRef" class="bp-pdf-loader" role="alertdialog" aria-modal="true"
        aria-labelledby="bp-pdf-loader-title" tabindex="-1">
        <div class="bp-pdf-loader-panel">
          <span v-if="!exportError" class="bp-pdf-spinner" aria-hidden="true" />
          <h2 id="bp-pdf-loader-title" class="text-16 font-bold text-[#1f2a18]">
            {{ exportError ? "Unduhan gagal" : "Menyiapkan peta" }}
          </h2>
          <p class="max-w-[280px] text-center text-13 leading-snug text-[#55604c]">
            {{ exportError || exportStatus }}
          </p>
          <div v-if="!exportError" class="bp-pdf-bar" aria-hidden="true"><span /></div>
          <button v-else type="button" class="bp-btn mt-1" @click="closeExportError">Tutup</button>
        </div>
      </div>
    </Teleport>
  </main>
</template>
