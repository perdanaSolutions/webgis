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
const selectedTahun = ref("");

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

const filterConfigs = computed<
  Array<{
    key: FilterKey;
    label: string;
    placeholder: string;
    options: Array<{ label: string; value: string }>;
    disabled: boolean;
  }>
>(() => [
  {
    key: "area",
    label: "Area",
    placeholder: "Ketik atau pilih Area",
    options: filterOptions.value.area,
    disabled: false,
  },
  {
    key: "pt",
    label: "Perusahaan (PT)",
    placeholder: "Pilih Area terlebih dahulu",
    options: filterOptions.value.pt,
    disabled: !filterInputs.area,
  },
  {
    key: "estate",
    label: "Estate",
    placeholder: "Pilih Perusahaan terlebih dahulu",
    options: filterOptions.value.estate,
    disabled: !filterInputs.pt,
  },
  {
    key: "afdeling",
    label: "Afdeling",
    placeholder: "Pilih Estate terlebih dahulu",
    options: filterOptions.value.afdeling,
    disabled: !filterInputs.estate,
  },
  {
    key: "blok",
    label: "Blok",
    placeholder: "Pilih Afdeling terlebih dahulu",
    options: filterOptions.value.blok,
    disabled: !filterInputs.afdeling,
  },
]);

onMounted(async () => {
  await mapStore.loadGeoJSONData();
  await initTemaDataOptions();
});

function getSelectedLabelByKey(key: FilterKey): string {
  const value = filters.value[key] || "";
  if (!value) return "";
  const option = filterOptions.value[key].find((item) => item.value === value);
  return option?.label ?? value;
}

