<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";

import "~/assets/css/blok-profile.css";
import AreaStatementCard from "~/components/blok-profile/AreaStatementCard.vue";
import BlockDetailDrawer from "~/components/blok-profile/BlockDetailDrawer.vue";
import BlockInfoCard from "~/components/blok-profile/BlockInfoCard.vue";
import BlokProfileMap from "~/components/blok-profile/BlokProfileMap.vue";
import FilterPanel from "~/components/blok-profile/FilterPanel.vue";
import ProductionChartCard from "~/components/blok-profile/ProductionChartCard.vue";
import ProductionGapCard from "~/components/blok-profile/ProductionGapCard.vue";
import RotationCard from "~/components/blok-profile/RotationCard.vue";
import SlopeDonutCard from "~/components/blok-profile/SlopeDonutCard.vue";
import SummaryBar from "~/components/blok-profile/SummaryBar.vue";
import Header from "~/components/Header.vue";
import { useMapOverlays } from "~/composables/useMapOverlays";
import { useAuthStore } from "~/stores/authStore";
import { useBlokProfileStore } from "~/stores/blokProfileStore";
import { dashboardStore } from "~/stores/dashboardStore";
import { BASEMAPS, type BasemapKey, type BudgetGapKey, SLOPE_RAMP } from "~/utils/mapLayers";
import { isAccessTokenExpired } from "~/utils/authSession";

defineOptions({ name: "BlokProfilePage" });

const authStore = useAuthStore();
const dashboardService = dashboardStore();
const store = useBlokProfileStore();
const route = useRoute();

const overlays = useMapOverlays(computed(() => ({ ...store.scopeParams })));
const layers = overlays.layers;

const mapRef = shallowRef<InstanceType<typeof BlokProfileMap> | null>(null);

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
const opacity = ref(80);
const showBlocks = ref(true);
const budgetColors = ref<Record<BudgetGapKey, boolean>>({
  OPTIMUM: true,
  "GAP I": true,
  "GAP II": true,
  "GAP III": true,
});

const detailOpen = ref(false);

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
const stageRef = ref<HTMLElement | null>(null);
const stageW = ref(0);

let mqDesktop: MediaQueryList | null = null;
let mqMobile: MediaQueryList | null = null;
let stageObserver: ResizeObserver | null = null;

const GUTTER = 24;
const LEFT_W = 340;
const RIGHT_W = 380;
const BOTTOM_BAR_H = 88;
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

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") closePanels();
}

function panelWidth(max: number) {
  if (isMobile.value) return Math.max(0, stageW.value - EDGE * 2);
  return Math.min(max, Math.max(0, stageW.value - EDGE * 2));
}

/** Bagian peta yang tertutup kartu mengambang -> dipakai untuk zoom-to-fit & posisi kontrol. */
const mapInsets = computed(() => {
  const bottom = isMobile.value ? 72 : GUTTER + BOTTOM_BAR_H;
  const pill = isMobile.value ? 0 : 200;
  const left = activeLeft.value ? EDGE + panelWidth(LEFT_W) + pill : 16;
  const right = activeRight.value ? EDGE + panelWidth(RIGHT_W) + pill : 72;
  return { top: 16, left, right, bottom };
});

const slopeLayerOn = computed(() => layers.value.some((l) => l.code === "slope" && l.enabled));

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

