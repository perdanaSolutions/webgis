<script setup lang="ts">
import { computed } from "vue";

import type { ProductionGapCategory, ProductionGapSummary } from "~/stores/blokProfileStore";
import { BUDGET_GAP_COLOR } from "~/utils/mapLayers";

const props = defineProps<{
  budget: ProductionGapSummary | null;
  sensus: ProductionGapSummary | null;
  loading: boolean;
}>();

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const columns = computed(() => [
  {
    key: "budget",
    title: "Budget",
    data: props.budget,
  },
  {
    key: "sensus",
    title: "Sensus",
    data: props.sensus,
  },
]);

function periodLabel(data: ProductionGapSummary | null) {
  const periode = data?.periode;
  if (!periode?.tahun) return "";
  const month = periode.bulan ? MONTHS[periode.bulan - 1] : "";
  return [month, periode.tahun].filter(Boolean).join(" ");
}

/** Nilai yang tampil sebagai 0,0% tidak ditampilkan. */
function isVisiblePct(value: number) {
  if (!Number.isFinite(value) || value <= 0) return false;
  return Math.round(value * 10) / 10 > 0;
}

function rowsOf(data: ProductionGapSummary | null): ProductionGapCategory[] {
  return (data?.kategori ?? []).filter((row) => isVisiblePct(row.persen_blok));
}

function ha(value: number) {
  return `${value.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Ha`;
}

function pct(value: number) {
  return `${value.toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function tone(name: string) {
  return BUDGET_GAP_COLOR[name.trim().toUpperCase()] ?? "#6e7866";
}
</script>

<template>
  <section class="bp-card p-4">
    <div class="mb-3">
      <h2 class="text-16 font-bold text-[#1f2a18]">Gap Produksi</h2>
      <p class="mt-0.5 text-12 leading-snug text-[#6e7866]">
        Varians produksi aktual dibanding budget dan sensus pada periode terakhir.
      </p>
    </div>

    <div v-if="loading && !budget && !sensus" class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">
      Memuat…
    </div>
    <p v-else-if="!budget && !sensus" class="py-8 text-center text-13 text-[#6e7866]">
      Belum ada ringkasan gap produksi.
    </p>

    <div v-else class="grid grid-cols-2">
      <div
        v-for="(column, index) in columns"
        :key="column.key"
        class="min-w-0"
        :class="index === 0 ? 'pr-3' : 'border-l border-[#d5dcc8] pl-3'"
      >
        <div class="mb-2 flex items-baseline justify-between gap-1">
          <h3 class="text-13 font-bold text-[#1f2a18]">{{ column.title }}</h3>
          <span v-if="periodLabel(column.data)" class="shrink-0 text-11 font-semibold text-[#55604c]">
            {{ periodLabel(column.data) }}
          </span>
        </div>

        <p v-if="!column.data" class="py-4 text-12 leading-snug text-[#6e7866]">Belum ada ringkasan.</p>
        <p v-else-if="!rowsOf(column.data).length" class="py-4 text-12 leading-snug text-[#6e7866]">
          Tidak ada varians.
        </p>

        <template v-else>
          <div
            class="mb-3 flex h-2 overflow-hidden rounded-full bg-[#e4e8de]"
            role="img"
            :aria-label="rowsOf(column.data).map((row) => `${row.kategori} ${pct(row.persen_blok)}`).join(', ')"
          >
            <span
              v-for="row in rowsOf(column.data)"
              :key="row.kategori"
              class="h-full"
              :style="{ width: `${row.persen_blok}%`, background: tone(row.kategori) }"
              :title="`${row.kategori}: ${pct(row.persen_blok)}`"
            />
          </div>

          <ul class="space-y-2.5">
            <li v-for="row in rowsOf(column.data)" :key="row.kategori" class="min-w-0">
              <div class="flex items-baseline justify-between gap-1.5">
                <p class="inline-flex min-w-0 items-center gap-1.5 text-12 font-semibold text-[#1f2a18]">
                  <span
                    class="h-2 w-2 shrink-0 rounded-[3px] shadow-[inset_0_0_0_1px_rgba(0,0,0,0.12)]"
                    :style="{ background: tone(row.kategori) }"
                  />
                  <span class="truncate">{{ row.kategori }}</span>
                </p>
                <p class="shrink-0 text-12 font-bold tabular-nums text-[#1f2a18]">{{ pct(row.persen_blok) }}</p>
              </div>
              <p v-if="row.keterangan" class="mt-0.5 pl-[14px] text-11 leading-snug text-[#6e7866]">{{ row.keterangan }}</p>
              <p class="pl-[14px] text-11 tabular-nums text-[#55604c]">
                {{ ha(row.luas) }} · {{ row.jumlah_blok.toLocaleString("id-ID") }} blok
              </p>
            </li>
          </ul>

          <dl class="mt-3 space-y-1 border-t border-[#d5dcc8] pt-2">
            <div class="flex items-baseline justify-between gap-2">
              <dt class="text-11 text-[#6e7866]">Total luas</dt>
              <dd class="text-11 font-semibold tabular-nums text-[#1f2a18]">{{ ha(column.data.grand_total.luas) }}</dd>
            </div>
            <div class="flex items-baseline justify-between gap-2">
              <dt class="text-11 text-[#6e7866]">Total blok</dt>
              <dd class="text-11 font-semibold tabular-nums text-[#1f2a18]">
                {{ column.data.grand_total.jumlah_blok.toLocaleString("id-ID") }}
              </dd>
            </div>
            <div v-if="isVisiblePct(column.data.grand_total.persen_blok)" class="flex items-baseline justify-between gap-2">
              <dt class="text-11 text-[#6e7866]">Cakupan</dt>
              <dd class="text-11 font-semibold tabular-nums text-[#1f2a18]">{{ pct(column.data.grand_total.persen_blok) }}</dd>
            </div>
          </dl>
        </template>
      </div>
    </div>
  </section>
</template>
