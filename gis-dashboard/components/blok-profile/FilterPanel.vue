<script setup lang="ts">
import { computed } from "vue";

import type { OverlayLayer } from "~/composables/useMapOverlays";
import type { Option, ScopeLevel } from "~/stores/blokProfileStore";
import { BASEMAPS, BUDGET_GAP_LAYERS, type BasemapKey } from "~/utils/mapLayers";
import { BULAN_POPUP_OPTIONS } from "~/utils/mapBlokPopup";

type FieldKey = "area" | "pt" | "estate" | "afdeling" | "blok" | "ownership";

const props = defineProps<{
  areaOptions: Option[];
  ptOptions: Option[];
  estateOptions: Option[];
  afdelingOptions: Option[];
  blokOptions: Option[];
  ownershipOptions: Option[];
  area: string;
  pt: string;
  estate: string;
  afdeling: string;
  blokId: string;
  ownership: string;
  bulan: string;
  tahun: string;
  scopeLevel: ScopeLevel;
  blockCount: number;
  loading: boolean;
  layers: OverlayLayer[];
  showBlocks: boolean;
  showYieldGap: boolean;
  basemap: BasemapKey;
  opacity: number; // 0..100
  /** Hanya superadmin@plantation.com. User biasa tidak melihat opsi "semua". */
  allowAll: boolean;
  /** Naik setiap filter dikosongkan, supaya input tidak menahan pilihan lama. */
  filterGeneration: number;
  /** Bagian yang ditampilkan. Tiap tombol collapse membuka satu bagian. */
  section: "filter" | "layer" | "basemap";
}>();

const emit = defineEmits<{
  (e: "update:area" | "update:pt" | "update:estate" | "update:afdeling" | "update:blok" | "update:ownership" | "update:bulan" | "update:tahun", value: string): void;
  (e: "apply"): void;
  (e: "reset"): void;
  (e: "toggle-layer", code: string): void;
  (e: "toggle-blocks"): void;
  (e: "toggle-yield-gap"): void;
  (e: "update:basemap", value: BasemapKey): void;
  (e: "update:opacity", value: number): void;
}>();

const SCOPE_TEXT: Record<ScopeLevel, string> = {
  semua: "Semua wilayah yang Anda akses",
  area: "Area",
  pt: "Perusahaan",
  estate: "Estate",
  afdeling: "Afdeling",
  blok: "Blok",
};

const monthOptions = [{ label: "Semua bulan", value: "" }, ...BULAN_POPUP_OPTIONS];
const yearOptions = computed(() => {
  const current = new Date().getFullYear();
  return Array.from({ length: 11 }, (_, index) => {
    const value = String(current - index);
    return { label: value, value };
  });
});

const scopeInfo = computed(() => {
  const month = BULAN_POPUP_OPTIONS.find((item) => item.value === props.bulan)?.label ?? "";
  const periode = [month, props.tahun].filter(Boolean).join(" ");
  const extra = [props.ownership, periode].filter(Boolean);
  const suffix = extra.length ? ` · ${extra.join(" · ")}` : "";
  const base = props.scopeLevel === "blok"
    ? `Pilihan: Blok${suffix}`
    : `Pilihan: ${SCOPE_TEXT[props.scopeLevel]}${suffix} · ${props.blockCount.toLocaleString("id-ID")} blok di peta terapan`;
  return `${base}. Tekan Apply Filter untuk memuat peta dan data transaksi.`;
});

const activeCount = computed(() => props.layers.filter((l) => l.enabled).length + (props.showBlocks ? 1 : 0) + (props.showYieldGap ? 1 : 0));
const totalCount = computed(() => props.layers.length + 2);

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

const HIERARCHY: FieldKey[] = ["area", "pt", "estate", "afdeling", "blok"];

const fields = computed(() => {
  const all = props.allowAll;
  return [
    { key: "area" as const, label: "Area", value: props.area, options: props.areaOptions, placeholder: all ? "Semua area" : "Pilih area", disabled: false },
    { key: "pt" as const, label: "Perusahaan (PT)", value: props.pt, options: props.ptOptions, placeholder: all ? "Semua perusahaan" : "Pilih perusahaan", disabled: !props.area },
    { key: "estate" as const, label: "Estate", value: props.estate, options: props.estateOptions, placeholder: all ? "Semua estate" : "Pilih estate", disabled: !props.pt },
    { key: "afdeling" as const, label: "Afdeling", value: props.afdeling, options: props.afdelingOptions, placeholder: all ? "Semua afdeling" : "Pilih afdeling", disabled: !props.estate },
    { key: "blok" as const, label: "Blok", value: props.blokId, options: props.blokOptions, placeholder: all ? "Semua blok" : "Pilih blok", disabled: !props.afdeling },
    { key: "ownership" as const, label: "Ownership", value: props.ownership, options: props.ownershipOptions, placeholder: "Semua ownership", disabled: false },
  ];
});