function downloadGeoJSON() {
  const features = [
    ...(showBlocks.value ? store.blockFeatures.map((f) => ({ ...f, properties: { layer: "batas_blok", ...f.properties } })) : []),
    ...layers.value.filter((l) => l.enabled && l.data).flatMap((l) =>
      l.data!.features.map((f) => ({ ...f, properties: { layer: l.code, ...(f.properties ?? {}) } }))),
  ];
  const blob = new Blob([JSON.stringify({ type: "FeatureCollection", features })], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `blok-profile-${store.scopeLabel.replace(/[^\w-]+/g, "_").toLowerCase()}.geojson`;
  link.click();
  URL.revokeObjectURL(url);
}

onMounted(async () => {
  store.resetFilters();
  mqDesktop = window.matchMedia("(min-width: 1280px)");
  mqMobile = window.matchMedia("(max-width: 767px)");
  syncLayout();
  mqDesktop.addEventListener("change", syncLayout);
  mqMobile.addEventListener("change", syncLayout);
  window.addEventListener("keydown", onKeydown);
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
  mqDesktop?.removeEventListener("change", syncLayout);
  mqMobile?.removeEventListener("change", syncLayout);
  window.removeEventListener("keydown", onKeydown);
  stageObserver?.disconnect();
});
</script>

<template>
  <main class="bp-map-shell flex min-h-0 flex-col overflow-hidden bg-[#f4f6f1] text-14 text-[#1f2a18]">
    <Header :brand-title="headerBrandTitle" :brand-subtitle="headerBrandSubtitle" />

    <!-- PAGE HEADER -->
    <div class="flex shrink-0 items-center justify-between gap-2 border-b border-[#d5dcc8] bg-white px-3 py-1.5 sm:px-4 lg:px-6">
      <div class="min-w-0">
        <nav class="hidden text-11 leading-none text-[#6e7866] sm:block" aria-label="Breadcrumb">
          <NuxtLink to="/dashboard" class="hover:underline">Beranda</NuxtLink>
          <span class="mx-1">/</span>
          <span>{{ pageTitle }}</span>
        </nav>
        <div class="flex min-w-0 items-baseline gap-x-2 sm:mt-0.5">
          <h1 class="truncate text-base font-bold leading-none tracking-tight text-[#1f2a18] sm:text-lg">{{ pageTitle }}</h1>
          <p class="hidden min-w-0 truncate text-12 leading-none text-[#6e7866] md:block">Tampilan peta layar penuh · scope: {{ store.scopeLabel }}</p>
        </div>
      </div>
      <div class="flex shrink-0 items-center gap-1.5">
        <button type="button" class="bp-btn max-sm:w-9 max-sm:justify-center max-sm:px-0" title="Unduh batas blok & layer aktif sebagai GeoJSON" aria-label="Unduh peta" @click="downloadGeoJSON">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" />
          </svg>
          <span class="hidden sm:inline">Unduh Peta</span>
        </button>
        <NuxtLink to="/document" class="bp-btn bp-btn-primary max-sm:w-9 max-sm:justify-center max-sm:px-0" aria-label="Tambah blok">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          <span class="hidden sm:inline">Tambah Blok</span>
        </NuxtLink>
      </div>
    </div>

    <div ref="stageRef" class="relative min-h-0 flex-1 overflow-hidden">
      <!-- PETA -->
      <section class="absolute inset-0 z-0">
        <BlokProfileMap ref="mapRef" :blocks="store.visibleBlocks" :selected-id="store.blokId" :show-blocks="showBlocks"
          :overlays="layers" :basemap="basemap" :opacity="opacity / 100" :budget-colors="budgetColors" :insets="mapInsets"
          :request-detail="store.loadSelectedDetail"
          @select="onSelectBlock" @deselect="onDeselectBlock" />

        <div v-if="store.loadingBlocks"
          class="pointer-events-none absolute left-1/2 top-4 z-[1200] max-w-[calc(100%-6rem)] -translate-x-1/2 truncate rounded-full bg-white/95 px-4 py-2 text-13 font-medium shadow-lg">
          Memuat batas blok…
        </div>
        <div v-else-if="!store.blockFeatures.length && store.area"
          class="pointer-events-none absolute left-1/2 top-4 z-[1200] max-w-[calc(100%-6rem)] -translate-x-1/2 truncate rounded-full bg-white/95 px-4 py-2 text-13 shadow-lg">
          Belum ada batas blok untuk scope ini.
        </div>

        <!-- Legenda kelas kemiringan + kontrol peta -->
        <div v-show="!(isMobile && (activeLeft || activeRight))"
          class="bp-controls absolute z-[1350] flex max-w-[calc(100%-5.5rem)] flex-col items-end gap-2 right-4 md:flex-row">
          <div v-if="slopeLayerOn" class="bp-card px-3 py-2 sm:px-4 sm:py-3">
            <p class="mb-2 text-11 font-bold uppercase tracking-[0.1em] text-[#6e7866]">Kelas Kemiringan</p>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <span v-for="(color, range) in SLOPE_RAMP" :key="range" class="inline-flex items-center gap-2 text-12 text-[#1f2a18] sm:text-13">
                <span class="h-3 w-3 rounded-[3px] ring-1 ring-black/10" :style="{ background: color }" />{{ range }}%
              </span>
            </div>
          </div>
          <div class="bp-card flex overflow-hidden !rounded-2xl">
            <button type="button" class="flex h-11 w-11 items-center justify-center hover:bg-[#eef3e7] sm:h-12 sm:w-12" aria-label="Perbesar" @click="mapRef?.zoomIn()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
            </button>
            <button type="button" class="flex h-11 w-11 items-center justify-center border-x border-[#d5dcc8] hover:bg-[#eef3e7] sm:h-12 sm:w-12" aria-label="Perkecil" @click="mapRef?.zoomOut()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14" /></svg>
            </button>
            <button type="button" class="flex h-11 w-11 items-center justify-center hover:bg-[#eef3e7] sm:h-12 sm:w-12" aria-label="Fokus ke scope / blok terpilih" @click="mapRef?.fitScope()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
            </button>
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
              <circle cx="16" cy="7" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="17" r="2" />
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
          <FilterPanel :section="activeLeft" :area-options="store.areaOptions" :pt-options="store.ptOptions" :estate-options="store.estateOptions"
            :afdeling-options="store.afdelingOptions" :blok-options="store.blokOptions"
            :ownership-options="store.ownershipOptions" :tahun-tanam-options="store.tahunTanamOptions"
            :area="store.area" :pt="store.pt" :estate="store.estate" :afdeling="store.afdeling" :blok-id="store.blokId"
            :ownership="store.ownership" :tahun-tanam="store.tahunTanam" :scope-level="store.scopeLevel"
            :block-count="store.blockFeatures.length" :loading="store.loadingOptions || store.loadingBlocks" :layers="layers"
            :show-blocks="showBlocks" :basemap="basemap" :opacity="opacity" :allow-all="store.allowAllScope"
            :filter-generation="store.filterGeneration"
            @update:area="store.setArea" @update:pt="store.setPt" @update:estate="store.setEstate"
            @update:afdeling="store.setAfdeling" @update:blok="store.selectBlock"
            @update:ownership="store.setOwnership" @update:tahun-tanam="store.setTahunTanam"
            @reset="store.reset" @toggle-layer="overlays.toggle"
            @toggle-blocks="showBlocks = !showBlocks"
            @update:basemap="basemap = $event" @update:opacity="opacity = $event" />
        </div>
      </aside>

      <!-- TOMBOL COLLAPSE KANAN -->
      <aside v-show="!(isMobile && activeLeft)" class="bp-rail bp-rail-right" :class="activeRight && 'is-open'">
        <div class="bp-rail-pills" role="toolbar" aria-label="Panel kanan">
          <button type="button" class="bp-collapse-btn" :class="activeRight === 'info' && 'is-active'"
            :aria-expanded="activeRight === 'info'" aria-controls="bp-panel-info" @click="openRight('info')">
            <span>Informasi Blok</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" />
            </svg>
          </button>
          <button v-if="store.canViewProduction" type="button" class="bp-collapse-btn" :class="activeRight === 'produksi' && 'is-active'"
            :aria-expanded="activeRight === 'produksi'" aria-controls="bp-panel-produksi" @click="openRight('produksi')">
            <span>Produksi</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" d="M4 19V5M4 19h16" /><path stroke-linecap="round" stroke-linejoin="round" d="M8 15v-3M12 15V8M16 15v-5" />
            </svg>
          </button>
          <button v-if="store.canViewProduction" type="button" class="bp-collapse-btn" :class="activeRight === 'slope' && 'is-active'"
            :aria-expanded="activeRight === 'slope'" aria-controls="bp-panel-slope" @click="openRight('slope')">
            <span>Slope Kemiringan</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linejoin="round" d="m3 18 7-9 4 5 7-8" /><path stroke-linecap="round" d="M3 21h18" />
            </svg>
          </button>
          <button v-if="store.canViewAreaStatement" type="button" class="bp-collapse-btn" :class="activeRight === 'area' && 'is-active'"
            :aria-expanded="activeRight === 'area'" aria-controls="bp-panel-area" @click="openRight('area')">
            <span>Areal Statement</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h4" /><path d="M4 8h2M4 12h2M4 16h2" />
            </svg>
          </button>
          <button v-if="store.canViewRotation" type="button" class="bp-collapse-btn" :class="activeRight === 'rotasi' && 'is-active'"
            :aria-expanded="activeRight === 'rotasi'" aria-controls="bp-panel-rotasi" @click="openRight('rotasi')">
            <span>Rotasi Pusingan</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20 12a8 8 0 1 1-2.3-5.7L20 8" /><path stroke-linecap="round" stroke-linejoin="round" d="M20 4v4h-4" />
            </svg>
          </button>
        </div>

        <div v-if="activeRight === 'info'" id="bp-panel-info" class="bp-collapse-panel">
          <BlockInfoCard :summary="store.summary" :detail="store.detail" :loading="store.loadingDetail" />
        </div>
        <div v-else-if="activeRight === 'produksi'" id="bp-panel-produksi" class="bp-collapse-panel bp-collapse-stack">
          <ProductionGapCard title="Gap terhadap Budget"
            caption="Varians produksi aktual dibanding budget pada periode terakhir."
            :data="store.productionGapBudget" :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
          <ProductionGapCard title="Gap terhadap Sensus"
            caption="Varians produksi aktual dibanding sensus pada periode terakhir."
            :data="store.productionGapSensus" :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
          <ProductionChartCard :years="store.productionYears"
            :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
        </div>
        <div v-else-if="activeRight === 'slope'" id="bp-panel-slope" class="bp-collapse-panel">
          <SlopeDonutCard :shares="store.slopeShares" :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
        </div>
        <div v-else-if="activeRight === 'area'" id="bp-panel-area" class="bp-collapse-panel">
          <AreaStatementCard :data="store.areaStatementView" :loading="store.blokId ? store.loadingDetail : store.loadingAreaStatement" />
        </div>
        <div v-else-if="activeRight === 'rotasi'" id="bp-panel-rotasi" class="bp-collapse-panel">
          <RotationCard :data="store.rotationView" :loading="store.blokId ? store.loadingDetail : store.loadingRotation" />
        </div>
      </aside>

      <!-- BAR RINGKASAN: sembunyi di mobile, tetap tampil di tablet dan desktop -->
      <div class="bp-summary absolute z-[1260] hidden left-3 right-3 md:block">
        <SummaryBar :summary="store.summary" :detail="store.detail" @open-detail="detailOpen = true" />
      </div>
    </div>

    <BlockDetailDrawer :open="detailOpen" :detail="store.detail" @close="detailOpen = false" />
  </main>
</template>
