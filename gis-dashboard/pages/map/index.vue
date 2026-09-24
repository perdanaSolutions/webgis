<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import Header from "~/components/Header.vue";

import { useAuthStore } from "~/stores/authStore";
import { dashboardStore } from "~/stores/dashboardStore";
import { useMapStore } from "~/stores/mapStore";

const { $api } = useNuxtApp();
const authStore = useAuthStore();
const dashboardService = dashboardStore();
const route = useRoute();

defineOptions({
  name: "MapPage",
});

const mapStore = useMapStore();

const activeModule = computed(() => {
  const path = route.path;
  return (
    dashboardService.flatModuleItems.find((item) => {
      if (!item.to) return false;
      return path === item.to || path.startsWith(`${item.to}/`);
    }) ?? null
  );
});

const headerBrandTitle = computed(
  () => activeModule.value?.title || dashboardService.dashboardConfig.brandTitle,
);

const headerBrandSubtitle = computed(
  () =>
    activeModule.value?.description ||
    dashboardService.dashboardConfig.brandSubtitle,
);

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

const FILTER_PARENT: Partial<Record<FilterKey, FilterKey>> = {
  pt: "area",
  estate: "pt",
  afdeling: "estate",
  blok: "afdeling",
};

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
const selectedOwnership = ref("");

const ownershipOptions = [
  { label: "Inti", value: "inti" },
  { label: "Plasma", value: "plasma" },
];

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
  return Array.from({ length: 6 }, (_, index) => {
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
    const response = await $api<Array<{ table: string; label: string }>>(
      `${baseUrl}/v1/spatial/history/tables`,
      {
        method: "GET",
        headers: getAuthHeaders(),
      },
    );

    const normalizedData = Array.isArray(response)
      ? response
      : ((response as any)?.data ?? []);

    temaDataOptions.value = normalizedData
      .map((item: { table?: string; label?: string }) => {
        const value = item?.table || "";
        const label = item?.label || value;
        return value ? { label, value } : null;
      })
      .filter(Boolean) as Array<{ label: string; value: string }>;

    if (!selectedTemaData.value && temaDataOptions.value.length > 0) {
      selectedTemaData.value = temaDataOptions.value[0]?.value || "";
    }
  } catch {
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
  if (!HIERARCHICAL_FILTER_KEYS.includes(key)) {
    return options;
  }

  if (options.length === 0) {
    return [ALL_FILTER_OPTION];
  }

  if (options.length <= 1) {
    return options;
  }

  return [ALL_FILTER_OPTION, ...options];
}

function isParentSpecific(key: FilterKey): boolean {
  const parentKey = FILTER_PARENT[key];
  if (!parentKey) return true;
  return !!filterInputs[parentKey]?.trim();
}

function getHierarchicalOptions(
  key: FilterKey,
  options: Array<{ label: string; value: string }>,
) {
  if (!HIERARCHICAL_FILTER_KEYS.includes(key)) {
    return options;
  }

  if (!isParentSpecific(key)) {
    return [ALL_FILTER_OPTION];
  }

  return withAllOption(key, options);
}

function isFilterDisabled(key: FilterKey): boolean {
  if (key === "area") return false;
  if (!filterInputs.area) return true;
  if (key === "pt" || key === "estate") return false;
  if (key === "afdeling") return !filterInputs.estate;
  if (key === "blok") return !filterInputs.afdeling;
  return false;
}

function canSelectSpecificValue(key: FilterKey, value: string): boolean {
  if (!value) return true;
  return isParentSpecific(key);
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
    options: getHierarchicalOptions("pt", filterOptions.value.pt),
    disabled: isFilterDisabled("pt"),
    clearable: false,
  },
  {
    key: "estate",
    label: "Estate",
    placeholder: "All",
    options: getHierarchicalOptions("estate", filterOptions.value.estate),
    disabled: isFilterDisabled("estate"),
    clearable: false,
  },
  {
    key: "afdeling",
    label: "Afdeling",
    placeholder: "All",
    options: getHierarchicalOptions("afdeling", filterOptions.value.afdeling),
    disabled: isFilterDisabled("afdeling"),
    clearable: false,
  },
  {
    key: "blok",
    label: "Blok",
    placeholder: "All",
    options: getHierarchicalOptions("blok", filterOptions.value.blok),
    disabled: isFilterDisabled("blok"),
    clearable: false,
  },
]);

