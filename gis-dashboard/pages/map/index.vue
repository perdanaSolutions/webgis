<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { useMapStore } from '~/stores/mapStore'

defineOptions({
  name: 'MapPage',
})

const mapStore = useMapStore()

const topTabs = ref([
  { key: 'scorecard', label: 'Scorecard' },
  { key: 'condition', label: 'Condition' },
  { key: 'crop-indices', label: 'Crop Indices' },
  { key: 'comparison', label: 'Comparison' },
  { key: 'yield-projection', label: 'Yield Projection' },
])

const activeTab = ref('scorecard')

const filterInputs = reactive({
  pt: '',
  estate: '',
  afdeling: '',
  blok: '',
  tahunTanam: '',
  statusTanam: '',
  jenisBibit: '',
})

const filterOptions = computed(() => mapStore.filterOptions)
const filters = computed(() => mapStore.filters)
const summary = computed(() => mapStore.summary)
const isLoading = computed(() => mapStore.isLoading)

const filterConfigs = computed(() => [
  { key: 'pt', label: 'Perusahaan (PT)', placeholder: 'Ketik atau pilih PT', options: filterOptions.value.pt },
  { key: 'estate', label: 'Estate', placeholder: 'Ketik atau pilih Estate', options: filterOptions.value.estate },
  { key: 'afdeling', label: 'Afdeling', placeholder: 'Ketik atau pilih Afdeling', options: filterOptions.value.afdeling },
  { key: 'blok', label: 'Blok', placeholder: 'Ketik atau pilih Blok', options: filterOptions.value.blok },
  { key: 'tahunTanam', label: 'Tahun Tanam', placeholder: 'Ketik atau pilih Tahun', options: filterOptions.value.tahunTanam },
  { key: 'statusTanam', label: 'Status Tanam', placeholder: 'Ketik atau pilih Status', options: filterOptions.value.statusTanam },
  { key: 'jenisBibit', label: 'Jenis Bibit', placeholder: 'Ketik atau pilih Bibit', options: filterOptions.value.jenisBibit },
] as const)

onMounted(async () => {
  await mapStore.loadGeoJSONData()
})

const blockProfileRows = computed(() => [
  { label: 'Perusahaan (PT)', value: filters.value.pt || 'Semua PT' },
  { label: 'Estate', value: filters.value.estate || 'Semua Estate' },
  { label: 'Afdeling', value: filters.value.afdeling || 'Semua Afdeling' },
  { label: 'Blok', value: filters.value.blok || 'Semua Blok' },
  { label: 'Tahun Tanam', value: filters.value.tahunTanam || 'Semua Tahun' },
  { label: 'Status Tanam', value: filters.value.statusTanam || 'Semua Status' },
  { label: 'Jenis Bibit', value: filters.value.jenisBibit || 'Semua Bibit' },
])

const slopeSummaryRows = computed(() => {
  const totalLuas = summary.value.totalLuasTanam
  const totalPokok = summary.value.totalPokok
  const totalJalan = summary.value.totalJalan
  const totalDrainase = summary.value.totalDrainase
  const totalJembatan = summary.value.totalJembatan

  return [
    {
      label: '0-3%',
      value: `${(totalLuas * 0.32).toFixed(2)} ha`,
      metric: `${Math.round(totalPokok * 0.32).toLocaleString('id-ID')} pokok`,
    },
    {
      label: '3-8%',
      value: `${(totalLuas * 0.28).toFixed(2)} ha`,
      metric: `${totalJalan.toFixed(2)} jalan`,
    },
    {
      label: '8-15%',
      value: `${(totalLuas * 0.22).toFixed(2)} ha`,
      metric: `${totalDrainase.toFixed(2)} drainase`,
    },
    {
      label: '15-25%',
      value: `${(totalLuas * 0.12).toFixed(2)} ha`,
      metric: `${totalJembatan.toLocaleString('id-ID')} jembatan`,
    },
    {
      label: '>25%',
      value: `${(totalLuas * 0.06).toFixed(2)} ha`,
      metric: 'Perlu pemantauan',
    },
  ]
})

const availableYears = computed(() => {
  return filterOptions.value.tahunTanam
    .map(option => Number(option.value))
    .filter(year => Number.isFinite(year))
    .sort((a, b) => a - b)
})

