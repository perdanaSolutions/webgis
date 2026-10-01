<script setup lang="ts">
import { computed } from "vue";

import type { ProductionGapSummary } from "~/stores/blokProfileStore";

const props = defineProps<{
  title: string;
  caption: string;
  data: ProductionGapSummary | null;
  loading: boolean;
}>();

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const TONE: Record<string, string> = {
  OPTIMUM: "#638840",
  "GAP I": "#c4a15a",
  "GAP II": "#d87633",
  "GAP III": "#8b4034",
};

const periodLabel = computed(() => {
  const periode = props.data?.periode;
  if (!periode?.tahun) return "";
  const month = periode.bulan ? MONTHS[periode.bulan - 1] : "";
  return [month, periode.tahun].filter(Boolean).join(" ");
});

const segments = computed(() =>
  (props.data?.kategori ?? []).filter((row) => row.persen_blok > 0),
);

function ha(value: number) {
  return `${value.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Ha`;
}

function pct(value: number) {
  return `${value.toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function tone(name: string) {
  return TONE[name] ?? "#6e7866";
}
</script>

<template>
  <section class="bp-card p-5">
    <div class="mb-4 flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-18 font-bold text-[#1f2a18]">{{ title }}</h2>
        <p class="mt-0.5 text-12 leading-snug text-[#6e7866]">{{ caption }}</p>
      </div>
      <span v-if="periodLabel" class="shrink-0 rounded-lg bg-[#eef3e7] px-2.5 py-1 text-12 font-semibold text-[#55604c]">
        {{ periodLabel }}
      </span>
    </div>

    <div v-if="loading && !data" class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="!data" class="py-8 text-center text-13 text-[#6e7866]">Belum ada ringkasan gap produksi.</p>

    <template v-else>
      <div v-if="segments.length" class="mb-4 flex h-2.5 overflow-hidden rounded-full bg-[#e4e8de]" role="img"
        :aria-label="segments.map((row) => `${row.kategori} ${pct(row.persen_blok)}`).join(', ')">
        <span v-for="row in segments" :key="row.kategori" class="h-full" :style="{ width: `${row.persen_blok}%`, background: tone(row.kategori) }"
          :title="`${row.kategori}: ${pct(row.persen_blok)}`" />
      </div>

      <ul class="space-y-3">
        <li v-for="row in data.kategori" :key="row.kategori" class="min-w-0">
          <div class="flex items-baseline justify-between gap-3">
            <p class="inline-flex min-w-0 items-center gap-2 text-14 font-semibold text-[#1f2a18]">
              <span class="h-2.5 w-2.5 shrink-0 rounded-[3px]" :style="{ background: tone(row.kategori) }" />
              {{ row.kategori }}
            </p>
            <p class="shrink-0 text-14 font-bold tabular-nums text-[#1f2a18]">{{ pct(row.persen_blok) }}</p>
          </div>
          <p class="mt-0.5 pl-[18px] text-12 text-[#6e7866]">{{ row.keterangan }}</p>
          <p class="pl-[18px] text-12 tabular-nums text-[#55604c]">
            {{ ha(row.luas) }} · {{ row.jumlah_blok.toLocaleString("id-ID") }} blok
          </p>
        </li>
      </ul>

      <dl class="mt-4 grid grid-cols-3 gap-2 border-t border-[#d5dcc8] pt-3">
        <div>
          <dt class="text-11 text-[#6e7866]">Total luas</dt>
          <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ ha(data.grand_total.luas) }}</dd>
        </div>
        <div>
          <dt class="text-11 text-[#6e7866]">Total blok</dt>
          <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ data.grand_total.jumlah_blok.toLocaleString("id-ID") }}</dd>
        </div>
        <div class="text-right">
          <dt class="text-11 text-[#6e7866]">Cakupan</dt>
          <dd class="text-13 font-semibold tabular-nums text-[#1f2a18]">{{ pct(data.grand_total.persen_blok) }}</dd>
        </div>
      </dl>
    </template>
  </section>
</template>
