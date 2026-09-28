<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";

import "~/assets/css/blok-profile.css";
import BlockDetailDrawer from "~/components/blok-profile/BlockDetailDrawer.vue";
import BlockInfoCard from "~/components/blok-profile/BlockInfoCard.vue";
import BlokProfileMap from "~/components/blok-profile/BlokProfileMap.vue";
import FilterPanel from "~/components/blok-profile/FilterPanel.vue";
import ProductionChartCard from "~/components/blok-profile/ProductionChartCard.vue";
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
let mq: MediaQueryList | null = null;
const syncDesktop = () => { isDesktop.value = !!mq?.matches; };

const GUTTER = 24;
const LEFT_W = 340;
const RIGHT_W = 380;
const BOTTOM_BAR_H = 72;

/** Bagian peta yang tertutup kartu mengambang -> dipakai untuk zoom-to-fit & posisi kontrol. */
const mapInsets = computed(() => {
  if (!isDesktop.value || !showPanels.value) return { top: GUTTER, right: GUTTER, bottom: GUTTER + 56, left: GUTTER };
  return { top: GUTTER, left: GUTTER + LEFT_W, right: GUTTER + RIGHT_W, bottom: GUTTER + BOTTOM_BAR_H };
});

const slopeLayerOn = computed(() => layers.value.some((l) => l.code === "slope" && l.enabled));