onMounted(async () => {
  if (!authStore.token) {
    await navigateTo("/login");
    return;
  }

  if (!dashboardService.moduleItems.length) {
    await dashboardService.initDataMenu();
  }

  await mapStore.loadGeoJSONData();
  await initTemaDataOptions();

  if (mapStore.filters.area) {
    await applyAllFilters();
  }
});

function getSelectedLabelByKey(key: FilterKey): string {
  const value = filters.value[key] || "";
  if (!value) {
    return HIERARCHICAL_FILTER_KEYS.includes(key) ? "All" : "";
  }

  const option = filterOptions.value[key].find((item) => item.value === value);
  return option?.label ?? value;
}

function formatDisplayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? String(value)
      : value.toLocaleString("id-ID", { maximumFractionDigits: 2 });
  }
  return String(value);
}

function getLatestHistoryRow(): Record<string, unknown> | null {
  const history = mapStore.historyData;
  if (!history) return null;

  if (Array.isArray(history.data_histori) && history.data_histori.length > 0) {
    return (history.data_histori[history.data_histori.length - 1] ??
      null) as Record<string, unknown> | null;
  }

  if (Array.isArray(history.data) && history.data.length > 0) {
    const last = history.data[history.data.length - 1];
    if (last && typeof last === "object" && !("groups" in last)) {
      return last as Record<string, unknown>;
    }
  }

  return null;
}

function getHistoryTable(): string {
  const history = mapStore.historyData;
  if (!history) return "";
  return String(history.table || history.meta?.table || "");
}

const isArealStatement = computed(() => {
  const history = mapStore.historyData;
  if (!history) return false;
  if (getHistoryTable() === "trx_areal_statement") return true;
  return !!history.grand_total;
});

const arealGrandTotal = computed(() => mapStore.historyData?.grand_total ?? null);

const blockProfileRows = computed(() => {
  const latest = getLatestHistoryRow();
  const grand = arealGrandTotal.value;

  return [
    { label: "Area", value: getSelectedLabelByKey("area") },
    { label: "Perusahaan (PT)", value: getSelectedLabelByKey("pt") },
    { label: "Estate", value: getSelectedLabelByKey("estate") },
    { label: "Afdeling", value: getSelectedLabelByKey("afdeling") },
    { label: "Blok", value: getSelectedLabelByKey("blok") },
    { label: "Bibit", value: "" },
    { label: "Tahun Tanam", value: selectedTahun.value || "" },
    {
      label: "Luas Kerangka",
      value: formatDisplayValue(grand?.luas_tanah ?? latest?.luas_tanah),
    },
    {
      label: "Luas Tertanam",
      value: formatDisplayValue(
        grand?.luas_tanam ?? latest?.luas_tanam ?? latest?.luas,
      ),
    },
    {
      label: "Pokok",
      value: formatDisplayValue(
        grand?.total_pokok ?? latest?.total_pokok ?? latest?.pokok,
      ),
    },
    {
      label: "SPH",
      value: formatDisplayValue(grand?.sph ?? latest?.sph),
    },
  ];
});

const historyInfoTitle = computed(
  () =>
    mapStore.historyData?.label ||
    mapStore.historyData?.meta?.label ||
    "Data Informasi",
);

const historyModeAkumulasi = computed(
  () =>
    mapStore.historyData?.mode_akumulasi ||
    mapStore.historyData?.meta?.mode_akumulasi ||
    "",
);

const slopeRows = computed(() => {
  const slope = mapStore.historyData?.slope_kemiringan_lereng;
  if (!slope || typeof slope !== "object") return [];

  return Object.entries(slope).map(([label, value]) => ({
    label,
    value: formatDisplayValue(value),
  }));
});

const AREAL_GROUP_KEY_LABELS: Record<string, string> = {
  status_tanam: "Status Tanam",
  bulan_tanam: "Bulan Tanam",
  tahun_tanam: "Tahun Tanam",
  jenis_bibit: "Bibit",
  jenis_topografi: "Topografi",
  jenis_tanah: "Jenis Tanah",
};

