<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import Header from "~/components/Header.vue";

import { useMapStore } from "~/stores/mapStore";

const { $api } = useNuxtApp();

defineOptions({
  name: "MapPage",
});

const mapStore = useMapStore();

type FilterKey =
  | "area"
  | "pt"
  | "estate"
  | "afdeling"
  | "blok";

const ALL_FILTER_VALUE = "__all__";
const ALL_FILTER_OPTION = { label: "All", value: ALL_FILTER_VALUE };

const HIERARCHICAL_FILTER_KEYS: FilterKey[] = [
  "pt",
  "estate",
  "afdeling",
  "blok",
];

const filterInputs = reactive<Record<FilterKey, string>>({
  area: "",
  pt: "",
  estate: "",
  afdeling: "",
  blok: "",
});

const filterOptions = computed(() => mapStore.filterOptions);
const filters = computed(() => mapStore.filters);
const summary = computed(() => mapStore.summary);
const isLoading = computed(() => mapStore.isLoading);
const isLoadingGeoJSON = computed(() => mapStore.loadingGeoJSON);
const loadingByField = computed<Record<FilterKey, boolean>>(() => ({
  area: mapStore.loadingArea,
  pt: mapStore.loadingPt,
  estate: mapStore.loadingEstate,
  afdeling: mapStore.loadingAfdeling,
  blok: mapStore.loadingBlok,
}));

const isFilterCollapsed = ref(false);

const selectedTemaData = ref("");
const selectedBulan = ref("");
const selectedTahun = ref(String(new Date().getFullYear()));

const temaDataOptions = ref<Array<{ label: string; value: string }>>([]);
const isTemaDataLoading = ref(false);

const bulanOptions = [
  { label: "Januari", value: "1" },
  { label: "Februari", value: "2" },
  { label: "Maret", value: "3" },
  { label: "April", value: "4" },
  { label: "Mei", value: "5" },
  { label: "Juni", value: "6" },
  { label: "Juli", value: "7" },
  { label: "Agustus", value: "8" },
  { label: "September", value: "9" },
  { label: "Oktober", value: "10" },
  { label: "November", value: "11" },
  { label: "Desember", value: "12" },
];

const tahunOptions = computed<Array<{ label: string; value: string }>>(() => {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: 11 }, (_, index) => {
    const year = currentYear - index;
    return { label: String(year), value: String(year) };
  });
});

function toggleFilterCollapse() {
  isFilterCollapsed.value = !isFilterCollapsed.value;
}

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

function getAuthHeaders(): Record<string, string> {
  if (process.client) {
    const token = localStorage.getItem("token");
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
  }
  return {};
}

