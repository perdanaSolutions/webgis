<script setup lang="ts">
import { computed, ref } from "vue";

import TruncatedText from "~/components/blok-profile/TruncatedText.vue";
import type { RotationActivity, RotationHistory } from "~/stores/blokProfileStore";

const props = defineProps<{ data: RotationHistory | null; loading: boolean }>();

const hovered = ref<number | null>(null);
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

const rows = computed(() =>
  (props.data?.data ?? [])
    .map((row) => ({
      tahun: Number(row.tahun),
      hari: Number(row.avg_pusingan_hari ?? 0),
      rotasi: Number(row.rotasi_terakhir ?? 0),
      putaran: Number(row.total_rotasi ?? 0),
      luas: Number(row.total_luas_rotasi ?? 0),
      pokok: Number(row.total_pokok_rotasi ?? 0),
    }))
    .filter((row) => Number.isFinite(row.tahun)),
);

const bars = computed(() => {
  const max = Math.max(...rows.value.map((row) => row.hari), 1);
  const latest = rows.value[rows.value.length - 1]?.tahun;
  return rows.value.map((row) => ({
    ...row,
    height: Math.max((row.hari / max) * 100, row.hari > 0 ? 4 : 0),
    latest: row.tahun === latest,
  }));
});

function num(value: number, digits = 1) {
  return value.toLocaleString("id-ID", { maximumFractionDigits: digits });
}
</script>

<template>
  <section class="bp-card p-5">
    <div class="mb-3 flex items-baseline justify-between">
      <h2 class="text-18 font-bold text-[#1f2a18]">Rotasi Pusingan</h2>
      <span class="text-12 text-[#6e7866]">hari</span>
    </div>

    <div v-if="loading && !bars.length && !kegiatan?.length" class="flex h-[180px] items-center justify-center text-13 text-[#6e7866]">Memuat…</div>
    <p v-else-if="kegiatan && !kegiatan.length" class="py-10 text-center text-13 text-[#6e7866]">Belum ada data rotasi untuk periode ini.</p>
    <ul v-else-if="kegiatan" class="max-h-[320px] space-y-0 overflow-y-auto pr-1">
      <li v-for="(row, index) in kegiatan" :key="`${row.tanggal}-${row.rotasi}-${index}`" class="border-t border-[#e4e8de] py-2 first:border-t-0">
        <div class="flex items-baseline justify-between gap-3">
          <p class="text-14 font-semibold text-[#1f2a18]">{{ formatTanggal(row.tanggal) }}</p>
          <p class="text-14 font-semibold tabular-nums text-[#1f2a18]">{{ num(row.hari) }} hari</p>
        </div>
        <TruncatedText tag="p" class="text-12 font-medium text-[#6e7866]" :text="activityLine(row)" />
      </li>
    </ul>
    <p v-else-if="!bars.length" class="py-10 text-center text-13 text-[#6e7866]">Belum ada data rotasi untuk scope ini.</p>

    <template v-else>
      <div class="relative" role="img"
        :aria-label="`Rata-rata pusingan: ${bars.map((bar) => `${bar.tahun} ${num(bar.hari)} hari`).join(', ')}`">
        <div class="flex h-[140px] items-end gap-1.5 border-b border-[#d5dcc8]">
          <div v-for="bar in bars" :key="bar.tahun" class="group relative flex h-full flex-1 flex-col items-center justify-end"
            @mouseenter="hovered = bar.tahun" @mouseleave="hovered = null">
            <span class="mb-1 text-11 tabular-nums"
              :class="bar.latest || hovered === bar.tahun ? 'font-semibold text-[#1f2a18]' : 'text-transparent'">
              {{ num(bar.hari) }}
            </span>
            <div class="w-full max-w-[36px] rounded-t-[4px] transition-colors"
              :class="bar.latest ? 'bg-[#638840]' : hovered === bar.tahun ? 'bg-[#d87633]' : 'bg-[#c5d4b4]'"
              :style="{ height: `${bar.height}%` }" />
          </div>
        </div>
        <div class="mt-2 flex gap-1.5">
          <span v-for="bar in bars" :key="`y-${bar.tahun}`" class="flex-1 text-center text-11 tabular-nums"
            :class="bar.latest ? 'font-semibold text-[#1f2a18]' : 'text-[#6e7866]'">{{ bar.tahun }}</span>
        </div>
      </div>

      <ul class="mt-4 max-h-[220px] space-y-0 overflow-y-auto pr-1">
        <li v-for="bar in [...bars].reverse()" :key="`row-${bar.tahun}`" class="border-t border-[#e4e8de] py-2">
          <div class="flex items-baseline justify-between gap-3">
            <p class="text-14 font-semibold text-[#1f2a18]" :class="bar.latest && 'text-[#638840]'">{{ bar.tahun }}</p>
            <p class="text-14 font-semibold tabular-nums text-[#1f2a18]">{{ num(bar.hari) }} hari</p>
          </div>
          <TruncatedText tag="p" class="text-12 font-medium text-[#6e7866]"
            :text="`Rotasi ${num(bar.rotasi)} · ${num(bar.putaran, 0)} putaran · ${num(bar.luas)} ha · ${num(bar.pokok, 0)} pokok`" />
        </li>
      </ul>
    </template>
  </section>
</template>