const AREAL_TOTAL_METRIC_KEYS = [
  { key: "luas_tanam", label: "Luas Tanam", unit: "Ha" },
  { key: "luas_tanah", label: "Luas Tanah", unit: "Ha" },
  { key: "total_pokok", label: "Total Pokok", unit: "" },
  { key: "sph", label: "SPH", unit: "" },
] as const;

const AREAL_TOPO_KEYS = [
  { key: "pct_tanah_datar", label: "Datar" },
  { key: "pct_berbukit", label: "Berbukit" },
  { key: "pct_gelombang", label: "Gelombang" },
  { key: "pct_curam", label: "Curam" },
] as const;

function getBulanLabel(bulan: unknown): string {
  if (bulan === null || bulan === undefined || bulan === "") return "";

  const asString = String(bulan).trim();
  const shortMonthMap: Record<string, string> = {
    Jan: "Januari",
    Feb: "Februari",
    Mar: "Maret",
    Apr: "April",
    May: "Mei",
    Jun: "Juni",
    Jul: "Juli",
    Aug: "Agustus",
    Sep: "September",
    Oct: "Oktober",
    Nov: "November",
    Dec: "Desember",
  };
  if (shortMonthMap[asString]) return shortMonthMap[asString];

  const match = bulanOptions.find(
    (item) => item.value === String(Number(bulan)),
  );
  return match?.label || `Bulan ${bulan}`;
}

function getPeriodTitle(row: Record<string, unknown>): string {
  const bulanLabel = getBulanLabel(row.bulan);
  const tahun = formatDisplayValue(row.tahun);

  if (bulanLabel && tahun) return `${bulanLabel} ${tahun}`;
  if (bulanLabel) return bulanLabel;
  if (tahun) return `Tahun ${tahun}`;
  if (row.periode != null) return `Periode ${formatDisplayValue(row.periode)}`;
  return "Periode";
}

function buildMetricItems(row: Record<string, unknown>) {
  if ("luas" in row || "ton" in row || "ton_ha" in row) {
    return [
      { label: "Luas", value: formatDisplayValue(row.luas) },
      { label: "Ton", value: formatDisplayValue(row.ton) },
      { label: "Ton/Ha", value: formatDisplayValue(row.ton_ha) },
      { label: "BJR", value: formatDisplayValue(row.bjr) },
      { label: "Jjg/Pkk", value: formatDisplayValue(row.jjg_ppk) },
      { label: "Kg/Pkk", value: formatDisplayValue(row.kg_ppk) },
    ].filter((item) => item.value !== "");
  }

  const excludedKeys = new Set(["tahun", "bulan", "periode", "groups"]);
  return Object.entries(row)
    .filter(
      ([key, value]) =>
        !excludedKeys.has(key) && value != null && value !== "",
    )
    .map(([key, value]) => ({
      label: key
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase()),
      value: formatDisplayValue(value),
    }));
}

function buildArealMetricItems(totals: Record<string, unknown> | null | undefined) {
  if (!totals) return [];
  return AREAL_TOTAL_METRIC_KEYS.map((item) => ({
    label: item.label,
    unit: item.unit,
    value: formatDisplayValue(totals[item.key]),
  })).filter((item) => item.value !== "");
}

function buildArealTopoItems(totals: Record<string, unknown> | null | undefined) {
  if (!totals) return [];
  return AREAL_TOPO_KEYS.map((item) => {
    const raw = totals[item.key];
    const numeric =
      typeof raw === "number" ? raw : Number(raw ?? Number.NaN);
    return {
      label: item.label,
      value: formatDisplayValue(raw),
      percent: Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : 0,
    };
  }).filter((item) => item.value !== "");
}

function buildArealGroupTags(groupKeys: Record<string, unknown> | null | undefined) {
  if (!groupKeys) return [];
  return Object.entries(groupKeys)
    .filter(([, value]) => value != null && value !== "")
    .map(([key, value]) => ({
      key,
      label: AREAL_GROUP_KEY_LABELS[key] || key.replace(/_/g, " "),
      value:
        key === "bulan_tanam"
          ? getBulanLabel(value) || formatDisplayValue(value)
          : formatDisplayValue(value),
    }));
}

