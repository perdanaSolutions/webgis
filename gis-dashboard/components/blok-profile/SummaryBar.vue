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
    pokok: number;
    produksiTon: number | null;
    produksiTahun: number | null;
  };
  detail: Record<string, any> | null;
}>();

const emit = defineEmits<{ (e: "open-detail"): void }>();

const STATUS: Record<string, string> = { TM: "Menghasilkan", TBM: "Belum Menghasilkan", LC: "Land Clearing" };

const caption = computed(() => {
  if (props.summary.kind === "scope") return props.summary.subtitle;
  const info = props.detail?.informasi_blok ?? {};
  return [STATUS[props.summary.status?.toUpperCase()] ?? props.summary.status,
  info.tahun_tanam ? `Tahun tanam ${info.tahun_tanam}` : null, info.jenis_bibit ? `Bibit ${info.jenis_bibit}` : null]
    .filter(Boolean).join(" · ");
});

const heading = computed(() => props.summary.kind === "blok"
  ? `${props.summary.title}${props.summary.subtitle ? ` · ${props.summary.subtitle.split(" · ")[0]}` : ""}`
  : props.summary.title);

function fmt(value: number | null, digits = 1) {
  return value ? value.toLocaleString("id-ID", { maximumFractionDigits: digits }) : "-";
}
</script>

<template>
  <div class="bp-card flex items-center gap-4 px-4 py-3">
    <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#638840] text-white">
      <svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
        <path stroke-linejoin="round" d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 9 8-4.5M12 12v9m0-9L4 7.5" />
      </svg>
    </span>
    <div class="min-w-0 flex-1">
      <TruncatedText tag="p" class="text-16 font-bold text-[#1f2a18]" :text="heading" />
      <TruncatedText tag="p" class="text-13 text-[#6e7866]" :text="caption" />
    </div>
    <dl class="hidden shrink-0 items-center gap-6 xl:flex">
      <div class="text-right">
        <dd class="text-18 font-bold tabular-nums text-[#1f2a18]">{{ fmt(summary.luas) }} Ha</dd>
        <dt class="text-12 text-[#6e7866]">Luas</dt>
      </div>
      <div class="text-right">
        <dd class="text-18 font-bold tabular-nums text-[#1f2a18]">{{ fmt(summary.pokok, 0) }}</dd>
        <dt class="text-12 text-[#6e7866]">Pokok</dt>
      </div>
      <div class="text-right">
        <dd class="text-18 font-bold tabular-nums text-[#1f2a18]">{{ fmt(summary.produksiTon, 0) }} t</dd>
        <dt class="text-12 text-[#6e7866]">Produksi{{ summary.produksiTahun ? ` ${summary.produksiTahun}` : "" }}</dt>
      </div>
    </dl>
    <!-- ini belum di eksekusi jangan di edit2  -->
    <!-- <button type="button"
      class="inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-[#638840] px-5 text-14 font-semibold text-white hover:bg-[#527036] disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="summary.kind !== 'blok'" :title="summary.kind !== 'blok' ? 'Pilih blok di peta terlebih dahulu' : ''"
      @click="emit('open-detail')">
      Buka Detail
      <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8" /></svg>
    </button> -->
  </div>
</template>