const historyRows = computed(() => {
  const years = availableYears.value
  const baseLuas = summary.value.totalLuasTanam
  const basePokok = summary.value.totalPokok

  if (!years.length) return []

  const minYear = years[0] as number
  const maxYear = years[years.length - 1] as number
  const span = Math.max(maxYear - minYear, 1)

  return years.map((year) => {
    const progress = (year - minYear) / span
    const luas = baseLuas * (0.78 + progress * 0.22)
    const pokok = basePokok * (0.72 + progress * 0.28)
    const tonPerHa = 8.5 + progress * 4.1
    const bjr = 12 + progress * 2.4

    return {
      year,
      luas,
      pokok,
      tonPerHa,
      bjr,
    }
  })
})

watch(
  filters,
  (currentFilters) => {
    filterInputs.pt = currentFilters.pt
    filterInputs.estate = currentFilters.estate
    filterInputs.afdeling = currentFilters.afdeling
    filterInputs.blok = currentFilters.blok
    filterInputs.tahunTanam = currentFilters.tahunTanam
    filterInputs.statusTanam = currentFilters.statusTanam
    filterInputs.jenisBibit = currentFilters.jenisBibit
  },
  { immediate: true, deep: true },
)

function getOptionsByKey(key: keyof typeof filterInputs) {
  return filterOptions.value[key]
}

function normalizeAutocompleteValue(key: keyof typeof filterInputs, rawValue: string) {
  const value = typeof rawValue === 'string' ? rawValue : ''
  const trimmed = value.trim()
  if (!trimmed) return ''
  const options = getOptionsByKey(key)
  const exact = options.find(option => option.value.toLowerCase() === trimmed.toLowerCase())
  return exact?.value ?? ''
}

function applyAutocompleteNormalization(key: keyof typeof filterInputs) {
  const normalizedValue = normalizeAutocompleteValue(key, filterInputs[key])
  filterInputs[key] = normalizedValue
}

function onAutoCompleteEnter(key: keyof typeof filterInputs, event: KeyboardEvent) {
  event.preventDefault()
  applyAutocompleteNormalization(key)
}

async function applyAllFilters() {
  ; (Object.keys(filterInputs) as Array<keyof typeof filterInputs>).forEach((key) => {
    applyAutocompleteNormalization(key)
  })

  await mapStore.applyFilters({
    pt: filterInputs.pt,
    estate: filterInputs.estate,
    afdeling: filterInputs.afdeling,
    blok: filterInputs.blok,
    tahunTanam: filterInputs.tahunTanam,
    statusTanam: filterInputs.statusTanam,
    jenisBibit: filterInputs.jenisBibit,
  })
}

async function resetAllFilters() {
  filterInputs.pt = ''
  filterInputs.estate = ''
  filterInputs.afdeling = ''
  filterInputs.blok = ''
  filterInputs.tahunTanam = ''
  filterInputs.statusTanam = ''
  filterInputs.jenisBibit = ''
  await mapStore.resetFilters()
}

async function gotoDashboard() {
  await navigateTo('/dashboard')
}
</script>

