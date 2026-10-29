<script setup lang="ts">
import { computed, ref } from "vue";

import TruncatedText from "~/components/blok-profile/TruncatedText.vue";
import type { RotationActivity, RotationHistory } from "~/stores/blokProfileStore";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

const props = defineProps<{ data: RotationHistory | null; loading: boolean; expanded?: boolean }>();

const hovered = ref<string | null>(null);
const kegiatan = computed(() => props.data?.kegiatan ?? null);

function formatTanggal(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value || "-";
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return date.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

function activityLine(row: RotationActivity) {
  const status = row.status ? `${row.status} · ` : "";
  return `Rotasi ${row.rotasi} · ${status}${num(row.luas)} ha · ${num(row.pokok, 0)} pokok`;
}

function periodLabel(tahun: number, bulan: number | null) {
  if (bulan && bulan >= 1 && bulan <= 12) return `${MONTHS[bulan - 1]} ${tahun}`;
  return String(tahun);
}

function shortLabel(tahun: number, bulan: number | null, multiYear: boolean) {
  if (bulan && bulan >= 1 && bulan <= 12) {
    return multiYear ? `${MONTHS[bulan - 1]} '${String(tahun).slice(-2)}` : MONTHS[bulan - 1];
  }
  return String(tahun);
}

function rowKey(tahun: number, bulan: number | null) {
  return `${tahun}-${bulan ?? "y"}`;
}

const rows = computed(() =>
  (props.data?.data ?? [])
    .map((row) => {
      const tahun = Number(row.tahun);
      const bulanRaw = row.bulan == null ? null : Number(row.bulan);
      const bulan = bulanRaw != null && Number.isFinite(bulanRaw) && bulanRaw >= 1 && bulanRaw <= 12
        ? bulanRaw
        : null;
      return {
        key: rowKey(tahun, bulan),
        tahun,
        bulan,
        label: periodLabel(tahun, bulan),
        hari: Number(row.avg_pusingan_hari ?? 0),
        rotasi: Number(row.rotasi_terakhir ?? 0),
        putaran: Number(row.total_rotasi ?? 0),
        luas: Number(row.total_luas_rotasi ?? 0),
        pokok: Number(row.total_pokok_rotasi ?? 0),
      };
    })
    .filter((row) => Number.isFinite(row.tahun))
    .sort((a, b) => a.tahun - b.tahun || (a.bulan ?? 0) - (b.bulan ?? 0)),
);

const multiYear = computed(() => new Set(rows.value.map((row) => row.tahun)).size > 1);

const bars = computed(() => {
  const max = Math.max(...rows.value.map((row) => row.hari), 1);
  const latestKey = rows.value[rows.value.length - 1]?.key;
  return rows.value.map((row) => ({
    ...row,
    short: shortLabel(row.tahun, row.bulan, multiYear.value),
    height: Math.max((row.hari / max) * 100, row.hari > 0 ? 4 : 0),
    latest: row.key === latestKey,
  }));
});

const latest = computed(() => bars.value[bars.value.length - 1] ?? null);

/** Ringkasan agregat seluruh periode pada filter tahun (bukan hanya periode terakhir). */
const totals = computed(() => {
  const list = bars.value;
  const first = list[0];
  const last = list[list.length - 1];
  if (!first || !last) return null;
  const period = first.key === last.key ? first.label : `${first.label} – ${last.label}`;
  const n = list.length;
  return {
    period,
    hari: list.reduce((sum, row) => sum + row.hari, 0) / n,
    rotasi: list.reduce((sum, row) => sum + row.rotasi, 0),
    luas: list.reduce((sum, row) => sum + row.luas, 0),
  };
});

const listRows = computed(() => [...bars.value].reverse());

function num(value: number, digits = 1) {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString("id-ID", { maximumFractionDigits: digits });
}

function metricLine(row: { rotasi: number; putaran: number; luas: number; pokok: number }) {
  return `Rotasi ${num(row.rotasi)} · Luas Panen ${num(row.luas)} ha`;
}
</script>

<template>
  <section class="bp-card p-5">
    <div class="mb-3 flex items-baseline justify-between gap-3">
      <h2 class="text-18 font-bold text-[#1f2a18]">Rotasi</h2>
    </div>

    <div v-if="loading && !bars.length && !kegiatan?.length"
      class="flex h-[180px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="kegiatan && !kegiatan.length" class="py-10 text-center text-13 text-[#6e7866]">Belum ada data rotasi
      untuk periode ini.</p>
    <ul v-else-if="kegiatan" class="space-y-0 pr-1" :class="expanded ? '' : 'max-h-[320px] overflow-y-auto'">
      <li v-for="(row, index) in kegiatan" :key="`${row.tanggal}-${row.rotasi}-${index}`"
        class="border-t border-[#e4e8de] py-2 first:border-t-0">
        <div class="flex items-baseline justify-between gap-3">
          <p class="text-14 font-semibold text-[#1f2a18]">{{ formatTanggal(row.tanggal) }}</p>
          <p class="text-14 font-semibold tabular-nums text-[#1f2a18]">{{ num(row.hari) }} hari</p>
        </div>
        <TruncatedText tag="p" class="text-12 font-medium text-[#6e7866]" :text="activityLine(row)" />
      </li>
    </ul>
    <p v-else-if="!bars.length" class="py-10 text-center text-13 text-[#6e7866]">Belum ada data rotasi untuk scope ini.
    </p>

    <template v-else>
      <div v-if="totals" class="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-2">
        <div class="rounded-lg bg-[#eef2e8] px-3 py-2">
          <p class="text-11 text-[#6e7866]">Periode</p>
          <p class="text-14 font-semibold text-[#1f2a18]">{{ totals.period }}</p>
        </div>
        <div class="rounded-lg bg-[#eef2e8] px-3 py-2">
          <p class="text-11 text-[#6e7866]">Rata-rata pusingan</p>
          <p class="text-14 font-semibold tabular-nums text-[#638840]">{{ num(totals.hari) }} hari</p>
        </div>
        <div class="rounded-lg bg-[#eef2e8] px-3 py-2">
          <p class="text-11 text-[#6e7866]">Rotasi</p>
          <p class="text-14 font-semibold tabular-nums text-[#1f2a18]">{{ num(totals.rotasi) }}</p>
        </div>
        <div class="rounded-lg bg-[#eef2e8] px-3 py-2">
          <p class="text-11 text-[#6e7866]">Luas Panen</p>
          <p class="text-14 font-semibold tabular-nums text-[#1f2a18]">{{ num(totals.luas) }} ha</p>
        </div>
      </div>

      <div class="relative" role="img"
        :aria-label="`Rata-rata pusingan: ${bars.map((bar) => `${bar.label} ${num(bar.hari)} hari`).join(', ')}`">
        <div class="flex h-[140px] items-end gap-1 border-b border-[#d5dcc8]">
          <div v-for="bar in bars" :key="bar.key"
            class="group relative flex h-full min-w-0 flex-1 flex-col items-center justify-end"
            @mouseenter="hovered = bar.key" @mouseleave="hovered = null">
            <span class="mb-1 text-11 tabular-nums text-[#1f2a18]"
              :class="bar.latest || hovered === bar.key ? 'font-semibold' : ''">
              {{ num(bar.hari) }}
            </span>
            <div class="w-full max-w-[36px] rounded-t-[4px] transition-colors"
              :class="bar.latest ? 'bg-[#638840]' : hovered === bar.key ? 'bg-[#d87633]' : 'bg-[#c5d4b4]'"
              :style="{ height: `${bar.height}%` }" />
          </div>
        </div>
        <div class="mt-2 flex gap-1">
          <span v-for="bar in bars" :key="`y-${bar.key}`"
            class="min-w-0 flex-1 truncate text-center text-11 tabular-nums"
            :class="bar.latest ? 'font-semibold text-[#1f2a18]' : 'text-[#6e7866]'">{{ bar.short }}</span>
        </div>
      </div>

      <!-- <div class="mt-3 flex items-center justify-between gap-2 text-12 text-[#6e7866]">
        <span>Luas {{ num(latest?.luas ?? 0) }} ha · {{ num(latest?.pokok ?? 0, 0) }} pokok</span>
        <span>{{ bars.length }} periode</span>
      </div> -->

      <ul class="mt-3 space-y-0 pr-1" :class="expanded ? '' : 'max-h-[220px] overflow-y-auto'">
        <li v-for="bar in listRows" :key="`row-${bar.key}`" class="border-t border-[#e4e8de] py-2">
          <div class="flex items-baseline justify-between gap-3">
            <p class="text-14 font-semibold text-[#1f2a18]" :class="bar.latest && 'text-[#638840]'">{{ bar.label }}</p>
            <p class="text-14 font-semibold tabular-nums text-[#1f2a18]">{{ num(bar.hari) }} hari</p>
          </div>
          <TruncatedText tag="p" class="text-12 font-medium text-[#6e7866]" :text="metricLine(bar)" />
        </li>
      </ul>
    </template>
  </section>
</template>
