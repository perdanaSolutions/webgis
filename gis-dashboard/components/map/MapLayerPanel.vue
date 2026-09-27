<script setup lang="ts">
import { ref } from "vue";

import { BASEMAPS, type BasemapKey, type LegendItem } from "~/utils/mapLayers";

export type OverlayListItem = {
  code: string;
  name: string;
  geometryType: string;
  color: string;
  enabled: boolean;
  loading: boolean;
  count: number | null;
  period: string;
  error: string;
  legend: LegendItem[];
};

defineProps<{
  basemap: BasemapKey;
  overlays: OverlayListItem[];
  blockCount: number;
  showBlocks: boolean;
}>();

const emit = defineEmits<{
  (e: "update:basemap", value: BasemapKey): void;
  (e: "toggle-overlay", code: string): void;
  (e: "toggle-blocks"): void;
}>();

const isOpen = ref(false);

function geometryIcon(type: string) {
  const t = type.toUpperCase();
  if (t.includes("POINT")) return "point";
  if (t.includes("LINE")) return "line";
  return "polygon";
}
</script>

<template>
  <div class="map-layer-panel pointer-events-auto flex flex-col items-end gap-2">
    <button type="button"
      class="inline-flex h-10 items-center gap-2 rounded-xl border border-map-light bg-surface px-3 text-13 font-semibold text-gray-title shadow-md hover-bg-hover-slate"
      :aria-expanded="isOpen" aria-label="Pengaturan layer peta" @click="isOpen = !isOpen">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-blue-primary" fill="none" viewBox="0 0 24 24"
        stroke="currentColor" stroke-width="1.8">
        <path stroke-linecap="round" stroke-linejoin="round" d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" />
      </svg>
      Layer
      <span class="text-11 text-gray-muted">{{ isOpen ? "▴" : "▾" }}</span>
    </button>

    <div v-if="isOpen"
      class="w-[300px] max-h-[70vh] overflow-y-auto rounded-2xl border border-map-light bg-surface p-3 shadow-xl">
      <p class="mb-2 text-11 font-semibold uppercase tracking-wide text-gray-muted">
        Peta Dasar
      </p>
      <div class="grid grid-cols-3 gap-2">
        <button v-for="option in BASEMAPS" :key="option.key" type="button"
          class="group flex flex-col items-center gap-1 rounded-lg p-1 text-center"
          :class="option.key === basemap ? 'ring-2 ring-[#2B7FFF]' : 'hover-bg-hover-slate'"
          @click="emit('update:basemap', option.key)">
          <span class="h-10 w-full rounded-md border border-map-light" :style="{ background: option.preview }" />
          <span class="text-11 leading-tight"
            :class="option.key === basemap ? 'font-bold text-blue-primary' : 'text-gray-label'">
            {{ option.label }}
          </span>
        </button>
      </div>

      <p class="mb-2 mt-4 text-11 font-semibold uppercase tracking-wide text-gray-muted">
        Layer Data
      </p>

      <label class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover-bg-hover-slate">
        <input type="checkbox" class="h-4 w-4 accent-[#2B7FFF]" :checked="showBlocks" @change="emit('toggle-blocks')">
        <span class="h-3.5 w-3.5 shrink-0 rounded-sm border border-[#1e293b]" style="background:#2e7d32aa" />
        <span class="min-w-0 flex-1 truncate text-13 font-medium text-gray-darker">Batas Blok</span>
        <span class="text-11 text-gray-muted">{{ blockCount }}</span>
      </label>

      <div v-for="item in overlays" :key="item.code" class="rounded-lg">
        <label class="flex cursor-pointer items-center gap-2 px-2 py-1.5 hover-bg-hover-slate">
          <input type="checkbox" class="h-4 w-4 accent-[#2B7FFF]" :checked="item.enabled"
            @change="emit('toggle-overlay', item.code)">
          <span v-if="geometryIcon(item.geometryType) === 'point'" class="h-3 w-3 shrink-0 rounded-full"
            :style="{ background: item.color }" />
          <span v-else-if="geometryIcon(item.geometryType) === 'line'" class="h-1 w-3.5 shrink-0 rounded-full"
            :style="{ background: item.color }" />
          <span v-else class="h-3.5 w-3.5 shrink-0 rounded-sm" :style="{ background: item.color }" />
          <span class="min-w-0 flex-1 truncate text-13 font-medium text-gray-darker">{{ item.name }}</span>
          <span v-if="item.loading"
            class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-blue-primary border-t-transparent" />
          <span v-else-if="item.enabled && item.count !== null" class="text-11 text-gray-muted">
            {{ item.count.toLocaleString("id-ID") }}
          </span>
        </label>

        <div v-if="item.enabled && !item.loading" class="pb-1.5 pl-8 pr-2">
          <p v-if="item.error" class="text-11 text-[#dc2626]">{{ item.error }}</p>
          <p v-else-if="item.count === 0" class="text-11 text-gray-muted">Tidak ada data untuk filter ini</p>
          <template v-else>
            <p v-if="item.period" class="text-11 text-gray-muted">Periode {{ item.period }}</p>
            <div v-if="item.legend.length" class="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
              <span v-for="entry in item.legend" :key="entry.label"
                class="inline-flex items-center gap-1 text-11 text-gray-label">
                <span class="h-2.5 w-2.5 rounded-sm" :style="{ background: entry.color }" />
                {{ entry.label }}
              </span>
            </div>
          </template>
        </div>
      </div>

      <p v-if="!overlays.length" class="px-2 py-1 text-12 text-gray-muted">Memuat daftar layer...</p>
    </div>
  </div>
</template>