<template>
  <main class="min-h-screen bg-[#F7F8FA] text-[14px] text-[#2B2B2B]">
    <header class="sticky top-0 z-30 border-b border-[#E7EAF0] bg-white">
      <div class="flex items-center justify-between gap-4 px-4 py-3 lg:px-6">
        <div class="flex items-center gap-3">
          <button
            class="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#D8DEE8] text-[#566074]"
            type="button" aria-label="Back" @click="gotoDashboard">
            ‹
          </button>
          <div>
            <h1 class="text-[20px] font-bold text-[#1F2937]">
              Block Profile
            </h1>
            <p class="text-[14px] text-[#7B8190]">
              Dashboard / Block Profile
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <button class="flex h-9 w-9 items-center justify-center rounded-full bg-[#FFF1E9] text-[#65442F]"
            type="button">
            🔔
          </button>
          <div class="flex items-center gap-2 rounded-xl border border-[#E6EAF0] bg-[#FFF8F2] px-2 py-1.5">
            <div class="h-8 w-8 rounded-lg bg-[#D0B59A]" />
            <div class="leading-tight">
              <p class="text-[16px] font-bold text-[#1F2937]">
                Bruno Fernandes
              </p>
              <p class="text-[14px] text-[#6B7280]">
                Super Admin
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>

    <div class="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[260px_minmax(0,1fr)_360px] lg:gap-5 lg:p-5">
      <aside class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
        <div class="mb-4 rounded-xl border border-[#E4E8EE] bg-[#FAFCFF] p-3">
          <p class="text-[16px] font-bold text-[#1F2937]">
            Area
          </p>
          <p class="text-[14px] text-[#6B7280]">
            Filter data spasial kebun
          </p>
        </div>

        <div class="mb-3 rounded-lg border border-[#DBE4F1] bg-[#F7FAFF] px-3 py-2 text-[14px] text-[#2F3A4A]">
          <div class="flex items-center justify-between gap-2">
            <span class="font-semibold">Smart Filter</span>
            <span v-if="isLoading" class="inline-flex items-center gap-1.5 text-[14px] text-[#1E68DB]">
              <span class="h-3 w-3 animate-spin rounded-full border-2 border-[#1E68DB] border-t-transparent" />
              Memproses...
            </span>
          </div>
        </div>

        <div class="space-y-3">
          <label v-for="field in filterConfigs" :key="field.key" class="block">
            <span class="mb-1.5 block text-[16px] font-bold text-[#2F3A4A]">{{ field.label }}</span>
            <v-autocomplete v-model="filterInputs[field.key]" :items="field.options" item-title="label"
              item-value="value" :placeholder="field.placeholder" variant="underlined" density="comfortable"
              bg-color="white" color="#2B7FFF" hide-details clearable menu-icon="mdi-chevron-down"
              @blur="applyAutocompleteNormalization(field.key)"
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
      </aside>

      <section class="space-y-3">
        <div class="grid grid-cols-2 gap-2 xl:grid-cols-5">
          <button v-for="tab in topTabs" :key="tab.key" type="button"
            class="h-11 rounded-lg border text-[14px] font-semibold transition"
            :class="tab.key === activeTab ? 'border-[#2B7FFF] bg-[#ECF4FF] text-[#1D4ED8]' : 'border-[#D8DEE8] bg-white text-[#4B5563] hover:border-[#AEB8C8]'"
            @click="activeTab = tab.key">
            {{ tab.label }}
          </button>
        </div>

        <div class="relative h-[72vh] min-h-[520px] overflow-hidden rounded-2xl border border-[#DCE3ED] bg-white">
          <div v-if="isLoading"
            class="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center bg-white/75 backdrop-blur-sm">
            <div class="relative mb-4 h-16 w-16">
              <div class="absolute inset-0 animate-ping rounded-full bg-[#2B7FFF]/25" />
              <div class="absolute inset-0 animate-spin rounded-full border-4 border-[#2B7FFF] border-t-transparent" />
            </div>
            <p class="text-[16px] font-bold text-[#1E40AF]">
              Memproses data peta...
            </p>
            <p class="mt-1 text-[14px] text-[#475569]">
              Mohon tunggu, filter sedang diterapkan
            </p>
            <div class="mt-4 h-2 w-56 overflow-hidden rounded-full bg-[#DBEAFE]">
              <div class="h-full w-1/2 animate-[pulse_1s_ease-in-out_infinite] rounded-full bg-[#2B7FFF]" />
            </div>
          </div>

          <MapDashboard />
        </div>

        <div v-if="isLoading" class="grid grid-cols-3 gap-3 rounded-xl border border-[#E5EAF1] bg-white p-3">
          <div v-for="item in 3" :key="`skeleton-${item}`" class="h-12 animate-pulse rounded-lg bg-[#EEF2F8]" />
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
              <p class="text-[14px] text-[#6B7280]">
                {{ item.label }}
              </p>
              <p class="truncate text-[14px] font-semibold text-[#111827]">
                {{ item.value }}
              </p>
            </div>
          </div>
        </div>

        <div class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
          <h2 class="mb-3 text-[16px] font-bold text-[#1F2937]">
            Slope (Kemiringan Lereng)
          </h2>
          <div class="grid grid-cols-5 overflow-hidden rounded-lg border border-[#E5EAF1]">
            <div v-for="item in slopeSummaryRows" :key="item.label"
              class="border-r border-[#E5EAF1] p-2 text-center last:border-r-0">
              <p class="text-[14px] font-bold text-[#1F2937]">
                {{ item.label }}
              </p>
              <p class="mt-1 text-[14px] text-[#6B7280]">
                {{ item.value }}
              </p>
              <p class="mt-1 text-[14px] text-[#6B7280]">
                {{ item.metric }}
              </p>
            </div>
          </div>
        </div>

        <div class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
          <h2 class="mb-3 text-[16px] font-bold text-[#1F2937]">
            Data Historis
          </h2>
          <div class="overflow-auto rounded-lg border border-[#E5EAF1]">
            <table class="min-w-full border-collapse">
              <thead class="bg-[#F8FAFC]">
                <tr>
                  <th class="px-2 py-2 text-left text-[14px] font-bold text-[#334155]">
                    Tahun
                  </th>
                  <th class="px-2 py-2 text-left text-[14px] font-bold text-[#334155]">
                    Luas (ha)
                  </th>
                  <th class="px-2 py-2 text-left text-[14px] font-bold text-[#334155]">
                    Pokok
                  </th>
                  <th class="px-2 py-2 text-left text-[14px] font-bold text-[#334155]">
                    Ton/Ha
                  </th>
                  <th class="px-2 py-2 text-left text-[14px] font-bold text-[#334155]">
                    BJR
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in historyRows" :key="row.year" class="border-t border-[#EDF1F7]">
                  <td class="px-2 py-2 text-[14px] text-[#374151]">
                    {{ row.year }}
                  </td>
                  <td class="px-2 py-2 text-[14px] text-[#374151]">
                    {{ row.luas.toFixed(2) }}
                  </td>
                  <td class="px-2 py-2 text-[14px] text-[#374151]">
                    {{ Math.round(row.pokok).toLocaleString('id-ID') }}
                  </td>
                  <td class="px-2 py-2 text-[14px] text-[#374151]">
                    {{ row.tonPerHa.toFixed(2) }}
                  </td>
                  <td class="px-2 py-2 text-[14px] text-[#374151]">
                    {{ row.bjr.toFixed(2) }}
                  </td>
                </tr>
                <tr v-if="historyRows.length === 0">
                  <td colspan="5" class="px-2 py-3 text-center text-[14px] text-[#6B7280]">
                    Tidak ada data tahun tanam yang tersedia untuk ditampilkan.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="rounded-2xl border border-[#E5EAF1] bg-white p-4">
          <h2 class="mb-3 text-[16px] font-bold text-[#1F2937]">
            Ringkasan Utama
          </h2>
          <div class="grid grid-cols-2 gap-2">
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">
                Total Blok
              </p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalBlok.toLocaleString('id-ID') }}
              </p>
            </div>
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">
                Total Luas
              </p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalLuasTanam.toFixed(2) }} ha
              </p>
            </div>
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">
                Total Pokok
              </p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalPokok.toLocaleString('id-ID') }}
              </p>
            </div>
            <div class="rounded-lg bg-[#F8FAFC] p-2">
              <p class="text-[14px] text-[#6B7280]">
                Total Jalan
              </p>
              <p class="text-[16px] font-bold text-[#111827]">
                {{ summary.totalJalan.toFixed(2) }}
              </p>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <div v-if="isLoading"
      class="pointer-events-none fixed inset-0 z-40 flex items-end justify-center bg-[#0F172A]/20 p-6 lg:items-start lg:justify-end">
      <div class="w-full max-w-sm rounded-xl border border-[#CBD5E1] bg-white/95 p-4 shadow-2xl backdrop-blur">
        <div class="flex items-start gap-3">
          <div class="mt-0.5 h-9 w-9 shrink-0 rounded-full bg-[#DBEAFE] p-2 text-[#1D4ED8]">
            <div class="h-full w-full animate-spin rounded-full border-2 border-[#1D4ED8] border-t-transparent" />
          </div>
          <div>
            <p class="text-[16px] font-bold text-[#1E3A8A]">
              Sinkronisasi Filter Berjalan
            </p>
            <p class="mt-1 text-[14px] text-[#475569]">
              Sistem sedang memperbarui peta, ringkasan, dan tabel berdasarkan pilihan filter terbaru.
            </p>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
