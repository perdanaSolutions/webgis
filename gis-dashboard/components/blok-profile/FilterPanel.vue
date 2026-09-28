<script setup lang="ts">
import { computed } from "vue";

import type { OverlayLayer } from "~/composables/useMapOverlays";
import type { Option, ScopeLevel } from "~/stores/blokProfileStore";
import { BASEMAPS, type BasemapKey } from "~/utils/mapLayers";

const props = defineProps<{
  areaOptions: Option[];
  estateOptions: Option[];
  afdelingOptions: Option[];
  blokOptions: Option[];
  area: string;
  estate: string;
  afdeling: string;
  blokId: string;
  scopeLevel: ScopeLevel;
  blockCount: number;
  loading: boolean;
  layers: OverlayLayer[];
  showBlocks: boolean;
  basemap: BasemapKey;
  opacity: number; // 0..100
}>();

const emit = defineEmits<{
  (e: "update:area" | "update:estate" | "update:afdeling" | "update:blok", value: string): void;
  (e: "reset"): void;
  (e: "toggle-layer", code: string): void;
  (e: "toggle-blocks"): void;
  (e: "update:basemap", value: BasemapKey): void;
  (e: "update:opacity", value: number): void;
}>();

const SCOPE_TEXT: Record<ScopeLevel, string> = {
  semua: "Semua wilayah yang Anda akses",
  area: "Area",
  estate: "Estate",
  afdeling: "Afdeling",
  blok: "Blok",
};

const scopeInfo = computed(() => props.scopeLevel === "blok"
  ? "Scope aktif: Blok — data tidak diagregasi"
  : `Scope aktif: ${SCOPE_TEXT[props.scopeLevel]} — agregasi ${props.blockCount.toLocaleString("id-ID")} blok`);

const activeCount = computed(() => props.layers.filter((l) => l.enabled).length + (props.showBlocks ? 1 : 0));
const totalCount = computed(() => props.layers.length + 1);

function unitOf(type: string) {
  const t = type.toUpperCase();
  return t.includes("POINT") ? "titik" : t.includes("LINE") ? "garis" : "poligon";
}

function subtitleOf(layer: OverlayLayer) {
  if (layer.loading) return "memuat…";
  if (layer.error) return layer.error;
  if (!layer.enabled || layer.count === null) return unitOf(layer.geometryType);
  const count = `${layer.count.toLocaleString("id-ID")} ${unitOf(layer.geometryType)}`;
  return layer.period ? `${count} · ${layer.period}` : count;
}

const fields = computed(() => [
  { key: "area" as const, label: "Area", value: props.area, options: props.areaOptions, placeholder: "Pilih area", disabled: false },
  { key: "estate" as const, label: "Estate", value: props.estate, options: props.estateOptions, placeholder: "Semua estate", disabled: !props.area },
  { key: "afdeling" as const, label: "Afdeling", value: props.afdeling, options: props.afdelingOptions, placeholder: "Semua afdeling", disabled: !props.estate },
  { key: "blok" as const, label: "Blok", value: props.blokId, options: props.blokOptions, placeholder: "Pilih blok di peta", disabled: !props.blokOptions.length },
]);

function onField(key: "area" | "estate" | "afdeling" | "blok", value: string) {
  emit(`update:${key}` as any, value);
}
</script>