const arealGrandTotalMetrics = computed(() =>
  buildArealMetricItems(arealGrandTotal.value as Record<string, unknown> | null),
);

const arealGrandTotalTopo = computed(() =>
  buildArealTopoItems(arealGrandTotal.value as Record<string, unknown> | null),
);

const arealStatementPeriods = computed(() => {
  const history = mapStore.historyData;
  if (!history || !isArealStatement.value || !Array.isArray(history.data)) {
    return [];
  }

  return history.data.map((row, index) => {
    const item = row as Record<string, unknown>;
    const groups = Array.isArray(item.groups) ? item.groups : [];
    const title = getPeriodTitle(item);
    const yearHint = formatDisplayValue(item.tahun) || selectedTahun.value;

    return {
      id: `areal-${item.bulan ?? index}-${yearHint}`,
      title: yearHint && !String(title).includes(yearHint)
        ? `${title} ${yearHint}`
        : title,
      groupCount: groups.length,
      groups: groups.map((group, groupIndex) => {
        const g = (group || {}) as {
          group_keys?: Record<string, unknown>;
          totals?: Record<string, unknown>;
        };
        return {
          id: `${item.bulan ?? index}-${groupIndex}`,
          tags: buildArealGroupTags(g.group_keys),
          metrics: buildArealMetricItems(g.totals),
          topo: buildArealTopoItems(g.totals),
          countRecords: formatDisplayValue(g.totals?.count_records),
        };
      }),
    };
  });
});

const expandedArealPeriodId = ref<string | null>(null);

watch(
  arealStatementPeriods,
  (periods) => {
    if (!periods.length) {
      expandedArealPeriodId.value = null;
      return;
    }
    const stillExists = periods.some(
      (period) => period.id === expandedArealPeriodId.value,
    );
    if (!stillExists) {
      expandedArealPeriodId.value = periods[0]?.id ?? null;
    }
  },
  { immediate: true },
);

function toggleArealPeriod(periodId: string) {
  expandedArealPeriodId.value =
    expandedArealPeriodId.value === periodId ? null : periodId;
}

const dataInformasiPeriods = computed(() => {
  const history = mapStore.historyData;
  if (!history || isArealStatement.value) return [];

  const rows: Array<Record<string, unknown>> = Array.isArray(
    history.data_histori,
  )
    ? (history.data_histori as Array<Record<string, unknown>>)
    : Array.isArray(history.data)
      ? (history.data as Array<Record<string, unknown>>)
      : [];

  return rows.map((row, index) => ({
    id: `${row.tahun ?? "y"}-${row.bulan ?? row.periode ?? index}`,
    title: getPeriodTitle(row),
    metrics: buildMetricItems(row),
  }));
});

const hasDataInformasiContent = computed(() => {
  if (isArealStatement.value) {
    return (
      arealGrandTotalMetrics.value.length > 0 ||
      arealStatementPeriods.value.length > 0
    );
  }
  return slopeRows.value.length > 0 || dataInformasiPeriods.value.length > 0;
});

const isLoadingHistory = computed(() => mapStore.loadingHistory);

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

  if (nextValue && !canSelectSpecificValue(key, nextValue)) {
    filterInputs[key] = "";
    return;
  }

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
  (Object.keys(filterInputs) as FilterKey[]).forEach((key) => {
    applyAutocompleteNormalization(key);
  });

  if (!filterInputs.pt) {
    filterInputs.estate = "";
    filterInputs.afdeling = "";
    filterInputs.blok = "";
  } else if (!filterInputs.estate) {
    filterInputs.afdeling = "";
    filterInputs.blok = "";
  } else if (!filterInputs.afdeling) {
    filterInputs.blok = "";
  }

  try {
    const table =
      selectedTemaData.value || temaDataOptions.value[0]?.value || "";

    await mapStore.applyFilters(
      {
        area: filterInputs.area,
        pt: filterInputs.pt,
        estate: filterInputs.estate,
        afdeling: filterInputs.afdeling,
        blok: filterInputs.blok,
        ownership: selectedOwnership.value,
      },
      selectedTahun.value,
      table,
    );
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
  selectedOwnership.value = "";
  await mapStore.resetFilters();
}

