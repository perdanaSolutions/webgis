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
import { BASEMAPS, type BasemapKey, SLOPE_RAMP } from "~/utils/mapLayers";

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
const showPanels = ref(true);
const detailOpen = ref(false);

watch(basemap, (value) => {
  try { localStorage.setItem(BASEMAP_KEY, value); } catch { /* mode privat */ }
});

// ------------------------------------------------------------------ tata letak
const isDesktop = ref(false);
const isMobile = ref(false);
const leftOpen = ref(false);
const rightOpen = ref(false);
const stageRef = ref<HTMLElement | null>(null);
const stageW = ref(0);

let mqDesktop: MediaQueryList | null = null;
let mqMobile: MediaQueryList | null = null;
let stageObserver: ResizeObserver | null = null;

const GUTTER = 24;
const LEFT_W = 340;
const RIGHT_W = 380;
const BOTTOM_BAR_H = 72;
const EDGE = 12;
const DRAWER_CLEAR = 72; // selaras dengan w-[min(...,calc(100%-4.5rem))]
const TOGGLE_GAP = 8;

function drawerSize(max: number) {
  return Math.min(max, Math.max(0, stageW.value - DRAWER_CLEAR));
}

function measureStage() {
  stageW.value = stageRef.value?.clientWidth ?? window.innerWidth;
}

function syncLayout() {
  const wasDesktop = isDesktop.value;
  isDesktop.value = !!mqDesktop?.matches;
  isMobile.value = !!mqMobile?.matches;
  measureStage();
  if (isDesktop.value && !wasDesktop) {
    leftOpen.value = false;
    rightOpen.value = false;
  }
}

function toggleLeft() {
  leftOpen.value = !leftOpen.value;
  if (leftOpen.value) rightOpen.value = false;
}

function toggleRight() {
  rightOpen.value = !rightOpen.value;
  if (rightOpen.value) leftOpen.value = false;
}

function closeDrawers() {
  leftOpen.value = false;
  rightOpen.value = false;
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape" && !isDesktop.value) closeDrawers();
}

const leftToggleStyle = computed(() => {
  if (!leftOpen.value) return { left: "max(12px, env(safe-area-inset-left))", right: "auto" };
  return { left: `${EDGE + drawerSize(LEFT_W) + TOGGLE_GAP}px`, right: "auto" };
});

const rightToggleStyle = computed(() => {
  if (!rightOpen.value) return { right: "max(12px, env(safe-area-inset-right))", left: "auto" };
  return { right: `${EDGE + drawerSize(RIGHT_W) + TOGGLE_GAP}px`, left: "auto" };
});

const controlsShift = computed(() => {
  if (isDesktop.value || !rightOpen.value) return undefined;
  return {
    right: `${EDGE + drawerSize(RIGHT_W) + TOGGLE_GAP + 56}px`,
    bottom: "11.5rem",
  };
});

/** Bagian peta yang tertutup kartu mengambang -> dipakai untuk zoom-to-fit & posisi kontrol. */
const mapInsets = computed(() => {
  if (isDesktop.value) {
    if (!showPanels.value) return { top: GUTTER, right: GUTTER, bottom: GUTTER + 56, left: GUTTER };
    return { top: GUTTER, left: GUTTER + LEFT_W, right: GUTTER + RIGHT_W, bottom: GUTTER + BOTTOM_BAR_H };
  }
  const left = leftOpen.value ? EDGE + drawerSize(LEFT_W) + 60 : 56;
  const right = rightOpen.value ? EDGE + drawerSize(RIGHT_W) + 60 : 72;
  return { top: 16, left, right, bottom: isMobile.value ? 80 : 136 };
});

const slopeLayerOn = computed(() => layers.value.some((l) => l.code === "slope" && l.enabled));

// ------------------------------------------------------------------ aksi
function onSelectBlock(id: string) {
  if (!id || store.blokId === id) return;
  void store.selectBlock(id);
}