<template>
  <div class="bp-card flex h-full flex-col overflow-hidden">
    <div class="flex-1 overflow-y-auto">
      <!-- FILTER -->
      <section class="px-5 pb-5 pt-5">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="bp-section-title">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" />
              <circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" />
            </svg>
            Filter Kebun
          </h2>
          <button type="button" class="text-13 font-semibold text-[#6b4a2e] hover:underline disabled:opacity-40"
            :disabled="loading" @click="emit('reset')">Reset</button>
        </div>

        <label v-for="field in fields" :key="field.key" class="mb-3 block">
          <span class="bp-label">{{ field.label }}</span>
          <div class="relative">
            <select class="bp-select" :value="field.value" :disabled="field.disabled || loading"
              @change="onField(field.key, ($event.target as HTMLSelectElement).value)">
              <option v-if="field.key !== 'area'" value="">{{ field.placeholder }}</option>
              <option v-else-if="!field.value" value="" disabled>{{ field.placeholder }}</option>
              <option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <svg class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6b5a48]" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </div>
        </label>

        <div class="mt-4 flex items-start gap-2 rounded-xl bg-[#f6efe4] px-3.5 py-3 text-13 text-[#6b5a48]">
          <svg viewBox="0 0 24 24" class="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="9" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
          </svg>
          <span>{{ scopeInfo }}</span>
        </div>
      </section>

      <!-- LAYER DATA -->
      <section class="border-t border-[#eadfce] px-5 py-5">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="bp-section-title">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linejoin="round" d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" />
            </svg>
            Layer Data
          </h2>
          <span class="text-13 font-semibold text-[#6b5a48]">{{ activeCount }} / {{ totalCount }} aktif</span>
        </div>

        <ul class="space-y-1">
          <li class="bp-layer-row">
            <span class="bp-layer-icon" :style="{ color: '#5a3a1c' }">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 18c3-8 7-12 16-14M6 20l-2-2" /></svg>
            </span>
            <div class="min-w-0 flex-1" :class="!showBlocks && 'opacity-60'">
              <p class="bp-layer-name">Batas Blok</p>
              <p class="bp-layer-sub">{{ blockCount.toLocaleString('id-ID') }} poligon</p>
            </div>
            <button type="button" role="switch" :aria-checked="showBlocks" aria-label="Batas Blok" class="bp-switch"
              :class="showBlocks && 'is-on'" @click="emit('toggle-blocks')"><span /></button>
          </li>

          <li v-for="layer in layers" :key="layer.code" class="bp-layer-row">
            <span class="bp-layer-icon" :style="{ color: layer.style.defaultColor }">
              <svg v-if="layer.geometryType.toUpperCase().includes('POINT')" viewBox="0 0 24 24" class="h-4 w-4" fill="none"
                stroke="currentColor" stroke-width="2"><path d="M12 21s-7-6.5-7-11a7 7 0 1 1 14 0c0 4.5-7 11-7 11Z" /><circle cx="12" cy="10" r="2.5" /></svg>
              <svg v-else-if="layer.geometryType.toUpperCase().includes('LINE')" viewBox="0 0 24 24" class="h-4 w-4" fill="none"
                stroke="currentColor" stroke-width="2"><path d="M4 20 10 4l4 10 6-6" /></svg>
              <svg v-else viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linejoin="round" d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5" /></svg>
            </span>
            <div class="min-w-0 flex-1" :class="!layer.enabled && 'opacity-60'">
              <p class="bp-layer-name">{{ layer.name }}</p>
              <p class="bp-layer-sub" :class="layer.error && 'text-[#b42318]'">{{ subtitleOf(layer) }}</p>
            </div>
            <span v-if="layer.loading" class="mr-1 h-4 w-4 animate-spin rounded-full border-2 border-[#6b4a2e] border-t-transparent" />
            <button type="button" role="switch" :aria-checked="layer.enabled" :aria-label="layer.name" class="bp-switch"
              :class="layer.enabled && 'is-on'" @click="emit('toggle-layer', layer.code)"><span /></button>
          </li>
        </ul>
      </section>

      <!-- BASEMAP -->
      <section class="border-t border-[#eadfce] px-5 py-5">
        <h2 class="bp-section-title mb-3">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linejoin="round" d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Zm6-3v15m6-12v15" />
          </svg>
          Basemap
        </h2>
        <div class="relative">
          <select class="bp-select" :value="basemap" aria-label="Basemap"
            @change="emit('update:basemap', ($event.target as HTMLSelectElement).value as BasemapKey)">
            <option v-for="option in BASEMAPS" :key="option.key" :value="option.key">{{ option.label }}</option>
          </select>
          <svg class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#6b5a48]" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
        </div>

        <label class="mt-4 block">
          <span class="flex items-center justify-between text-13 text-[#6b5a48]">
            Opasitas layer <strong class="text-[#2b2118]">{{ opacity }}%</strong>
          </span>
          <input type="range" min="10" max="100" step="5" class="bp-range mt-2 w-full" :value="opacity"
            :style="{ '--fill': `${((opacity - 10) / 90) * 100}%` }"
            @input="emit('update:opacity', Number(($event.target as HTMLInputElement).value))">
        </label>
      </section>
    </div>
  </div>
</template>
