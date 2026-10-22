<script setup lang="ts">
import { ref } from "vue";

import AreaStatementCard from "~/components/blok-profile/AreaStatementCard.vue";
import BlockInfoCard from "~/components/blok-profile/BlockInfoCard.vue";
import ProductionChartCard from "~/components/blok-profile/ProductionChartCard.vue";
import ProductionGapCard from "~/components/blok-profile/ProductionGapCard.vue";
import RotationCard from "~/components/blok-profile/RotationCard.vue";
import SlopeInfoCard from "~/components/blok-profile/SlopeInfoCard.vue";
import type { AreaStatementHistory, AreaStatementSummary, LayerArealData, ProductionGapSummary, ProductionYear, RotationHistory } from "~/stores/blokProfileStore";

defineProps<{
  scopeLabel: string;
  filterLine: string;
  summary: {
    kind: "blok" | "scope";
    title: string;
    subtitle: string;
    status: string;
    luas: number;
    luasKerangka: number;
    pokok: number;
    blokCount: number;
    filter: { grup: string; pt: string; estate: string; afdeling: string; blok: string };
    geojsonPeriod: { bulan: number | null; tahun: number } | null;
  };
  detail: Record<string, any> | null;
  loadingDetail: boolean;
  canViewProduction: boolean;
  productionYears: ProductionYear[];
  productionLoading: boolean;
  productionGapBudget: ProductionGapSummary | null;
  productionGapSensus: ProductionGapSummary | null;
  slopeOn: boolean;
  slopeFeatures: GeoJSON.Feature[];
  slopeLoading: boolean;
  slopeError: string;
  slopePeriod: string;
  canViewArea: boolean;
  areaStatement: AreaStatementHistory | null;
  areaLoading: boolean;
  layerAreal: LayerArealData | null;
  layerLoading: boolean;
  areaSummary: AreaStatementSummary | null;
  summaryLoading: boolean;
  canViewRotation: boolean;
  rotation: RotationHistory | null;
  rotationLoading: boolean;
}>();

const root = ref<HTMLElement | null>(null);

function sections() {
  return [...(root.value?.querySelectorAll<HTMLElement>(".bp-card") ?? [])];
}

defineExpose({ sections });
</script>

<template>
  <div ref="root" class="bp-print-host" aria-hidden="true">
    <header class="bp-print-section bp-print-intro">
      <p class="text-11 font-bold uppercase tracking-[0.12em] text-[#6e7866]">Informasi</p>
      <h2 class="mt-1 text-[22px] font-bold leading-tight text-[#1f2a18]">{{ scopeLabel }}</h2>
      <p class="mt-1 text-13 leading-snug text-[#55604c]">{{ filterLine }}</p>
    </header>

    <div class="bp-print-section">
      <BlockInfoCard :summary="summary" :detail="detail" :loading="loadingDetail" />
    </div>

    <template v-if="canViewProduction">
      <div class="bp-print-section">
        <ProductionChartCard :years="productionYears" :loading="productionLoading" expanded />
      </div>
      <div class="bp-print-section">
        <ProductionGapCard :budget="productionGapBudget" :sensus="productionGapSensus" :loading="productionLoading" />
      </div>
    </template>

    <div v-if="slopeOn" class="bp-print-section">
      <SlopeInfoCard :features="slopeFeatures" :loading="slopeLoading" :error="slopeError" :period="slopePeriod" expanded />
    </div>

    <div v-if="canViewArea" class="bp-print-section">
      <AreaStatementCard :data="areaStatement" :loading="areaLoading" :layer-areal="layerAreal"
        :layer-loading="layerLoading" :area-summary="areaSummary" :summary-loading="summaryLoading" expanded />
    </div>

    <div v-if="canViewRotation" class="bp-print-section">
      <RotationCard :data="rotation" :loading="rotationLoading" expanded />
    </div>
  </div>
</template>
