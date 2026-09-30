<script setup lang="ts">
import { computed, ref } from "vue";

import TruncatedText from "~/components/blok-profile/TruncatedText.vue";
import type { SlopeShare } from "~/stores/blokProfileStore";
import { SLOPE_RAMP } from "~/utils/mapLayers";

const props = defineProps<{ shares: SlopeShare[]; loading: boolean }>();

const COLOR_BY_KEY: Record<string, string> = {
  datar: SLOPE_RAMP["0-3"]!,
  gelombang: SLOPE_RAMP["3-8"]!,
  berbukit: SLOPE_RAMP["8-15"]!,
  curam: SLOPE_RAMP["15-25"]!,
  sangat: "#3a2412",
};

const RADIUS = 52;
const CIRC = 2 * Math.PI * RADIUS;
const GAP = 2; // jarak antarsegmen (px) agar batas kelas terbaca

const hovered = ref<string | null>(null);

const total = computed(() => props.shares.reduce((acc, s) => acc + s.value, 0));

const segments = computed(() => {
  let offset = 0;
  return props.shares.filter((s) => s.value > 0).map((s) => {
    const length = (s.value / (total.value || 1)) * CIRC;
    const seg = {
      ...s, color: COLOR_BY_KEY[s.key] ?? "#9c6f3a",
      dash: `${Math.max(length - GAP, 0.01)} ${CIRC}`, offset: -offset,
    };
    offset += length;
    return seg;
  });
});

/** "Layak tanam" = lereng <= 8% (datar + bergelombang). */
const layak = computed(() => {
  if (!total.value) return null;
  const ok = props.shares.filter((s) => s.key === "datar" || s.key === "gelombang").reduce((a, s) => a + s.value, 0);
  return Math.round((ok / total.value) * 100);
});

function pct(value: number) {
  return `${Math.round((value / (total.value || 1)) * 100)}%`;
}

function ha(value: number) {
  return `${value.toLocaleString("id-ID", { maximumFractionDigits: 2 })} ha`;
}
</script>

<template>
  <section class="bp-card p-5">
    <h2 class="mb-4 text-18 font-bold text-[#2b2118]">Analisa Kemiringan</h2>

    <div v-if="loading && !shares.length" class="flex h-[132px] items-center justify-center text-13 text-[#8a7a68]">Memuat…</div>
    <p v-else-if="!shares.length" class="py-8 text-center text-13 text-[#8a7a68]">Belum ada data kemiringan untuk scope ini.</p>

    <div v-else class="bp-slope-body flex items-center gap-4">
      <svg viewBox="0 0 132 132" class="h-[132px] w-[132px] shrink-0 -rotate-90" role="img"
        :aria-label="`Kemiringan: ${shares.map((s) => `${s.label} ${pct(s.value)}`).join(', ')}`">
        <circle cx="66" cy="66" :r="RADIUS" fill="none" stroke="#f3ece1" stroke-width="18" />
        <circle v-for="seg in segments" :key="seg.key" cx="66" cy="66" :r="RADIUS" fill="none" :stroke="seg.color"
          :stroke-width="hovered === seg.key ? 22 : 18" :stroke-dasharray="seg.dash" :stroke-dashoffset="seg.offset"
          class="cursor-pointer transition-[stroke-width]" @mouseenter="hovered = seg.key" @mouseleave="hovered = null">
          <title>{{ seg.label }} ({{ seg.range }}): {{ pct(seg.value) }}{{ seg.ha != null ? ` · ${ha(seg.ha)}` : "" }}</title>
        </circle>
        <g class="rotate-90" style="transform-origin: 66px 66px">
          <text x="66" y="66" text-anchor="middle" class="fill-[#2b2118] text-[22px] font-bold">{{ layak }}%</text>
          <text x="66" y="84" text-anchor="middle" class="fill-[#8a7a68] text-[11px]">layak ≤8%</text>
        </g>
      </svg>

      <ul class="min-w-0 flex-1 space-y-2">
        <li v-for="seg in segments" :key="seg.key" class="flex items-center gap-2 rounded-md px-1 text-14 transition"
          :class="hovered === seg.key && 'bg-[#f6efe4]'" @mouseenter="hovered = seg.key" @mouseleave="hovered = null">
          <span class="h-3 w-3 shrink-0 rounded-[3px] ring-1 ring-black/10" :style="{ background: seg.color }" />
          <TruncatedText class="flex-1 text-14 text-[#4a3a2c]" :text="`${seg.label} ${seg.range}`">
            {{ seg.label }} <span class="text-12 text-[#8a7a68]">{{ seg.range }}</span>
          </TruncatedText>
          <span class="font-semibold tabular-nums text-[#2b2118]">{{ pct(seg.value) }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>
