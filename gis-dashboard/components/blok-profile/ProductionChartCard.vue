<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { ProductionYear } from "~/stores/blokProfileStore";
import { yearlySummaries } from "~/utils/productionSummary";

const PAGE_SIZE = 10;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const props = defineProps<{
  years: ProductionYear[];
  loading: boolean;
  expanded?: boolean;
  /** rekap_tahunan (satu baris per tahun, semua tahun dalam filter wilayah). */
  recap?: ProductionYear[];
}>();

type View = "bulanan" | "tahunan";
const view = ref<View>("bulanan");
const page = ref(1);
const recapRows = computed(() => props.recap ?? []);
const hasRecap = computed(() => recapRows.value.length > 0);
/** Data tabel aktif: per periode (bulanan) atau rekap per tahun. */
const active = computed(() => (view.value === "tahunan" && hasRecap.value ? recapRows.value : props.years));
const isYearly = computed(() => view.value === "tahunan" && hasRecap.value);
/** Mode cetak (expanded): kedua tabel ditampilkan berurutan. */
const sections = computed(() => (
  props.expanded
    ? [{ key: "bulanan" as View, list: props.years }, ...(hasRecap.value ? [{ key: "tahunan" as View, list: recapRows.value }] : [])]
    : [{ key: (isYearly.value ? "tahunan" : "bulanan") as View, list: active.value }]
));

/** Ringkasan 1 tahun dari SEMUA baris (bukan hanya halaman aktif). */
const summaries = computed(() => yearlySummaries(props.years));

const pageCount = computed(() => Math.max(1, Math.ceil(active.value.length / PAGE_SIZE)));

function rowsOf(list: ProductionYear[]) {
  return props.expanded ? list : list.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE);
}

function trendsOf(list: ProductionYear[]) {
  return {
    ton: sparkline(list.map((row) => row.ton)),
    ton_ha: sparkline(list.map((row) => row.ton_ha)),
    bjr: sparkline(list.map((row) => row.bjr)),
    jjg_ppk: sparkline(list.map((row) => row.jjg_ppk)),
    kg_ppk: sparkline(list.map((row) => row.kg_ppk)),
  };
}

function setView(next: View) {
  view.value = next;
  page.value = 1;
}

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

function periodOf(row: ProductionYear, yearly = false) {
  if (yearly) return String(row.tahun);
  if (row.bulan && row.bulan >= 1 && row.bulan <= 12) return `${MONTHS[row.bulan - 1]} ${row.tahun}`;
  return String(row.periode ?? row.tahun);
}

function rowKey(row: ProductionYear) {
  return `${row.tahun}-${row.bulan ?? "y"}`;
}

const rangeLabel = computed(() => {
  const total = active.value.length;
  const unit = isYearly.value ? "tahun" : "periode";
  if (!total) return `0 ${unit}`;
  const start = (page.value - 1) * PAGE_SIZE + 1;
  const end = Math.min(page.value * PAGE_SIZE, total);
  return `${start.toLocaleString("id-ID")}–${end.toLocaleString("id-ID")} dari ${total.toLocaleString("id-ID")} ${unit}`;
});

function go(next: number) {
  page.value = Math.min(pageCount.value, Math.max(1, next));
}

watch(() => [props.years, props.recap], () => {
  page.value = 1;
});
watch(pageCount, (count) => {
  if (page.value > count) page.value = count;
});
</script>