function itemsOf(field: { key: FieldKey; options: Option[]; placeholder: string }) {
  const hierarchy = HIERARCHY.includes(field.key);
  if (hierarchy && !props.allowAll) return field.options;
  return [{ label: field.placeholder, value: "" }, ...field.options];
}

function onField(key: FieldKey, value: unknown) {
  emit(`update:${key}`, value == null ? "" : String(value));
}
</script>

<template>
  <div class="bp-card overflow-hidden">
    <!-- FILTER -->
    <section v-if="section === 'filter'" class="px-5 pb-5 pt-5">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="bp-section-title">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"
            aria-hidden="true">
            <path stroke-linecap="round" d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0" />
            <circle cx="16" cy="6" r="2" />
            <circle cx="10" cy="12" r="2" />
            <circle cx="18" cy="18" r="2" />
          </svg>
          Filter Kebun
        </h2>
        <button type="button" class="text-13 font-semibold text-[#638840] hover:underline disabled:opacity-40"
          :disabled="loading" @click="emit('reset')">Reset</button>
      </div>

      <template v-for="field in fields" :key="`${filterGeneration}-${field.key}`">
        <label class="mb-3 block w-full">
          <span class="bp-label">{{ field.label }}</span>
          <v-autocomplete class="bp-autocomplete" :model-value="field.value || null" :items="itemsOf(field)"
            item-title="label" item-value="value" :placeholder="field.placeholder" :disabled="field.disabled || loading"
            variant="solo" flat density="comfortable" hide-details single-line color="#638840" base-color="#d5dcc8"
            menu-icon="mdi-chevron-down" autocomplete="off" no-data-text="Tidak ditemukan"
            :menu-props="{ contentClass: 'bp-filter-menu' }" @update:model-value="onField(field.key, $event)" />
        </label>

        <div v-if="field.key === 'ownership'" class="mb-3">
          <span class="bp-label">Periode</span>
          <div class="grid grid-cols-2 gap-2">
            <v-autocomplete class="bp-autocomplete min-w-0" :model-value="bulan || null" :items="monthOptions"
              item-title="label" item-value="value" placeholder="Bulan" :disabled="loading" variant="solo" flat
              density="comfortable" hide-details single-line color="#638840" base-color="#d5dcc8"
              menu-icon="mdi-chevron-down" autocomplete="off" no-data-text="Tidak ditemukan"
              :menu-props="{ contentClass: 'bp-filter-menu' }"
              @update:model-value="emit('update:bulan', $event == null ? '' : String($event))" />
            <v-autocomplete class="bp-autocomplete min-w-0" :model-value="tahun || null" :items="yearOptions"
              item-title="label" item-value="value" placeholder="Tahun" :disabled="loading" variant="solo" flat
              density="comfortable" hide-details single-line color="#638840" base-color="#d5dcc8"
              menu-icon="mdi-chevron-down" autocomplete="off" no-data-text="Tidak ditemukan"
              :menu-props="{ contentClass: 'bp-filter-menu' }"
              @update:model-value="emit('update:tahun', $event == null ? '' : String($event))" />
          </div>
        </div>
      </template>

      <div class="mt-4 flex items-start gap-2 rounded-xl bg-[#eef3e7] px-3.5 py-3 text-13 text-[#55604c]">
        <svg viewBox="0 0 24 24" class="mt-0.5 h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2"
          aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
        </svg>
        <span>{{ scopeInfo }}</span>
      </div>

      <button type="button" class="bp-btn bp-btn-primary mt-4 h-11 w-full justify-center text-14"
        :disabled="loading || !area" @click="emit('apply')">
        <svg v-if="loading" viewBox="0 0 24 24" class="h-4 w-4 animate-spin" fill="none" stroke="currentColor"
          stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="9" class="opacity-25" />
          <path d="M21 12a9 9 0 0 1-9 9" />
        </svg>
        <span class="text-white">{{ loading ? "Menerapkan…" : "Apply Filter" }}</span>
      </button>
    </section>

    <!-- LAYER DATA -->
    <section v-if="section === 'layer'" class="px-5 py-5">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="bp-section-title">
          <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2"
            aria-hidden="true">
            <path stroke-linejoin="round" d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5" />
          </svg>
          Layer Data
        </h2>
        <span class="text-13 font-semibold text-[#55604c]">{{ activeCount }} / {{ totalCount }} aktif</span>
      </div>

      <ul class="space-y-1">
        <li class="bp-layer-row">
          <span class="bp-layer-icon" :style="{ color: '#638840' }">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 18c3-8 7-12 16-14M6 20l-2-2" />
            </svg>
          </span>
          <div class="min-w-0 flex-1" :class="!showBlocks && 'opacity-60'">
            <p class="bp-layer-name">Batas Blok</p>
            <p class="bp-layer-sub">{{ blockCount.toLocaleString('id-ID') }} poligon</p>
          </div>
          <button type="button" role="switch" :aria-checked="showBlocks" aria-label="Batas Blok" class="bp-switch"
            :class="showBlocks && 'is-on'" @click="emit('toggle-blocks')"><span /></button>
        </li>

        <li class="border-t border-[#e4eadc] pt-2">
          <div class="bp-layer-row">
            <span class="bp-layer-icon text-[#6e7866]">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linejoin="round" d="m12 3 8 4.5-8 4.5L4 7.5 12 3Z" />
                <path d="M5 13.5c2.2 1.2 4.6 1.2 7 0s4.8-1.2 7 0" />
                <path d="M5 17.5c2.2 1.2 4.6 1.2 7 0s4.8-1.2 7 0" />
              </svg>
            </span>
            <div class="min-w-0 flex-1" :class="!showYieldGap && 'opacity-60'">
              <p class="bp-layer-name">Yield Gap</p>
              <p class="bp-layer-sub">{{ showYieldGap ? "Blok diwarnai menurut kategori yield" : "Mati · batas blok tetap garis abu-abu" }}</p>
            </div>
            <button type="button" role="switch" :aria-checked="showYieldGap" aria-label="Yield Gap" class="bp-switch"
              :class="showYieldGap && 'is-on'" @click="emit('toggle-yield-gap')"><span /></button>
          </div>
          <ul v-if="showYieldGap" class="mb-2 ml-12 space-y-1.5 pr-1">
            <li v-for="item in BUDGET_GAP_LAYERS" :key="item.key" class="flex items-center gap-2 text-12 text-[#55604c]">
              <span class="h-3 w-3 shrink-0 rounded-[3px] ring-1 ring-black/10" :style="{ background: item.color }" />
              <span class="font-semibold text-[#1f2a18]">{{ item.label }}</span>
              <span class="truncate">{{ item.hint }}</span>
            </li>
          </ul>
        </li>

        <li v-for="layer in layers" :key="layer.code" class="bp-layer-row">
          <span class="bp-layer-icon" :style="{ color: layer.style.defaultColor }">
            <svg v-if="layer.geometryType.toUpperCase().includes('POINT')" viewBox="0 0 24 24" class="h-4 w-4"
              fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 21s-7-6.5-7-11a7 7 0 1 1 14 0c0 4.5-7 11-7 11Z" />
              <circle cx="12" cy="10" r="2.5" />
            </svg>
            <svg v-else-if="layer.geometryType.toUpperCase().includes('LINE')" viewBox="0 0 24 24" class="h-4 w-4"
              fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 20 10 4l4 10 6-6" />
            </svg>
            <svg v-else viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linejoin="round" d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5" />
            </svg>
          </span>
          <div class="min-w-0 flex-1" :class="!layer.enabled && 'opacity-60'">
            <p class="bp-layer-name">{{ layer.name }}</p>
            <p class="bp-layer-sub" :class="layer.error && 'text-[#b42318]'">{{ subtitleOf(layer) }}</p>
          </div>
          <span v-if="layer.loading"
            class="mr-1 h-4 w-4 animate-spin rounded-full border-2 border-[#638840] border-t-transparent" />
          <button type="button" role="switch" :aria-checked="layer.enabled" :aria-label="layer.name" class="bp-switch"
            :class="layer.enabled && 'is-on'" @click="emit('toggle-layer', layer.code)"><span /></button>
        </li>
      </ul>
    </section>

    <!-- BASEMAP -->
    <section v-if="section === 'basemap'" class="px-5 py-5">
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
        <svg class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#55604c]"
          viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </div>

      <label class="mt-4 block">
        <span class="flex items-center justify-between text-13 text-[#55604c]">
          Opasitas layer <strong class="text-[#1f2a18]">{{ opacity }}%</strong>
        </span>
        <input type="range" min="10" max="100" step="5" class="bp-range mt-2 w-full" :value="opacity"
          :style="{ '--fill': `${((opacity - 10) / 90) * 100}%` }"
          @input="emit('update:opacity', Number(($event.target as HTMLInputElement).value))">
      </label>
    </section>
  </div>
</template>
