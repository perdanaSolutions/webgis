<script setup lang="ts">
import { computed } from "vue";

import TruncatedText from "~/components/blok-profile/TruncatedText.vue";

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
    filter: { pt: string; estate: string; afdeling: string; blok: string };
  };
  detail: Record<string, any> | null;
  loading: boolean;
}>();

const STATUS: Record<string, { label: string; tone: string }> = {
  TM: { label: "Menghasilkan", tone: "bg-[#e7f0dc] text-[#3f6a24]" },
  TBM: { label: "Belum Menghasilkan", tone: "bg-[#f6ecd6] text-[#8a5a14]" },
  LC: { label: "Land Clearing", tone: "bg-[#f1e7df] text-[#7a4a2a]" },
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

function num(value: unknown, digits = 1) {
  const n = Number(value);
  return Number.isFinite(n) && n !== 0 ? n.toLocaleString("id-ID", { maximumFractionDigits: digits }) : "-";
}

const status = computed(() => STATUS[props.summary.status?.toUpperCase()] ?? null);

const filterRows = computed(() => [
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
  const periode = String(props.detail?.areal_statement?.periode ?? "");
  const [m, y] = periode.split("-");
  return [
    ...filterRows.value,
    kerangka,
    { label: "Luas Tanam", value: props.summary.luas ? `${num(props.summary.luas)} Ha` : "-" },
    { label: "Tahun Tanam", value: info.tahun_tanam ?? "-" },
    { label: "Jenis Tanah", value: info.jenis_tanah ?? "-" },
    { label: "Bibit", value: info.jenis_bibit ?? "-" },
    { label: "Pembaruan", value: y ? `${MONTHS[Number(m) - 1] ?? m} ${y}` : "-" },
  ];
});
</script>

<template>
  <section class="bp-card p-5" aria-live="polite">
    <div class="flex flex-wrap items-start justify-between gap-2 border-b border-[#eadfce] pb-4">
      <div class="min-w-0 flex-1 basis-[160px]">
        <TruncatedText tag="h2" class="text-[22px] font-bold leading-tight tracking-tight text-[#2b2118] sm:text-[26px]"
          :text="summary.title || '-'" />
        <TruncatedText tag="p" class="text-14 text-[#8a7a68]" :text="summary.subtitle" />
      </div>
      <span v-if="status" class="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1 text-12 font-semibold"
        :class="status.tone">
        <span class="h-1.5 w-1.5 rounded-full bg-current" />{{ status.label }}
      </span>
      <span v-else-if="summary.kind === 'scope'"
        class="shrink-0 rounded-lg bg-[#f6efe4] px-2.5 py-1 text-12 font-semibold text-[#6b5a48]">
      </span>
    </div>

    <dl class="mt-4 grid grid-cols-2 gap-x-6 gap-y-3" :class="loading && 'animate-pulse'">
      <div v-for="row in rows" :key="row.label" class="min-w-0">
        <dt class="text-12 text-[#8a7a68]">{{ row.label }}</dt>
        <TruncatedText tag="dd" class="text-15 font-semibold text-[#2b2118]" :text="String(row.value)" />
      </div>
    </dl>
  </section>
</template>
