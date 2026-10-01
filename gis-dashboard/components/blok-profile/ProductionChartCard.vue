<script setup lang="ts">
import { computed, ref } from "vue";

import type { ProductionYear } from "~/stores/blokProfileStore";

const props = defineProps<{ years: ProductionYear[]; loading: boolean }>();

const MAX_BARS = 6;
const hovered = ref<number | null>(null);

const bars = computed(() => {
  const rows = props.years.slice(-MAX_BARS);
  const max = Math.max(...rows.map((r) => r.ton), 1);
  const latest = rows[rows.length - 1]?.tahun;
  return rows.map((r) => ({ ...r, height: Math.max((r.ton / max) * 100, 2), latest: r.tahun === latest }));
});

function ton(value: number) {
  return value.toLocaleString("id-ID", { maximumFractionDigits: value >= 100 ? 0 : 1 });
}
</script>

<template>
  <section class="bp-card p-5">
    <div class="mb-3 flex items-baseline justify-between">
      <h2 class="text-18 font-bold text-[#1f2a18]">Produksi per Tahun</h2>
      <span class="text-12 text-[#6e7866]">ton TBS</span>
    </div>

    <div v-if="loading && !bars.length" class="flex h-[180px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="!bars.length" class="py-10 text-center text-13 text-[#6e7866]">Belum ada data produksi untuk scope ini.</p>

    <div v-else class="relative" role="img"
      :aria-label="`Produksi TBS per tahun: ${bars.map((b) => `${b.tahun} ${ton(b.ton)} ton`).join(', ')}`">
      <div class="flex h-[180px] items-end gap-2 border-b border-[#d5dcc8]">
        <div v-for="bar in bars" :key="bar.tahun" class="group relative flex h-full flex-1 flex-col items-center justify-end"
          @mouseenter="hovered = bar.tahun" @mouseleave="hovered = null">
          <!-- label nilai hanya untuk tahun terbaru & yang di-hover (label selektif) -->
          <span class="mb-1 text-12 tabular-nums"
            :class="bar.latest || hovered === bar.tahun ? 'font-semibold text-[#1f2a18]' : 'text-transparent'">
            {{ ton(bar.ton) }}
          </span>
          <div class="w-full max-w-[44px] rounded-t-[4px] transition-colors"
            :class="bar.latest ? 'bg-[#638840]' : hovered === bar.tahun ? 'bg-[#d87633]' : 'bg-[#c5d4b4]'"
            :style="{ height: `${bar.height}%` }" />
          <div v-if="hovered === bar.tahun"
            class="pointer-events-none absolute bottom-full z-10 mb-1 whitespace-nowrap rounded-lg bg-[#1f2a18] px-2.5 py-1.5 text-12 text-white shadow-lg">
            <p class="font-semibold">{{ bar.tahun }} · {{ ton(bar.ton) }} ton</p>
            <p class="text-white/75">{{ bar.ton_ha.toLocaleString('id-ID', { maximumFractionDigits: 2 }) }} ton/ha · BJR {{ bar.bjr.toLocaleString('id-ID', { maximumFractionDigits: 1 }) }}</p>
            <p class="text-white/75">{{ bar.jjg_ppk.toLocaleString('id-ID', { maximumFractionDigits: 2 }) }} jjg/pkk · {{ bar.kg_ppk.toLocaleString('id-ID', { maximumFractionDigits: 0 }) }} kg/pkk</p>
          </div>
        </div>
      </div>
      <div class="mt-2 flex gap-2">
        <span v-for="bar in bars" :key="bar.tahun" class="flex-1 text-center text-12 tabular-nums"
          :class="bar.latest ? 'font-semibold text-[#1f2a18]' : 'text-[#6e7866]'">{{ bar.tahun }}</span>
      </div>
    </div>
  </section>
</template>