async function initTemaDataOptions() {
  isTemaDataLoading.value = true;
  try {
    const baseUrl = getApiBaseUrl();
    const response = await $api<any[]>(`${baseUrl}/v1/database/tables`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    const normalizedData = Array.isArray(response)
      ? response
      : ((response as any)?.data ?? []);

    temaDataOptions.value = normalizedData
      .map((item: any) => {
        if (typeof item === "string") {
          return { label: item, value: item };
        }

        const value =
          item?.table_name ||
          item?.tableName ||
          item?.name ||
          item?.value ||
          "";
        const label = item?.label || value;

        return value ? { label, value } : null;
      })
      .filter(Boolean) as Array<{ label: string; value: string }>;
  } catch (error) {
    temaDataOptions.value = [];
  } finally {
    isTemaDataLoading.value = false;
  }
}

// jangan di hapus
// const topTabs = ref([
//   { key: 'scorecard', label: 'Scorecard' },
//   { key: 'condition', label: 'Condition' },
//   { key: 'crop-indices', label: 'Crop Indices' },
//   { key: 'comparison', label: 'Comparison' },
//   { key: 'yield-projection', label: 'Yield Projection' },
// ])

function toAutocompleteModelValue(key: FilterKey, value: string) {
  if (HIERARCHICAL_FILTER_KEYS.includes(key) && !value) {
    return ALL_FILTER_VALUE;
  }

  return value;
}

function fromAutocompleteModelValue(key: FilterKey, value: string | null) {
  if (HIERARCHICAL_FILTER_KEYS.includes(key) && value === ALL_FILTER_VALUE) {
    return "";
  }

  return typeof value === "string" ? value : "";
}

function getAutocompleteModel(key: FilterKey) {
  return toAutocompleteModelValue(key, filterInputs[key]);
}

function setAutocompleteModel(key: FilterKey, value: string | null) {
  filterInputs[key] = fromAutocompleteModelValue(key, value);
}

function withAllOption(
  key: FilterKey,
  options: Array<{ label: string; value: string }>,
) {
  if (!HIERARCHICAL_FILTER_KEYS.includes(key) || options.length <= 1) {
    return options;
  }

  return [ALL_FILTER_OPTION, ...options];
}

const filterConfigs = computed<
  Array<{
    key: FilterKey;
    label: string;
    placeholder: string;
    options: Array<{ label: string; value: string }>;
    disabled: boolean;
    clearable: boolean;
  }>
>(() => [
  {
    key: "area",
    label: "Area",
    placeholder: "Ketik atau pilih Area",
    options: filterOptions.value.area,
    disabled: false,
    clearable: true,
  },
  {
    key: "pt",
    label: "Perusahaan (PT)",
    placeholder: "All",
    options: withAllOption("pt", filterOptions.value.pt),
    disabled: !filterInputs.area,
    clearable: false,
  },
  {
    key: "estate",
    label: "Estate",
    placeholder: "All",
    options: withAllOption("estate", filterOptions.value.estate),
    disabled: !filterInputs.area,
    clearable: false,
  },
  {
    key: "afdeling",
    label: "Afdeling",
    placeholder: "All",
    options: withAllOption("afdeling", filterOptions.value.afdeling),
    disabled: !filterInputs.area,
    clearable: false,
  },
  {
    key: "blok",
    label: "Blok",
    placeholder: "All",
    options: withAllOption("blok", filterOptions.value.blok),
    disabled: !filterInputs.area,
    clearable: false,
  },
]);

onMounted(async () => {
  await mapStore.loadGeoJSONData();
  await initTemaDataOptions();
});

function getSelectedLabelByKey(key: FilterKey): string {
  const value = filters.value[key] || "";
  if (!value) {
    return HIERARCHICAL_FILTER_KEYS.includes(key) ? "All" : "";
  }

  const option = filterOptions.value[key].find((item) => item.value === value);
  return option?.label ?? value;
}

const blockProfileRows = computed(() => [
  { label: "Area", value: getSelectedLabelByKey("area") },
  { label: "Perusahaan (PT)", value: getSelectedLabelByKey("pt") },
  { label: "Estate", value: getSelectedLabelByKey("estate") },
  { label: "Afdeling", value: getSelectedLabelByKey("afdeling") },
  { label: "Blok", value: getSelectedLabelByKey("blok") },
  { label: "Bibit", value: "" },
  { label: "Tahun Tanam", value: "" },
  { label: "Luas Kerangka", value: "" },
  { label: "Luas Tertanam", value: "" },
  { label: "Pokok", value: "" },
  { label: "SPH", value: "" },
]);

watch(
  filters,
  (currentFilters) => {
    filterInputs.area = currentFilters.area || "";
    filterInputs.pt = currentFilters.pt;
    filterInputs.estate = currentFilters.estate;
    filterInputs.afdeling = currentFilters.afdeling;
    filterInputs.blok = currentFilters.blok;
  },
  { immediate: true, deep: true },
);

function getOptionsByKey(key: FilterKey) {
  return filterOptions.value[key];
}

function normalizeAutocompleteValue(key: FilterKey, rawValue: string | null) {
  const value = fromAutocompleteModelValue(key, rawValue);
  const trimmed = value.trim();
  if (!trimmed) return "";

  const options = getOptionsByKey(key);
  const exact = options.find(
    (option) => option.value.toLowerCase() === trimmed.toLowerCase(),
  );
  if (exact) return exact.value;

  if (HIERARCHICAL_FILTER_KEYS.includes(key)) {
    const allMatch = trimmed.toLowerCase() === ALL_FILTER_OPTION.label.toLowerCase();
    if (allMatch) return "";
  }

  return "";
}

function applyAutocompleteNormalization(key: FilterKey) {
  const normalizedValue = normalizeAutocompleteValue(key, filterInputs[key]);
  filterInputs[key] = normalizedValue;
}

async function onFilterInputChange(key: FilterKey, rawValue?: string | null) {
  if (rawValue !== undefined) {
    setAutocompleteModel(key, rawValue);
  }

  const beforeValue = filters.value[key] || "";
  applyAutocompleteNormalization(key);
  const nextValue = filterInputs[key] || "";

  if (nextValue === beforeValue) return;

  if (key === "area") {
    await mapStore.setSelectedArea(filterInputs.area);
    return;
  }

  if (key === "pt") {
    await mapStore.setSelectedPt(filterInputs.pt);
    return;
  }

  if (key === "estate") {
    await mapStore.setSelectedEstate(filterInputs.estate);
    return;
  }

  if (key === "afdeling") {
    await mapStore.setSelectedAfdeling(filterInputs.afdeling);
    return;
  }

  mapStore.setSelectedBlok(filterInputs.blok);
}

function onAutoCompleteEnter(key: FilterKey, event: KeyboardEvent) {
  event.preventDefault();
  void onFilterInputChange(key);
}

async function applyAllFilters() {
  (Object.keys(filterInputs) as FilterKey[]).forEach(
    (key) => {
      applyAutocompleteNormalization(key);
    },
  );

  try {
    await mapStore.applyFilters({
      area: filterInputs.area,
      pt: filterInputs.pt,
      estate: filterInputs.estate,
      afdeling: filterInputs.afdeling,
      blok: filterInputs.blok,
    }, selectedTahun.value);
  } catch {
    // errorMessage sudah di-set di store
  }
}

async function resetAllFilters() {
  filterInputs.area = "";
  filterInputs.pt = "";
  filterInputs.estate = "";
  filterInputs.afdeling = "";
  filterInputs.blok = "";
  await mapStore.resetFilters();
}

async function gotoDashboard() {
  await navigateTo("/dashboard");
}
</script>

<template>
  <main class="min-h-screen bg-[#F7F8FA] text-[14px] text-[#2B2B2B]">
    <Header brand-title="Block Profile" brand-subtitle="" />

    <aside class="mx-4 mt-3 rounded-xl border border-[#E5EAF1] bg-white transition-all duration-300"
      :class="isFilterCollapsed ? 'overflow-hidden p-2' : 'p-3'">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex min-w-0 items-center gap-2">
          <button type="button"
            class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[#D8DEE8] bg-white text-[13px] text-[#334155] hover:bg-[#F8FAFC]"
            :title="isFilterCollapsed ? 'Expand Filter' : 'Collapse Filter'"
            :aria-label="isFilterCollapsed ? 'Expand Filter' : 'Collapse Filter'" @click="toggleFilterCollapse">
            <span v-if="isFilterCollapsed">▶</span>
            <span v-else>◀</span>
          </button>
          <div class="min-w-0">
            <p class="truncate text-[14px] font-bold text-[#1F2937]">
              Filter Data Spasial Blok
            </p>
            <p v-if="!isFilterCollapsed" class="text-[12px] text-[#6B7280]">
              Area kebun dan informasi blok
            </p>
          </div>
        </div>
      </div>

      <template v-if="!isFilterCollapsed">
        <div class="mt-3 space-y-3">
          <section>
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#6B7280]">
              Area
            </p>
            <div class="grid grid-cols-1 gap-x-3 gap-y-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              <label v-for="field in filterConfigs" :key="field.key" class="min-w-0">
                <span class="mb-1 block text-[13px] font-medium text-[#2F3A4A]">
                  {{ field.label }}
                </span>
                <v-autocomplete :model-value="getAutocompleteModel(field.key)" class="custom-underlined-input"
                  :items="field.options" item-title="label" item-value="value" :placeholder="field.placeholder"
                  variant="underlined" density="compact" bg-color="white" color="#2B7FFF" hide-details
                  :clearable="field.clearable" menu-icon="mdi-chevron-down" :loading="loadingByField[field.key]"
                  :disabled="field.disabled || loadingByField[field.key]"
                  @update:model-value="onFilterInputChange(field.key, $event)"
                  @keydown.enter.prevent="onAutoCompleteEnter(field.key, $event)" />
              </label>
            </div>
          </section>

          <section class="border-t border-[#EEF2F6] py-3">
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#6B7280]">
              Informasi
            </p>
            <div class="grid grid-cols-1 gap-x-3 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
              <label class="min-w-0">
                <span class="mb-1 block text-[13px] font-medium text-[#2F3A4A]">
                  Tema Data
                </span>
                <v-autocomplete v-model="selectedTemaData" class="custom-underlined-input" :items="temaDataOptions"
                  item-title="label" item-value="value" placeholder="Pilih Tema Data" variant="underlined"
                  density="compact" bg-color="white" color="#2B7FFF" hide-details clearable menu-icon="mdi-chevron-down"
                  :loading="isTemaDataLoading" />
              </label>
              <label class="min-w-0">
                <span class="mb-1 block text-[13px] font-medium text-[#2F3A4A]">
                  Tahun
                </span>
                <v-autocomplete v-model="selectedTahun" class="custom-underlined-input" :items="tahunOptions"
                  item-title="label" item-value="value" placeholder="Pilih Tahun" variant="underlined" density="compact"
                  bg-color="white" color="#2B7FFF" hide-details clearable menu-icon="mdi-chevron-down" />
              </label>
            </div>
          </section>

          <div v-if="!isFilterCollapsed" class="flex justify-end items-center gap-2">
            <button
              class="inline-flex h-8 items-center justify-center rounded-md border border-[#D8DEE8] bg-white px-3 text-[13px] font-semibold text-[#334155] hover:bg-[#F8FAFC] disabled:cursor-not-allowed"
              type="button" :disabled="isLoading" @click="resetAllFilters">
              Reset
            </button>
            <button
              class="inline-flex h-8 items-center justify-center rounded-md bg-[#2B7FFF] px-3 text-[13px] font-semibold text-white hover:bg-[#1E68DB] disabled:cursor-not-allowed disabled:bg-[#93B8F7]"
              type="button" :disabled="isLoading" @click="applyAllFilters">
              {{ isLoadingGeoJSON ? 'Memuat...' : 'Apply' }}
            </button>
          </div>
        </div>
      </template>
    </aside>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 p-4 lg:gap-5 lg:p-5">
      <section class="space-y-3">
        <div
          class="relative h-[65vh] sm:h-[70vh] lg:h-[72vh] min-h-[400px] sm:min-h-[520px] w-full overflow-hidden rounded-2xl border border-[#DCE3ED] bg-white shadow-sm transition-all duration-300">
          <!-- Wrapper untuk MapDashboard agar mengisi penuh area dan ramah perangkat sentuh -->
          <div class="absolute inset-0 h-full w-full">
            <MapDashboard class="h-full w-full object-cover" />
          </div>
        </div>
      </section>

      <aside class="space-y-3">
        <div class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
          <h2 class="mb-3 text-[16px] font-bold text-[#1F2937]">
            Block Profile
          </h2>
          <div class="space-y-1.5">
            <div v-for="item in blockProfileRows" :key="item.label"
              class="grid grid-cols-[120px_minmax(0,1fr)] items-start gap-2 rounded-md px-2 py-1.5 odd:bg-[#F8FAFC]">
              <p class="text-[14px] text-[#6B7280]">{{ item.label }}</p>
              <p class="truncate text-[14px] font-semibold text-[#111827]">
                {{ item.value }}
              </p>
            </div>
          </div>
        </div>

        <div class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
          <h2 class="mb-3 text-[16px] font-bold text-[#1F2937]">
            Data Informasi
          </h2>
        </div>
      </aside>
    </div>
  </main>
</template>
<style scoped>
.custom-underlined-input :deep(.v-field__outline) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.2) !important;
  opacity: 1 !important;
}

.custom-underlined-input :deep(.v-field) {
  font-size: 13px;
}

.custom-underlined-input :deep(.v-field__input) {
  min-height: 34px;
  padding-top: 2px;
  padding-bottom: 2px;
}

.custom-underlined-input :deep(.v-field__append-inner),
.custom-underlined-input :deep(.v-field__clearable) {
  padding-top: 0;
  padding-bottom: 0;
}
</style>