const blockProfileRows = computed(() => [
  { label: "Area", value: getSelectedLabelByKey("area") },
  { label: "Perusahaan (PT)", value: getSelectedLabelByKey("pt") },
  { label: "Estate", value: getSelectedLabelByKey("estate") },
  { label: "Afdeling", value: getSelectedLabelByKey("afdeling") },
  { label: "Blok", value: getSelectedLabelByKey("blok") },
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

function normalizeAutocompleteValue(key: FilterKey, rawValue: string) {
  const value = typeof rawValue === "string" ? rawValue : "";
  const trimmed = value.trim();
  if (!trimmed) return "";
  const options = getOptionsByKey(key);
  const exact = options.find(
    (option) => option.value.toLowerCase() === trimmed.toLowerCase(),
  );
  return exact?.value ?? "";
}

function applyAutocompleteNormalization(key: FilterKey) {
  const normalizedValue = normalizeAutocompleteValue(key, filterInputs[key]);
  filterInputs[key] = normalizedValue;
}

async function onFilterInputChange(key: FilterKey) {
  const beforeValue = filters.value[key] || "";
  applyAutocompleteNormalization(key);
  const nextValue = filterInputs[key] || "";

  if (nextValue === beforeValue) return;

  if (key === "area") {
    await mapStore.setSelectedArea(filterInputs.area);
    filterInputs.pt = "";
    filterInputs.estate = "";
    filterInputs.afdeling = "";
    filterInputs.blok = "";
    return;
  }

  if (key === "pt") {
    await mapStore.setSelectedPt(filterInputs.pt);
    filterInputs.estate = "";
    filterInputs.afdeling = "";
    filterInputs.blok = "";
    return;
  }

  if (key === "estate") {
    await mapStore.setSelectedEstate(filterInputs.estate);
    filterInputs.afdeling = "";
    filterInputs.blok = "";
    return;
  }

  if (key === "afdeling") {
    await mapStore.setSelectedAfdeling(filterInputs.afdeling);
    filterInputs.blok = "";
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

  await mapStore.applyFilters({
    area: filterInputs.area,
    pt: filterInputs.pt,
    estate: filterInputs.estate,
    afdeling: filterInputs.afdeling,
    blok: filterInputs.blok,
  });
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

    <div class="grid grid-cols-1 gap-4 p-4 lg:gap-5 lg:p-5" :class="isFilterCollapsed
      ? 'lg:grid-cols-[4%_46%_50%]'
      : 'lg:grid-cols-[260px_minmax(0,1fr)_360px]'">
      <aside class="rounded-2xl border border-[#E5EAF1] bg-white transition-all duration-300"
        :class="isFilterCollapsed ? 'overflow-hidden p-2' : 'p-4'">
        <div class="mb-2 flex items-center justify-between">
          <button type="button"
            class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#D8DEE8] bg-white text-[#334155] hover:bg-[#F8FAFC]"
            @click="toggleFilterCollapse" :title="isFilterCollapsed ? 'Expand Filter' : 'Collapse Filter'"
            :aria-label="isFilterCollapsed ? 'Expand Filter' : 'Collapse Filter'">
            <span v-if="isFilterCollapsed">▶</span>
            <span v-else>◀</span>
          </button>
          <p v-if="!isFilterCollapsed" class="text-[16px] font-bold text-[#1F2937]">
            Filter
          </p>
        </div>

        <template v-if="!isFilterCollapsed">
          <div class="mb-4 rounded-xl border border-[#E4E8EE] bg-[#FAFCFF] p-3">
            <p class="text-[16px] font-bold text-[#1F2937]">Area</p>
            <p class="text-[14px] text-[#6B7280]">Filter data spasial kebun</p>
          </div>

          <div class="space-y-3">
            <label v-for="field in filterConfigs" :key="field.key" class="block">
              <span class="mb-1.5 block text-[16px] font-bold text-[#2F3A4A]">{{
                field.label
              }}</span>
              <v-autocomplete class="custom-underlined-input" v-model="filterInputs[field.key]" :items="field.options"
                item-title="label" item-value="value" :placeholder="field.placeholder" variant="underlined"
                density="comfortable" bg-color="white" color="#2B7FFF" hide-details clearable
                menu-icon="mdi-chevron-down" :loading="loadingByField[field.key]"
                :disabled="field.disabled || loadingByField[field.key]"
                @update:model-value="onFilterInputChange(field.key)"
                @keydown.enter.prevent="onAutoCompleteEnter(field.key, $event)" />
            </label>

            <div class="mt-2 grid grid-cols-2 gap-2">
              <button
                class="inline-flex h-10 w-full items-center justify-center rounded-lg bg-[#2B7FFF] px-4 text-[14px] font-semibold text-white hover:bg-[#1E68DB] disabled:cursor-not-allowed disabled:bg-[#93B8F7]"
                type="button" :disabled="isLoading" @click="applyAllFilters">
                Apply
              </button>
              <button
                class="inline-flex h-10 w-full items-center justify-center rounded-lg border border-[#D8DEE8] bg-white px-4 text-[14px] font-semibold text-[#334155] hover:bg-[#F8FAFC] disabled:cursor-not-allowed"
                type="button" :disabled="isLoading" @click="resetAllFilters">
                Reset
              </button>
            </div>
          </div>
        </template>
      </aside>

      <section class="space-y-3">
        <div class="relative h-[72vh] min-h-[520px] overflow-hidden rounded-2xl border border-[#DCE3ED] bg-white">
          <div class="flex h-full items-center justify-center text-[#64748B]">
            <MapDashboard />
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
            Ringkasan Utama
          </h2>
          <div class="grid grid-cols-2 gap-2">
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">Total Blok</p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalBlok.toLocaleString("id-ID") }}
              </p>
            </div>
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">Total Luas</p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalLuasTanam.toFixed(2) }} ha
              </p>
            </div>
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">Total Pokok</p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalPokok.toLocaleString("id-ID") }}
              </p>
            </div>
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">Total Jalan</p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalJalan.toFixed(2) }}
              </p>
            </div>
          </div>
        </div>
        <div class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
          <h2 class="mb-3 text-[16px] font-bold text-[#1F2937]">
            Data Informasi
          </h2>
          <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-[14px] font-semibold text-[#2F3A4A]">Tema Data</span>
              <v-autocomplete class="custom-underlined-input" v-model="selectedTemaData" :items="temaDataOptions"
                item-title="label" item-value="value" placeholder="Pilih Tema Data" variant="underlined"
                density="comfortable" bg-color="white" color="#2B7FFF" hide-details clearable
                menu-icon="mdi-chevron-down" :loading="isTemaDataLoading" />
            </label>

            <label class="block">
              <span class="mb-1.5 block text-[14px] font-semibold text-[#2F3A4A]">Bulan</span>
              <v-autocomplete class="custom-underlined-input" v-model="selectedBulan" :items="bulanOptions"
                item-title="label" item-value="value" placeholder="Pilih Bulan" variant="underlined"
                density="comfortable" bg-color="white" color="#2B7FFF" hide-details clearable
                menu-icon="mdi-chevron-down" />
            </label>

            <label class="block">
              <span class="mb-1.5 block text-[14px] font-semibold text-[#2F3A4A]">Tahun</span>
              <v-autocomplete class="custom-underlined-input" v-model="selectedTahun" :items="tahunOptions"
                item-title="label" item-value="value" placeholder="Pilih Tahun" variant="underlined"
                density="comfortable" bg-color="white" color="#2B7FFF" hide-details clearable
                menu-icon="mdi-chevron-down" />
            </label>
          </div>
          <button
            class="inline-flex h-10 w-full mt-4 items-center justify-center rounded-lg bg-[#2B7FFF] px-4 text-[14px] font-semibold text-white hover:bg-[#1E68DB] disabled:cursor-not-allowed disabled:bg-[#93B8F7]"
            type="button" :disabled="isLoading" @click="">
            Search Data
          </button>
        </div>
      </aside>
    </div>
  </main>
</template>
<style scoped>
.custom-underlined-input :deep(.v-field__outline) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.267) !important;
  opacity: 1 !important;
}
</style>
