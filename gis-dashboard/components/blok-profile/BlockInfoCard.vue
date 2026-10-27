<script setup lang="ts">
import { computed } from "vue";

import TruncatedText from "~/components/blok-profile/TruncatedText.vue";
import { blokDataPeriodLabel } from "~/utils/blokPeriodLabel";

const props = defineProps<{
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
    /** true = bulan periode dipilih di filter; false = data terbaru. */
    periodSpecific?: boolean;
  };
  detail: Record<string, any> | null;
  loading: boolean;
}>();

const STATUS: Record<string, { label: string; tone: string }> = {
  TM: { label: "Menghasilkan", tone: "bg-[#e5f0d8] text-[#3f5728]" },
  TBM: { label: "Belum Menghasilkan", tone: "bg-[#fbe8d8] text-[#b85f22]" },
  LC: { label: "Land Clearing", tone: "bg-[#f4ebe4] text-[#8a4e28]" },
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

function num(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) && n !== 0 ? n.toLocaleString("id-ID", { maximumFractionDigits: digits }) : "-";
}

const status = computed(() => STATUS[props.summary.status?.toUpperCase()] ?? null);

const geojsonPeriodLabel = computed(() =>
  blokDataPeriodLabel(props.summary.geojsonPeriod, Boolean(props.summary.periodSpecific)),
);

const filterRows = computed(() => [
  { label: "Grup", value: props.summary.filter.grup },
  { label: "PT", value: props.summary.filter.pt },
  { label: "Estate", value: props.summary.filter.estate },
  { label: "Afdeling", value: props.summary.filter.afdeling },
  { label: "Blok", value: props.summary.filter.blok },
]);

const rows = computed(() => {
  const kerangka = { label: "Luas Kerangka", value: props.summary.luasKerangka ? `${num(props.summary.luasKerangka, 2)} Ha` : "-" };
  if (props.summary.kind === "scope") {
    const sph = props.summary.luas ? props.summary.pokok / props.summary.luas : 0;
    return [
      ...filterRows.value,
      { label: "Jumlah Blok", value: props.summary.blokCount.toLocaleString("id-ID") },
      kerangka,
      { label: "Luas Tanam", value: `${num(props.summary.luas)} Ha` },
      { label: "Total Pokok", value: num(props.summary.pokok, 0) },
      { label: "SPH Rata-rata", value: num(sph, 0) },
    ];
  }
  const info = props.detail?.informasi_blok ?? {};
  const period = props.detail?.periode ?? {};
  const month = Number(period.bulan);
  const year = period.tahun;
  const updated = year ? `${month ? `${MONTHS[month - 1] ?? month} ` : ""}${year}` : "-";
  return [
    ...filterRows.value,
    kerangka,
    { label: "Luas Tanam", value: props.summary.luas ? `${num(props.summary.luas)} Ha` : "-" },
    { label: "SPH", value: num(info.sph, 0) },
    { label: "Tahun Tanam", value: info.tahun_tanam ?? "-" },
    { label: "Jenis Tanah", value: info.jenis_tanah ?? "-" },
    { label: "Bibit", value: info.jenis_bibit ?? "-" },
    { label: "Pembaruan", value: updated },
  ];
});
</script>

<template>
  <section class="bp-card p-5" aria-live="polite">
    <div class="flex flex-wrap items-start justify-between gap-2 border-b border-[#d5dcc8] pb-4">
      <div class="min-w-0 flex-1 basis-[160px]">
        <TruncatedText tag="h2" class="text-[22px] font-bold leading-tight tracking-tight text-[#1f2a18] sm:text-[26px]"
          :text="summary.title || '-'" />
        <TruncatedText tag="p" class="text-14 text-[#6e7866]" :text="summary.subtitle" />
        <p v-if="geojsonPeriodLabel" class="mt-2 text-13 leading-snug text-[#55604c]">
          {{ geojsonPeriodLabel }}
        </p>
      </div>
      <span v-if="status" class="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1 text-12 font-semibold"
        :class="status.tone">
        <span class="h-1.5 w-1.5 rounded-full bg-current" />{{ status.label }}
      </span>
      <span v-else-if="summary.kind === 'scope'"
        class="shrink-0 rounded-lg bg-[#eef3e7] px-2.5 py-1 text-12 font-semibold text-[#55604c]">
      </span>
    </div>

    <dl class="mt-4 grid grid-cols-2 gap-x-6 gap-y-3" :class="loading && 'animate-pulse'">
      <div v-for="row in rows" :key="row.label" class="min-w-0">
        <dt class="text-12 text-[#6e7866]">{{ row.label }}</dt>
        <TruncatedText tag="dd" class="text-15 font-semibold text-[#1f2a18]" :text="String(row.value)" />
      </div>
    </dl>
  </section>
</template>