async function gotoDashboard() {
  await navigateTo("/dashboard");
}
</script>

<template>
  <main class="min-h-screen bg-page-map text-14 text-dark">
    <Header :brand-title="headerBrandTitle" :brand-subtitle="headerBrandSubtitle" />

    <aside class="mx-4 mt-3 rounded-xl border border-map-light bg-surface transition-all duration-300"
      :class="isFilterCollapsed ? 'overflow-hidden p-2' : 'p-3'">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex min-w-0 items-center gap-2">
          <button type="button"
            class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-slate-light bg-surface text-13 text-slate hover-bg-hover-slate"
            :title="isFilterCollapsed ? 'Expand Filter' : 'Collapse Filter'"
            :aria-label="isFilterCollapsed ? 'Expand Filter' : 'Collapse Filter'" @click="toggleFilterCollapse">
            <span v-if="isFilterCollapsed">▶</span>
            <span v-else>◀</span>
          </button>
          <div class="min-w-0">
            <p class="truncate text-14 font-bold text-gray-title">
              Filter Data Spasial Blok
            </p>
            <p v-if="!isFilterCollapsed" class="text-12 text-gray-muted">
              Area kebun dan informasi blok
            </p>
          </div>
        </div>
      </div>

      <template v-if="!isFilterCollapsed">
        <div class="mt-3 space-y-3">
          <section>
            <p class="mb-2 text-11 font-semibold uppercase tracking-wide text-gray-muted">
              Area
            </p>
            <div class="grid grid-cols-1 gap-x-3 gap-y-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              <label v-for="field in filterConfigs" :key="field.key" class="min-w-0">
                <span class="mb-1 block text-13 font-medium text-gray-label">
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

          <section class="border-t border-section py-3">
            <p class="mb-2 text-11 font-semibold uppercase tracking-wide text-gray-muted">
              Informasi
            </p>
            <div class="grid grid-cols-1 items-end gap-x-3 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
              <label class="min-w-0">
                <span class="mb-1 block text-13 font-medium text-gray-label">
                  Tema Data
                </span>
                <v-autocomplete v-model="selectedTemaData" class="custom-underlined-input" :items="temaDataOptions"
                  item-title="label" item-value="value" placeholder="Pilih Tema Data" variant="underlined"
                  density="compact" bg-color="white" color="#2B7FFF" hide-details clearable menu-icon="mdi-chevron-down"
                  :loading="isTemaDataLoading" />
              </label>
              <label class="min-w-0">
                <span class="mb-1 block text-13 font-medium text-gray-label">
                  Ownership
                </span>
                <v-autocomplete v-model="selectedOwnership" class="custom-underlined-input"
                  :items="ownershipOptions" item-title="label" item-value="value"
                  placeholder="Pilih Ownership" variant="underlined" density="compact" bg-color="white"
                  color="#2B7FFF" hide-details clearable menu-icon="mdi-chevron-down" />
              </label>
              <label class="min-w-0">
                <span class="mb-1 block text-13 font-medium text-gray-label">
                  Tahun
                </span>
                <v-autocomplete v-model="selectedTahun" class="custom-underlined-input" :items="tahunOptions"
                  item-title="label" item-value="value" placeholder="Pilih Tahun" variant="underlined" density="compact"
                  bg-color="white" color="#2B7FFF" hide-details clearable menu-icon="mdi-chevron-down" />
              </label>
              <div class="flex items-center justify-stretch gap-2 sm:col-span-2 sm:justify-end lg:col-span-1">
                <button
                  class="inline-flex h-8 flex-1 items-center justify-center rounded-md border border-slate-light bg-surface px-3 text-13 font-semibold text-slate hover-bg-hover-slate disabled:cursor-not-allowed sm:flex-none"
                  type="button" :disabled="isLoading" @click="resetAllFilters">
                  Reset
                </button>
                <button
                  class="inline-flex h-8 flex-1 items-center justify-center rounded-md bg-blue-primary px-3 text-13 font-semibold text-on-brand hover-bg-blue-primary-hover disabled:cursor-not-allowed disabled:bg-blue-disabled sm:flex-none"
                  type="button" :disabled="isLoading" @click="applyAllFilters">
                  {{ isLoadingGeoJSON ? 'Memuat...' : 'Apply' }}
                </button>
              </div>
            </div>
          </section>
        </div>
      </template>
    </aside>

    <div class="space-y-4 p-4 lg:space-y-5 lg:p-5">
      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5">
        <section>
          <div
            class="relative h-[65vh] sm:h-[70vh] lg:h-[72vh] min-h-[400px] sm:min-h-[520px] w-full overflow-hidden rounded-2xl border border-map bg-surface shadow-sm transition-all duration-300">
            <div class="absolute inset-0 h-full w-full">
              <MapDashboard class="h-full w-full object-cover" />
            </div>
          </div>
        </section>

        <aside>
          <div class="rounded-2xl border border-map-light bg-surface p-4">
            <h2 class="mb-3 text-16 font-bold text-gray-title">
              Blok Profile
            </h2>
            <div class="space-y-1.5">
              <div v-for="item in blockProfileRows" :key="item.label"
                class="grid grid-cols-[120px_minmax(0,1fr)] items-start gap-2 rounded-md px-2 py-1.5 odd-bg-hover-slate">
                <p class="text-14 text-gray-muted">{{ item.label }}</p>
                <p class="truncate text-14 font-semibold text-gray-darker">
                  {{ item.value || "-" }}
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>

      <section class="rounded-2xl border border-map-light bg-surface p-4">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-16 font-bold text-gray-title">
            {{ historyInfoTitle }}
          </h2>
          <span v-if="historyModeAkumulasi"
            class="shrink-0 text-11 font-semibold uppercase tracking-wide text-gray-muted">
            {{ historyModeAkumulasi }}
          </span>
        </div>

        <p v-if="isLoadingHistory" class="text-14 text-gray-muted">
          Memuat data informasi...
        </p>

        <template v-else-if="isArealStatement && hasDataInformasiContent">
          <div v-if="arealGrandTotalMetrics.length" class="mb-4">
            <p class="mb-2 text-11 font-semibold uppercase tracking-wide text-gray-muted">
              Grand Total
            </p>
            <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div v-for="metric in arealGrandTotalMetrics" :key="`gt-${metric.label}`"
                class="rounded-lg border border-map-light bg-[#f8fafc] px-2.5 py-2">
                <p class="text-11 text-gray-muted">{{ metric.label }}</p>
                <p class="mt-0.5 text-14 font-bold text-gray-darker">
                  {{ metric.value }}
                  <span v-if="metric.unit" class="text-11 font-medium text-gray-muted">
                    {{ metric.unit }}
                  </span>
                </p>
              </div>
            </div>

            <div v-if="arealGrandTotalTopo.length" class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <div v-for="topo in arealGrandTotalTopo" :key="`gt-topo-${topo.label}`" class="space-y-1">
                <div class="flex items-center justify-between gap-2 text-12">
                  <span class="text-gray-muted">{{ topo.label }}</span>
                  <span class="font-semibold text-gray-darker">{{ topo.value }}%</span>
                </div>
                <div class="h-1.5 overflow-hidden rounded-full bg-[#e8eef5]">
                  <div class="h-full rounded-full bg-blue-primary transition-all duration-300"
                    :style="{ width: `${topo.percent}%` }" />
                </div>
              </div>
            </div>
          </div>

          <div v-if="arealStatementPeriods.length" class="space-y-2">
            <p class="text-11 font-semibold uppercase tracking-wide text-gray-muted">
              Rincian per Bulan
            </p>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div v-for="period in arealStatementPeriods" :key="period.id"
                class="overflow-hidden rounded-xl border border-map-light">
                <button type="button"
                  class="flex w-full items-center justify-between gap-2 bg-[#f8fafc] px-3 py-2.5 text-left hover-bg-hover-slate"
                  @click="toggleArealPeriod(period.id)">
                  <div class="min-w-0">
                    <p class="truncate text-13 font-bold text-gray-title">
                      {{ period.title }}
                    </p>
                    <p class="text-11 text-gray-muted">
                      {{ period.groupCount }} kelompok
                    </p>
                  </div>
                  <span class="shrink-0 text-12 text-gray-muted">
                    {{ expandedArealPeriodId === period.id ? "▴" : "▾" }}
                  </span>
                </button>

                <div v-if="expandedArealPeriodId === period.id" class="space-y-2 border-t border-map-light p-2.5">
                  <div v-for="group in period.groups" :key="group.id"
                    class="rounded-lg border border-map-light bg-surface p-2.5">
                    <div class="mb-2 flex flex-wrap items-center gap-1.5">
                      <span v-for="tag in group.tags" :key="`${group.id}-${tag.key}`"
                        class="inline-flex max-w-full items-center gap-1 rounded-md border border-slate-light bg-[#f8fafc] px-1.5 py-0.5 text-11 text-gray-darker">
                        <span class="text-gray-muted">{{ tag.label }}</span>
                        <span class="truncate font-semibold">{{ tag.value }}</span>
                      </span>
                      <span v-if="group.countRecords"
                        class="ml-auto text-11 font-medium text-gray-muted">
                        {{ group.countRecords }} rekaman
                      </span>
                    </div>

                    <div class="grid grid-cols-2 gap-2">
                      <div v-for="metric in group.metrics" :key="`${group.id}-${metric.label}`">
                        <p class="text-11 text-gray-muted">{{ metric.label }}</p>
                        <p class="text-13 font-semibold text-gray-darker">
                          {{ metric.value || "-" }}
                          <span v-if="metric.unit" class="text-11 font-medium text-gray-muted">
                            {{ metric.unit }}
                          </span>
                        </p>
                      </div>
                    </div>

                    <div v-if="group.topo.length" class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
                      <div v-for="topo in group.topo" :key="`${group.id}-topo-${topo.label}`"
                        class="flex items-baseline justify-between gap-1 text-11">
                        <span class="text-gray-muted">{{ topo.label }}</span>
                        <span class="font-semibold text-gray-darker">{{ topo.value }}%</span>
                      </div>
                    </div>
                  </div>

                  <p v-if="!period.groups.length" class="px-1 py-2 text-13 text-gray-muted">
                    Tidak ada kelompok data
                  </p>
                </div>
              </div>
            </div>
          </div>
        </template>

        <template v-else-if="hasDataInformasiContent">
          <div v-if="slopeRows.length" class="mb-4 space-y-1.5">
            <p class="mb-1 text-11 font-semibold uppercase tracking-wide text-gray-muted">
              Kemiringan Lereng
            </p>
            <div v-for="item in slopeRows" :key="`slope-${item.label}`"
              class="grid grid-cols-[120px_minmax(0,1fr)] items-start gap-2 rounded-md px-2 py-1.5 odd-bg-hover-slate">
              <p class="text-14 text-gray-muted">{{ item.label }}</p>
              <p class="truncate text-14 font-semibold text-gray-darker">
                {{ item.value || "-" }}
              </p>
            </div>
          </div>

          <div v-if="dataInformasiPeriods.length" class="data-info-table">
            <div v-for="period in dataInformasiPeriods" :key="period.id" class="data-info-cell">
              <p class="mb-2 text-13 font-bold text-gray-title">
                {{ period.title }}
              </p>
              <div class="space-y-1">
                <div v-for="metric in period.metrics" :key="`${period.id}-${metric.label}`"
                  class="flex items-baseline justify-between gap-2 text-13">
                  <span class="text-gray-muted">{{ metric.label }}</span>
                  <span class="font-semibold text-gray-darker">
                    {{ metric.value || "-" }}
                  </span>
                </div>
                <p v-if="!period.metrics.length" class="text-13 text-gray-muted">
                  Tidak ada data
                </p>
              </div>
            </div>
          </div>
        </template>

        <p v-else class="text-14 text-gray-muted">
          Belum ada data
        </p>
      </section>
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

.data-info-table {
  display: grid;
  grid-template-columns: 1fr;
  border-top: 1px solid #d7dee8;
  border-left: 1px solid #d7dee8;
  border-radius: 0.75rem;
  overflow: hidden;
}

.data-info-cell {
  padding: 0.75rem;
  border-right: 1px solid #d7dee8;
  border-bottom: 1px solid #d7dee8;
  background: #fff;
}

@media (min-width: 640px) {
  .data-info-table {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1024px) {
  .data-info-table {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
