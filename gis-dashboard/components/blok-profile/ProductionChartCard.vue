<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { ProductionYear } from "~/stores/blokProfileStore";

const PAGE_SIZE = 10;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const props = defineProps<{ years: ProductionYear[]; loading: boolean }>();

const page = ref(1);

const pageCount = computed(() => Math.max(1, Math.ceil(props.years.length / PAGE_SIZE)));
const rows = computed(() => props.years.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE));

const trends = computed(() => ({
  ton: sparkline(props.years.map((row) => row.ton)),
  ton_ha: sparkline(props.years.map((row) => row.ton_ha)),
  bjr: sparkline(props.years.map((row) => row.bjr)),
  jjg_ppk: sparkline(props.years.map((row) => row.jjg_ppk)),
  kg_ppk: sparkline(props.years.map((row) => row.kg_ppk)),
}));

function sparkline(values: number[]) {
  const nums = values.filter((value) => Number.isFinite(value));
  if (nums.length < 2) return "";
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const width = 78;
  const height = 22;
  const pad = 2;
  return nums
    .map((value, index) => {
      const x = pad + (index / (nums.length - 1)) * (width - pad * 2);
      const y = pad + (1 - (value - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function format(value: number, digits: number) {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function periodOf(row: ProductionYear) {
  if (row.bulan && row.bulan >= 1 && row.bulan <= 12) return `${MONTHS[row.bulan - 1]} ${row.tahun}`;
  return String(row.periode ?? row.tahun);
}

function rowKey(row: ProductionYear) {
  return `${row.tahun}-${row.bulan ?? "y"}`;
}

const rangeLabel = computed(() => {
  const total = props.years.length;
  if (!total) return "0 periode";
  const start = (page.value - 1) * PAGE_SIZE + 1;
  const end = Math.min(page.value * PAGE_SIZE, total);
  return `${start.toLocaleString("id-ID")}–${end.toLocaleString("id-ID")} dari ${total.toLocaleString("id-ID")} periode`;
});

function go(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next));
}

watch(() => props.years, () => {
  page.value = 1;
});
watch(pageCount, (count) => {
  if (page.value > count) page.value = count;
});
</script>

<template>
  <section class="bp-card flex flex-col gap-3 p-4">
    <h2 class="text-18 font-bold text-[#1f2a18]">Data Histori</h2>

    <div v-if="loading && !years.length" class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="!years.length" class="py-8 text-center text-13 text-[#6e7866]">Belum ada data produksi untuk scope ini.</p>

    <template v-else>
      <div class="overflow-x-auto rounded-xl border border-[#d5dcc8]">
        <table class="w-full min-w-[640px] border-collapse text-left text-12">
          <thead>
            <tr class="border-b border-[#d5dcc8] text-[#1f2a18]">
              <th class="px-2.5 py-2 font-bold">Periode</th>
              <th class="px-2.5 py-2 font-bold">Luas</th>
              <th class="px-2.5 py-2 font-bold">Ton</th>
              <th class="px-2.5 py-2 font-bold">Ton/ha</th>
              <th class="px-2.5 py-2 font-bold">BJR</th>
              <th class="px-2.5 py-2 font-bold">Jjg/Pkk</th>
              <th class="px-2.5 py-2 font-bold">Kg/Pkk</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="rowKey(row)" class="border-t border-[#e6e6e6] text-[#1f2a18]"
              :class="index % 2 === 1 && 'bg-[#f2f2f2]'">
              <td class="px-2.5 py-1.5 tabular-nums">{{ periodOf(row) }}</td>
              <td class="px-2.5 py-1.5 tabular-nums">{{ format(row.luas, 3) }}</td>
              <td class="px-2.5 py-1.5 tabular-nums">{{ format(row.ton, 3) }}</td>
              <td class="px-2.5 py-1.5 tabular-nums">{{ format(row.ton_ha, 2) }}</td>
              <td class="px-2.5 py-1.5 tabular-nums">{{ format(row.bjr, 2) }}</td>
              <td class="px-2.5 py-1.5 tabular-nums">{{ format(row.jjg_ppk, 2) }}</td>
              <td class="px-2.5 py-1.5 tabular-nums">{{ format(row.kg_ppk, 0) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="border-t border-[#d5dcc8] text-[#1f2a18]">
              <td class="px-2.5 py-2 font-semibold">Trend Line</td>
              <td class="px-2 py-1.5" />
              <td class="px-2 py-1.5">
                <svg v-if="trends.ton" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren ton">
                  <polyline :points="trends.ton" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trends.ton_ha" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren ton per hektare">
                  <polyline :points="trends.ton_ha" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trends.bjr" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren BJR">
                  <polyline :points="trends.bjr" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trends.jjg_ppk" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren janjang per pokok">
                  <polyline :points="trends.jjg_ppk" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trends.kg_ppk" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren kilogram per pokok">
                  <polyline :points="trends.kg_ppk" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      <div class="flex items-center justify-between gap-2 text-12 text-[#55604c]">
        <span>{{ rangeLabel }}</span>
        <div class="flex items-center gap-1">
          <button type="button" class="hist-page" :disabled="page <= 1" aria-label="Halaman histori sebelumnya" @click="go(page - 1)">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 6-6 6 6 6" /></svg>
          </button>
          <span class="min-w-[4.5rem] text-center font-semibold text-[#1f2a18]">{{ page }} / {{ pageCount }}</span>
          <button type="button" class="hist-page" :disabled="page >= pageCount" aria-label="Halaman histori berikutnya" @click="go(page + 1)">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6" /></svg>
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.hist-page {
  display: inline-flex;
  height: 28px;
  width: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid #d5dcc8;
  background: #fff;
  color: #1f2a18;
}
.hist-page:hover:not(:disabled) {
  background: #eef3e7;
}
.hist-page:disabled {
  opacity: 0.4;
}
</style>