function onDeselectBlock() {
  void store.clearBlockSelection();
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

  if (!authStore.token) {
    await navigateTo("/login");
    return;
  }
  const session = await authStore.validateToken();
  if (!session) return;
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
  <main class="bp-map-shell flex min-h-0 flex-col overflow-hidden bg-[#f7f2ea] text-14 text-[#2b2118]">
    <Header :brand-title="headerBrandTitle" :brand-subtitle="headerBrandSubtitle" />

    <!-- PAGE HEADER -->
    <div class="flex shrink-0 items-center justify-between gap-2 border-b border-[#eadfce] bg-white px-3 py-1.5 sm:px-4 lg:px-6">
      <div class="min-w-0">
        <nav class="hidden text-11 leading-none text-[#8a7a68] sm:block" aria-label="Breadcrumb">
          <NuxtLink to="/dashboard" class="hover:underline">Beranda</NuxtLink>
          <span class="mx-1">/</span>
          <span>{{ pageTitle }}</span>
        </nav>
        <div class="flex min-w-0 items-baseline gap-x-2 sm:mt-0.5">
          <h1 class="truncate text-base font-bold leading-none tracking-tight text-[#2b2118] sm:text-lg">{{ pageTitle }}</h1>
          <p class="hidden min-w-0 truncate text-12 leading-none text-[#8a7a68] md:block">Tampilan peta layar penuh · scope: {{ store.scopeLabel }}</p>
        </div>
      </div>
      <div class="flex shrink-0 items-center gap-1.5">
        <button type="button" class="bp-btn bp-btn-panels" :aria-pressed="showPanels" @click="showPanels = !showPanels">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16M14 10l-2 2 2 2" />
          </svg>
          Panel
        </button>
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
          :overlays="layers" :basemap="basemap" :opacity="opacity / 100" :insets="mapInsets"
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
        <div v-show="isDesktop || !(isMobile && (leftOpen || rightOpen))"
          class="bp-controls absolute z-[1350] flex max-w-[calc(100%-5.5rem)] flex-col items-end gap-2 right-4 md:flex-row xl:right-6 xl:max-w-none"
          :style="controlsShift">
          <div v-if="slopeLayerOn" class="bp-card px-3 py-2 sm:px-4 sm:py-3">
            <p class="mb-2 text-11 font-bold uppercase tracking-[0.1em] text-[#8a7a68]">Kelas Kemiringan</p>
            <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
              <span v-for="(color, range) in SLOPE_RAMP" :key="range" class="inline-flex items-center gap-2 text-12 text-[#2b2118] sm:text-13">
                <span class="h-3 w-3 rounded-[3px] ring-1 ring-black/10" :style="{ background: color }" />{{ range }}%
              </span>
            </div>
          </div>
          <div class="bp-card flex overflow-hidden !rounded-2xl">
            <button type="button" class="flex h-11 w-11 items-center justify-center hover:bg-[#f6efe4] sm:h-12 sm:w-12" aria-label="Perbesar" @click="mapRef?.zoomIn()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
            </button>
            <button type="button" class="flex h-11 w-11 items-center justify-center border-x border-[#eadfce] hover:bg-[#f6efe4] sm:h-12 sm:w-12" aria-label="Perkecil" @click="mapRef?.zoomOut()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14" /></svg>
            </button>
            <button type="button" class="flex h-11 w-11 items-center justify-center hover:bg-[#f6efe4] sm:h-12 sm:w-12" aria-label="Fokus ke scope / blok terpilih" @click="mapRef?.fitScope()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
            </button>
          </div>
        </div>
      </section>

      <button v-show="!isDesktop && (leftOpen || rightOpen)" type="button"
        class="absolute inset-0 z-[1250] bg-[#2b2118]/25 xl:hidden" aria-label="Tutup panel" @click="closeDrawers" />

      <!-- KARTU KIRI -->
      <aside id="bp-panel-left" v-show="!isDesktop || showPanels"
        class="bp-drawer absolute z-[1300] flex min-h-0 flex-col overflow-hidden max-xl:-translate-x-[calc(100%+1.25rem)] top-3 left-3 w-[min(340px,calc(100%-4.5rem))] xl:left-6 xl:top-6 xl:w-[340px]"
        :class="leftOpen && 'max-xl:!translate-x-0'"
        :inert="!isDesktop && !leftOpen ? true : undefined"
        :aria-hidden="!isDesktop && !leftOpen ? true : undefined">
        <FilterPanel class="min-h-0 flex-1" :area-options="store.areaOptions" :pt-options="store.ptOptions" :estate-options="store.estateOptions"
          :afdeling-options="store.afdelingOptions" :blok-options="store.blokOptions"
          :ownership-options="store.ownershipOptions" :tahun-tanam-options="store.tahunTanamOptions"
          :area="store.area" :pt="store.pt" :estate="store.estate" :afdeling="store.afdeling" :blok-id="store.blokId"
          :ownership="store.ownership" :tahun-tanam="store.tahunTanam" :scope-level="store.scopeLevel"
          :block-count="store.blockFeatures.length" :loading="store.loadingOptions || store.loadingBlocks" :layers="layers"
          :show-blocks="showBlocks" :basemap="basemap" :opacity="opacity"
          @update:area="store.setArea" @update:pt="store.setPt" @update:estate="store.setEstate"
          @update:afdeling="store.setAfdeling" @update:blok="store.selectBlock"
          @update:ownership="store.setOwnership" @update:tahun-tanam="store.setTahunTanam"
          @reset="store.reset" @toggle-layer="overlays.toggle"
          @toggle-blocks="showBlocks = !showBlocks" @update:basemap="basemap = $event" @update:opacity="opacity = $event" />
      </aside>

      <button v-show="!isMobile || !rightOpen" type="button" class="bp-edge-btn" :class="leftOpen && 'is-open'" :style="leftToggleStyle"
        :aria-expanded="leftOpen" aria-controls="bp-panel-left"
        :aria-label="leftOpen ? 'Tutup panel kiri' : 'Buka panel kiri'" @click="toggleLeft">
        <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
          <path v-if="leftOpen" stroke-linecap="round" stroke-linejoin="round" d="m15 6-6 6 6 6" />
          <path v-else stroke-linecap="round" stroke-linejoin="round" d="m9 6 6 6-6 6" />
        </svg>
      </button>

      <!-- KOLOM KANAN -->
      <aside id="bp-panel-right" v-show="!isDesktop || showPanels"
        class="bp-drawer bp-drawer-right absolute z-[1300] min-h-0 space-y-3 overflow-y-auto overscroll-contain max-xl:translate-x-[calc(100%+1.25rem)] top-3 right-3 w-[min(380px,calc(100%-4.5rem))] pb-1 xl:right-6 xl:top-6 xl:w-[380px] xl:space-y-4"
        :class="rightOpen && 'max-xl:!translate-x-0'"
        :inert="!isDesktop && !rightOpen ? true : undefined"
        :aria-hidden="!isDesktop && !rightOpen ? true : undefined">
        <BlockInfoCard :summary="store.summary" :detail="store.detail" :loading="store.loadingDetail" />
        <template v-if="store.canViewProduction">
          <ProductionGapCard title="Gap terhadap Budget"
            caption="Varians produksi aktual dibanding budget pada periode terakhir."
            :data="store.productionGapBudget" :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
          <ProductionGapCard title="Gap terhadap Sensus"
            caption="Varians produksi aktual dibanding sensus pada periode terakhir."
            :data="store.productionGapSensus" :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
        </template>
        <SlopeDonutCard v-if="store.canViewProduction"
          :shares="store.slopeShares" :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
        <ProductionChartCard v-if="store.canViewProduction" :years="store.productionYears"
          :loading="store.blokId ? store.loadingDetail : store.loadingProduction" />
        <AreaStatementCard v-if="store.canViewAreaStatement" :data="store.areaStatementView"
          :loading="store.blokId ? store.loadingDetail : store.loadingAreaStatement" />
        <RotationCard v-if="store.canViewRotation" :data="store.rotationView"
          :loading="store.blokId ? store.loadingDetail : store.loadingRotation" />
      </aside>

      <button v-show="!isMobile || !leftOpen" type="button" class="bp-edge-btn" :class="rightOpen && 'is-open'" :style="rightToggleStyle"
        :aria-expanded="rightOpen" aria-controls="bp-panel-right"
        :aria-label="rightOpen ? 'Tutup panel kanan' : 'Buka panel kanan'" @click="toggleRight">
        <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
          <path v-if="rightOpen" stroke-linecap="round" stroke-linejoin="round" d="m9 6 6 6-6 6" />
          <path v-else stroke-linecap="round" stroke-linejoin="round" d="m15 6-6 6 6 6" />
        </svg>
      </button>

      <!-- BAR RINGKASAN: sembunyi di mobile, tetap tampil di tablet dan desktop -->
      <div v-show="!isDesktop || showPanels"
        class="bp-summary absolute z-[1260] hidden left-3 right-3 md:block xl:left-[388px] xl:right-[428px]">
        <SummaryBar :summary="store.summary" :detail="store.detail" @open-detail="detailOpen = true" />
      </div>
    </div>

    <BlockDetailDrawer :open="detailOpen" :detail="store.detail" @close="detailOpen = false" />
  </main>
</template>