// ------------------------------------------------------------------ aksi
function onSelectBlock(id: string) {
  void store.selectBlock(store.blokId === id ? "" : id); // klik blok yang sama = batal pilih
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
  mq = window.matchMedia("(min-width: 1024px)");
  syncDesktop();
  mq.addEventListener("change", syncDesktop);
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

onBeforeUnmount(() => mq?.removeEventListener("change", syncDesktop));
</script>

<template>
  <main class="flex min-h-screen flex-col bg-[#f7f2ea] text-14 text-[#2b2118] lg:h-screen">
    <Header :brand-title="headerBrandTitle" :brand-subtitle="headerBrandSubtitle" />

    <!-- PAGE HEADER -->
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[#eadfce] bg-white px-4 py-1.5 lg:px-6">
      <div class="min-w-0">
        <nav class="text-11 leading-none text-[#8a7a68]" aria-label="Breadcrumb">
          <NuxtLink to="/dashboard" class="hover:underline">Beranda</NuxtLink>
          <span class="mx-1">/</span>
          <span>{{ pageTitle }}</span>
        </nav>
        <div class="mt-0.5 flex min-w-0 flex-wrap items-baseline gap-x-2">
          <h1 class="text-lg font-bold leading-none tracking-tight text-[#2b2118]">{{ pageTitle }}</h1>
          <p class="truncate text-12 leading-none text-[#8a7a68]">Tampilan peta layar penuh · scope: {{ store.scopeLabel }}</p>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <button type="button" class="bp-btn hidden lg:inline-flex" :aria-pressed="showPanels" @click="showPanels = !showPanels">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16M14 10l-2 2 2 2" />
          </svg>
          Panel
        </button>
        <button type="button" class="bp-btn" title="Unduh batas blok & layer aktif sebagai GeoJSON" @click="downloadGeoJSON">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" />
          </svg>
          Unduh Peta
        </button>
        <NuxtLink to="/document" class="bp-btn bp-btn-primary">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          Tambah Blok
        </NuxtLink>
      </div>
    </div>

    <div class="relative flex flex-1 flex-col lg:block lg:min-h-0 lg:overflow-hidden">
      <!-- PETA -->
      <section class="relative h-[62vh] min-h-[420px] lg:absolute lg:inset-0 lg:h-auto">
        <BlokProfileMap ref="mapRef" :blocks="store.blocks" :selected-id="store.blokId" :show-blocks="showBlocks"
          :overlays="layers" :basemap="basemap" :opacity="opacity / 100" :insets="mapInsets" @select="onSelectBlock" />

        <div v-if="store.loadingBlocks"
          class="pointer-events-none absolute left-1/2 top-6 z-[1200] -translate-x-1/2 rounded-full bg-white/95 px-4 py-2 text-13 font-medium shadow-lg">
          Memuat batas blok…
        </div>
        <div v-else-if="!store.blockFeatures.length && store.area"
          class="pointer-events-none absolute left-1/2 top-6 z-[1200] -translate-x-1/2 rounded-full bg-white/95 px-4 py-2 text-13 shadow-lg">
          Belum ada batas blok untuk scope ini.
        </div>

        <!-- Legenda kelas kemiringan + kontrol peta -->
        <div class="absolute bottom-6 right-6 z-[1100] flex items-end gap-3">
          <div v-if="slopeLayerOn" class="bp-card px-4 py-3">
            <p class="mb-2 text-11 font-bold uppercase tracking-[0.1em] text-[#8a7a68]">Kelas Kemiringan</p>
            <div class="grid grid-cols-2 gap-x-5 gap-y-1.5">
              <span v-for="(color, range) in SLOPE_RAMP" :key="range" class="inline-flex items-center gap-2 text-13 text-[#2b2118]">
                <span class="h-3 w-3 rounded-[3px] ring-1 ring-black/10" :style="{ background: color }" />{{ range }}%
              </span>
            </div>
          </div>
          <div class="bp-card flex overflow-hidden !rounded-2xl">
            <button type="button" class="flex h-12 w-12 items-center justify-center hover:bg-[#f6efe4]" aria-label="Perbesar" @click="mapRef?.zoomIn()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
            </button>
            <button type="button" class="flex h-12 w-12 items-center justify-center border-x border-[#eadfce] hover:bg-[#f6efe4]" aria-label="Perkecil" @click="mapRef?.zoomOut()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14" /></svg>
            </button>
            <button type="button" class="flex h-12 w-12 items-center justify-center hover:bg-[#f6efe4]" aria-label="Fokus ke scope / blok terpilih" @click="mapRef?.fitScope()">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>
            </button>
          </div>
        </div>
      </section>

      <!-- KARTU KIRI -->
      <aside v-show="showPanels || !isDesktop" class="z-[1100] p-4 lg:absolute lg:bottom-6 lg:left-6 lg:top-6 lg:w-[340px] lg:p-0">
        <FilterPanel :area-options="store.areaOptions" :estate-options="store.estateOptions"
          :afdeling-options="store.afdelingOptions" :blok-options="store.blokOptions" :area="store.area"
          :estate="store.estate" :afdeling="store.afdeling" :blok-id="store.blokId" :scope-level="store.scopeLevel"
          :block-count="store.blockFeatures.length" :loading="store.loadingOptions || store.loadingBlocks" :layers="layers"
          :show-blocks="showBlocks" :basemap="basemap" :opacity="opacity"
          @update:area="store.setArea" @update:estate="store.setEstate" @update:afdeling="store.setAfdeling"
          @update:blok="store.selectBlock" @reset="store.reset" @toggle-layer="overlays.toggle"
          @toggle-blocks="showBlocks = !showBlocks" @update:basemap="basemap = $event" @update:opacity="opacity = $event" />
      </aside>

      <!-- KOLOM KANAN -->
      <aside v-show="showPanels || !isDesktop"
        class="z-[1100] space-y-4 p-4 lg:absolute lg:bottom-[104px] lg:right-6 lg:top-6 lg:w-[380px] lg:overflow-y-auto lg:p-0 lg:pb-1">
        <BlockInfoCard :summary="store.summary" :detail="store.detail" :loading="store.loadingDetail" />
        <SlopeDonutCard v-if="store.canViewAreaStatement || store.canViewProduction"
          :shares="store.slopeShares" :loading="store.loadingProduction || store.loadingDetail" />
        <ProductionChartCard v-if="store.canViewProduction" :years="store.productionYears" :loading="store.loadingProduction" />
      </aside>

      <!-- BAR RINGKASAN -->
      <div v-show="showPanels || !isDesktop" class="z-[1100] p-4 lg:absolute lg:bottom-6 lg:left-[388px] lg:right-[428px] lg:p-0">
        <SummaryBar :summary="store.summary" :detail="store.detail" @open-detail="detailOpen = true" />
      </div>
    </div>

    <BlockDetailDrawer :open="detailOpen" :detail="store.detail" @close="detailOpen = false" />
  </main>
</template>