<template>
  <section class="bp-card flex flex-col gap-3 p-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="text-18 font-bold text-[#1f2a18]">Data Histori</h2>
      <div v-if="hasRecap && !expanded" class="hist-tabs" role="tablist" aria-label="Tampilan data histori">
        <button type="button" role="tab" :aria-selected="view === 'bulanan'" :class="view === 'bulanan' && 'is-active'"
          @click="setView('bulanan')">Bulanan</button>
        <button type="button" role="tab" :aria-selected="view === 'tahunan'" :class="view === 'tahunan' && 'is-active'"
          @click="setView('tahunan')">Tahunan</button>
      </div>
    </div>

    <div v-if="loading && !years.length && !hasRecap" class="flex h-[132px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="!years.length && !hasRecap" class="py-8 text-center text-13 text-[#6e7866]">Belum ada data produksi untuk scope ini.</p>

    <template v-else>
      <template v-if="!isYearly || expanded">
      <div v-for="s in summaries" :key="`sum-${s.tahun}`"
        class="rounded-xl border border-[#d5dcc8] bg-[#eef3e7] px-3 py-2.5 text-[#1f2a18]">
        <div class="mb-1.5 flex items-baseline justify-between gap-2">
          <h3 class="text-13 font-bold">Total {{ s.tahun }}</h3>
          <span class="text-11 text-[#55604c]">{{ s.periods.toLocaleString("id-ID") }} periode</span>
        </div>
        <dl class="grid grid-cols-3 gap-2 text-12">
          <div class="min-w-0">
            <dt class="text-11 text-[#6e7866]">Luas{{ s.luasBulan ? ` (${MONTHS[s.luasBulan - 1]})` : "" }}</dt>
            <dd class="font-semibold tabular-nums">{{ format(s.luas, 3) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-11 text-[#6e7866]">Total Ton</dt>
            <dd class="font-semibold tabular-nums">{{ format(s.ton, 3) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-11 text-[#6e7866]">Ton/ha</dt>
            <dd class="font-semibold tabular-nums">{{ format(s.ton_ha, 2) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-11 text-[#6e7866]" title="Rata-rata tertimbang: total Kg/Pkk ÷ total Jjg/Pkk">BJR (tertimbang)</dt>
            <dd class="font-semibold tabular-nums">{{ format(s.bjr, 2) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-11 text-[#6e7866]">Total Jjg/Pkk</dt>
            <dd class="font-semibold tabular-nums">{{ format(s.jjg_ppk, 2) }}</dd>
          </div>
          <div class="min-w-0">
            <dt class="text-11 text-[#6e7866]">Total Kg/Pkk</dt>
            <dd class="font-semibold tabular-nums">{{ format(s.kg_ppk, 0) }}</dd>
          </div>
        </dl>
      </div>

      </template>

      <div v-for="sec in sections" :key="sec.key" class="flex flex-col gap-1.5">
      <h3 v-if="expanded && sections.length > 1" class="text-13 font-bold text-[#1f2a18]">
        {{ sec.key === "tahunan" ? "Rekap Tahunan" : "Per Periode" }}
      </h3>
      <div class="overflow-x-auto rounded-xl border border-[#d5dcc8]">
        <table class="w-full min-w-[640px] border-collapse text-left text-12">
          <thead>
            <tr class="border-b border-[#d5dcc8] text-[#1f2a18]">
              <th class="px-2.5 py-2 font-bold">{{ sec.key === "tahunan" ? "Tahun" : "Periode" }}</th>
              <th class="px-2.5 py-2 font-bold">Luas</th>
              <th class="px-2.5 py-2 font-bold">Ton</th>
              <th class="px-2.5 py-2 font-bold">Ton/ha</th>
              <th class="px-2.5 py-2 font-bold">BJR</th>
              <th class="px-2.5 py-2 font-bold">Jjg/Pkk</th>
              <th class="px-2.5 py-2 font-bold">Kg/Pkk</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rowsOf(sec.list)" :key="rowKey(row)" class="border-t border-[#e6e6e6] text-[#1f2a18]"
              :class="index % 2 === 1 && 'bg-[#f2f2f2]'">
              <td class="px-2.5 py-1.5 tabular-nums" :title="sec.key === 'tahunan' && row.jumlah_periode ? `${row.jumlah_periode} periode` : undefined">{{ periodOf(row, sec.key === "tahunan") }}</td>
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
                <svg v-if="trendsOf(sec.list).ton" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren ton">
                  <polyline :points="trendsOf(sec.list).ton" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trendsOf(sec.list).ton_ha" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren ton per hektare">
                  <polyline :points="trendsOf(sec.list).ton_ha" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trendsOf(sec.list).bjr" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren BJR">
                  <polyline :points="trendsOf(sec.list).bjr" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trendsOf(sec.list).jjg_ppk" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren janjang per pokok">
                  <polyline :points="trendsOf(sec.list).jjg_ppk" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
              <td class="px-2 py-1.5">
                <svg v-if="trendsOf(sec.list).kg_ppk" viewBox="0 0 78 22" class="h-6 w-[4.5rem]" role="img" aria-label="Tren kilogram per pokok">
                  <polyline :points="trendsOf(sec.list).kg_ppk" fill="none" stroke="#e07b2a" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />
                </svg>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      </div>

      <div v-if="!expanded" class="flex items-center justify-between gap-2 text-12 text-[#55604c]">
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
.hist-tabs {
  display: inline-flex;
  border: 1px solid #d5dcc8;
  border-radius: 999px;
  padding: 2px;
  background: #fff;
}
.hist-tabs button {
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  color: #55604c;
}
.hist-tabs button.is-active {
  background: #4f6b2f;
  color: #fff;
}
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
