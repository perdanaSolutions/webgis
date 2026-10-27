<script setup lang="ts">
import { computed, reactive, ref, watch, onMounted } from "vue";
import Header from "~/components/Header.vue";
import CreateThemeModal from "~/components/upload/CreateThemeModal.vue";
import UploadColumnFilter from "~/components/upload/ColumnFilter.vue";
import UploadAnalysisGroups from "~/components/upload/AnalysisGroups.vue";
import UploadTemplateDownload from "~/components/upload/TemplateDownload.vue";
import UploadFailedRowsDownload from "~/components/upload/FailedRowsDownload.vue";
import { countQuarantined } from "~/utils/failedRowsDownload";
import { GROUP_FILTER_DEFS, findGroupColumns } from "~/utils/uploadPreviewFilters";
import { useDocumentUploadStore } from "~/stores/documentUploadStore";

defineOptions({
  name: "DocumentUploadPage",
});

const documentUploadStore = useDocumentUploadStore();
const { hasPermission } = useAccessControl();
const canCreateTheme = computed(() => hasPermission("upload:geojson"));
const isOpenCreateTheme = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

const isBusy = computed(
  () => documentUploadStore.isParsing || documentUploadStore.isUploading,
);

const selectedCategoryDescription = computed(() => {
  const selected = documentUploadStore.categories.find(
    (item) => item.value === documentUploadStore.selectedCategory,
  );
  return selected?.description ?? "";
});

const previewHeaders = computed(() => {
  const firstFeature = documentUploadStore.allPreviewRows[0];
  if (!firstFeature) return [];
  return Object.keys(firstFeature.properties ?? {});
});

const currentPage = ref(1);
const itemsPerPage = 5;
const searchQuery = ref("");
const isOpenModalValidasi = ref(false);
const isThereReplaceData = ref(false);

const previewRows = computed(() =>
  documentUploadStore.allPreviewRows.map((feature, index) => ({
    feature,
    number: index + 1,
  })),
);

// ---- Kolom hasil analisa (ditempel per part lewat no_preview) & filter gaya Excel ----
const ANALYSIS_COLUMNS = [
  { key: "status_analisa", label: "Status Analisa" },
  { key: "kode_gagal", label: "Kode Gagal" },
  { key: "alasan_gagal", label: "Alasan Gagal" },
] as const;
const GEOMETRY_COLUMN = "__geometry__";

const hasAnalysisColumns = computed(() => Object.keys(documentUploadStore.previewAnalysis).length > 0);

/** Kolom pengelompokan (group/perusahaan/area/estate/afdeling/blok) yang ada di file. */
const groupColumns = computed(() => findGroupColumns(previewHeaders.value));

const columnFilters = reactive<Record<string, string[] | null>>({});

function cellValue(row: { feature: any; number: number }, column: string): string {
  if (column === GEOMETRY_COLUMN) return String(row.feature.geometry?.type ?? "");
  if (ANALYSIS_COLUMNS.some((c) => c.key === column)) {
    const analysisRow = documentUploadStore.previewAnalysis[row.number] as Record<string, unknown> | undefined;
    if (!analysisRow) return column === "status_analisa" ? "BELUM DIANALISA" : "";
    return String(analysisRow[column] ?? "");
  }
  const value = row.feature.properties?.[column];
  return value == null ? "" : String(value).trim();
}

function passesFilters(row: { feature: any; number: number }, except?: string): boolean {
  for (const [column, selected] of Object.entries(columnFilters)) {
    if (!selected || column === except) continue;
    if (!selected.includes(cellValue(row, column))) return false;
  }
  return true;
}

function filterOptions(column: string): Array<{ value: string; count: number }> {
  const counts = new Map<string, number>();
  for (const row of searchedPreviewRows.value) {
    if (!passesFilters(row, column)) continue;
    const value = cellValue(row, column);
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => a.value.localeCompare(b.value, "id", { numeric: true }));
}

function setColumnFilter(column: string, value: string[] | null) {
  columnFilters[column] = value;
}

const activeFilterCount = computed(() => Object.values(columnFilters).filter((v) => v !== null).length);

function clearAllFilters() {
  for (const key of Object.keys(columnFilters)) columnFilters[key] = null;
}

const analysisStatusCounts = computed(() => {
  const rows = Object.values(documentUploadStore.previewAnalysis);
  const gagal = rows.filter((r) => r.status_analisa === "GAGAL").length;
  return { total: rows.length, aman: rows.length - gagal, gagal };
});

const filteredPreviewRows = computed(() => searchedPreviewRows.value.filter((row) => passesFilters(row)));

const searchedPreviewRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return previewRows.value;

  return previewRows.value.filter(({ feature, number }) => {
    const geometryType = String(feature.geometry?.type ?? "").toLowerCase();
    const propertiesValues = Object.values(feature.properties ?? {})
      .map((value) => String(value ?? "").toLowerCase())
      .join(" ");
    const matchesNumber = /^\d+$/.test(query)
      ? String(number) === query
      : String(number).includes(query);

    return (
      matchesNumber ||
      geometryType.includes(query) ||
      propertiesValues.includes(query)
    );
  });
});

onMounted(async () => {
  await documentUploadStore.initDataKategori();
  await documentUploadStore.resumeActiveJob();
});

const QUEUE_WARNING_SECONDS = 60;
const activeJob = computed(() => documentUploadStore.activeJob);

const multipart = computed(() => documentUploadStore.multipart);

const jobTitle = computed(() => {
  const base =
    activeJob.value?.kind === "execute" || multipart.value?.kind === "execute"
      ? "Menyimpan data ke database"
      : "Menganalisa file GeoJSON";
  const part = multipart.value;
  if (part && part.partTotal > 1) {
    return `${base} (part ${part.partIndex}/${part.partTotal})`;
  }
  const job = activeJob.value;
  if (job?.part_total && job.part_total > 1 && job.part_index) {
    return `${base} (part ${job.part_index}/${job.part_total})`;
  }
  return base;
});

const jobStatusText = computed(() => {
  const job = activeJob.value;
  if (!job) {
    const part = multipart.value;
    if (part && part.partTotal > 1) {
      return `Menyiapkan part ${part.partIndex} dari ${part.partTotal} (max 1.000 Feature/part)`;
    }
    return "";
  }
  if (job.cancel_requested || documentUploadStore.multipartAbort) return "Membatalkan proses...";
  if (job.status === "queued") {
    return job.queue_ahead
      ? `Menunggu giliran (${job.queue_ahead} proses di depan)`
      : "Menunggu giliran diproses";
  }
  const message = job.message ?? "Memproses";
  if (job.total) {
    const current = (job.current ?? 0).toLocaleString("id-ID");
    return `${message} ${current} / ${job.total.toLocaleString("id-ID")}`;
  }
  return message;
});

const jobPercent = computed(() => {
  const job = activeJob.value;
  if (!job?.total) return null;
  return Math.min(100, Math.round(((job.current ?? 0) / job.total) * 100));
});

const jobElapsed = computed(() => {
  const seconds = activeJob.value?.elapsed_seconds ?? 0;
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} menit ${seconds % 60} detik` : `${seconds} detik`;
});

const jobQueuedTooLong = computed(
  () => activeJob.value?.status === "queued" && (activeJob.value.elapsed_seconds ?? 0) > QUEUE_WARNING_SECONDS,
);

function onCancelJob() {
  documentUploadStore.cancelJob();
}

const totalPreviewRows = computed(() => filteredPreviewRows.value.length);

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(totalPreviewRows.value / itemsPerPage));
});

const paginatedPreviewRows = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  return filteredPreviewRows.value.slice(start, end);
});

const startItem = computed(() => {
  if (totalPreviewRows.value === 0) return 0;
  return (currentPage.value - 1) * itemsPerPage + 1;
});

const endItem = computed(() => {
  if (totalPreviewRows.value === 0) return 0;
  return Math.min(currentPage.value * itemsPerPage, totalPreviewRows.value);
});

function goToPrevPage() {
  if (currentPage.value > 1) currentPage.value -= 1;
}

function goToNextPage() {
  if (currentPage.value < totalPages.value) currentPage.value += 1;
}

watch(
  () => documentUploadStore.allPreviewRows,
  () => {
    currentPage.value = 1;
  },
  { deep: true },
);

watch(searchQuery, () => {
  currentPage.value = 1;
});

watch(columnFilters, () => {
  currentPage.value = 1;
}, { deep: true });

// File baru -> filter lama tidak berlaku lagi.
watch(
  () => documentUploadStore.selectedFile,
  () => clearAllFilters(),
);

watch(totalPages, (newTotal) => {
  if (currentPage.value > newTotal) currentPage.value = newTotal;
});

function openFilePicker() {
  fileInputRef.value?.click();
}

async function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  await documentUploadStore.setFile(file);
}

async function onDrop(event: DragEvent) {
  event.preventDefault();
  const file = event.dataTransfer?.files?.[0] ?? null;
  await documentUploadStore.setFile(file);
}

function onDragOver(event: DragEvent) {
  event.preventDefault();
}

function onSelectCategory(value: string) {
  documentUploadStore.setCategory(value);
}

async function onSubmitUpload() {
  if (Object.keys(documentUploadStore.summaryAnalyze).length === 0) {
    actionSubmit();
  } else {
    isOpenModalValidasi.value = true;
    isThereReplaceData.value = replaceCount.value > 0;
  }
}

const actionSubmit = async () => {
  if (Object.keys(documentUploadStore.summaryAnalyze).length > 0) {
    isOpenModalValidasi.value = false;
    isThereReplaceData.value = false;
  }
  await documentUploadStore.submitUpload();
}

function onCancelPreview() {
  documentUploadStore.cancelPreview();
  currentPage.value = 1;
  searchQuery.value = "";
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
}

async function gotoDashboard() {
  await navigateTo("/dashboard");
}

// Hasil analyze: layer bawaan & sawit membungkusnya di `data`, batas blok & layer dinamis tidak.
const liveAnalysis = computed<Record<string, any>>(() => documentUploadStore.liveAnalyze ?? {});

const analysis = computed<Record<string, any>>(() => {
  const summary = documentUploadStore.summaryAnalyze;
  const rawData = summary.data ?? summary;
  // Jika 'data' masih berupa string JSON, parse dulu. Jika sudah objek, langsung return.
  return typeof rawData === 'string' ? JSON.parse(rawData) : rawData;
});

/** Excel data gagal analisa: data tabel preview (fitur asli) + kode/alasan per nomor data. */
function analyzeFailedExport() {
  return {
    rows: documentUploadStore.allPreviewRows,
    analysis: documentUploadStore.previewAnalysis,
    kategori: documentUploadStore.selectedCategory,
    filename: documentUploadStore.selectedFile?.name,
    periode: documentUploadStore.month && documentUploadStore.year
      ? `${String(documentUploadStore.month).padStart(2, "0")}-${documentUploadStore.year}` : undefined,
    columns: previewHeaders.value,
  };
}

const executeFailedCount = computed(() => countQuarantined(documentUploadStore.executeResponse));

const hasNoValidData = computed(() => analysis.value.status_analisis === "TIDAK_ADA_DATA_VALID");

// Jumlah data lama di periode itu yang akan diganti (nama field berbeda per jenis upload).
const replaceCount = computed(() =>
  Number(analysis.value.data_periode_ini_akan_diganti ?? analysis.value.data_akan_ditimpa_di_periode_ini ?? 0),
);

function humanizeLabel(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatScalarValue(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString("id-ID");
  if (typeof value === "boolean") return value ? "Ya" : "Tidak";
  if (value == null || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

type ExecuteDetailRow =
  | { key: string; label: string; kind: "scalar"; value: string }
  | { key: string; label: string; kind: "object"; entries: Array<{ key: string; label: string; value: string }> }
  | {
    key: string;
    label: string;
    kind: "table";
    columns: string[];
    rows: Record<string, unknown>[];
  }
  | { key: string; label: string; kind: "list"; items: string[] };

function buildExecuteDetail(value: unknown, key: string): ExecuteDetailRow {
  const label = humanizeLabel(key);

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return { key, label, kind: "scalar", value: "-" };
    }
    const objects = value.filter(isPlainObject);
    if (objects.length) {
      const columns = Array.from(new Set(objects.flatMap((row) => Object.keys(row))));
      return { key, label, kind: "table", columns, rows: objects };
    }
    return { key, label, kind: "list", items: value.map((item) => formatScalarValue(item)) };
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return { key, label, kind: "scalar", value: "-" };
    }
    return {
      key,
      label,
      kind: "object",
      entries: entries.map(([entryKey, entryValue]) => ({
        key: entryKey,
        label: humanizeLabel(entryKey),
        value: formatScalarValue(entryValue),
      })),
    };
  }

  return { key, label, kind: "scalar", value: formatScalarValue(value) };
}

const executeView = computed(() => {
  const response = documentUploadStore.executeResponse;
  if (!response) return null;

  const body = (response.data ?? response.detail ?? response) as Record<string, any>;
  const statusProses = String(body?.status_proses ?? "");
  const apiMessage = typeof response.message === "string" ? response.message.trim() : "";
  let message = apiMessage;
  if (!message) {
    if (statusProses === "SUCCESS") message = "Submit analisis berhasil diproses.";
    else if (statusProses === "PARTIAL_SUCCESS") message = "Submit analisis selesai. Sebagian data tidak tersimpan.";
    else if (statusProses === "FAILED") message = "Submit analisis gagal. Tidak ada data yang tersimpan.";
    else message = "Submit analisis selesai.";
  }

  const detailSource = body?.detail_status;
  const detail: ExecuteDetailRow[] =
    detailSource && typeof detailSource === "object" && !Array.isArray(detailSource)
      ? Object.entries(detailSource as Record<string, unknown>).map(([key, value]) =>
        buildExecuteDetail(value, key),
      )
      : [];

  const scalarDetail = detail.filter((row) => row.kind === "scalar");
  const complexDetail = detail.filter((row) => row.kind !== "scalar");

  const totalEntry = Object.entries(body ?? {}).find(
    ([key, value]) => key.startsWith("total_data") && typeof value === "number",
  );

  const tone = statusProses === "FAILED" ? "error" : statusProses === "PARTIAL_SUCCESS" ? "warning" : "success";
  const title = tone === "error"
    ? "Submit analisis gagal"
    : tone === "warning"
      ? "Submit analisis selesai sebagian"
      : "Submit analisis berhasil";
  return {
    tone,
    title,
    message,
    statusProses,
    total: totalEntry?.[1] ?? null,
    detail,
    scalarDetail,
    complexDetail,
  };
});

const executeFinished = computed(
  () => Boolean(documentUploadStore.executeResponse) || Boolean(documentUploadStore.executeError),
);

const EXECUTE_PAGE_SIZE = 5;
const executePages = reactive<Record<string, number>>({});

function executePageCount(total: number) {
  return Math.max(1, Math.ceil(total / EXECUTE_PAGE_SIZE));
}

function executeVisiblePage(key: string, total: number) {
  return Math.min(Math.max(1, executePages[key] ?? 1), executePageCount(total));
}

function executePaged<T>(key: string, items: T[]) {
  const page = executeVisiblePage(key, items.length);
  const start = (page - 1) * EXECUTE_PAGE_SIZE;
  return items.slice(start, start + EXECUTE_PAGE_SIZE);
}

function executeRange(key: string, total: number) {
  const page = executeVisiblePage(key, total);
  const pages = executePageCount(total);
  if (!total) return { start: 0, end: 0, page, pages, total };
  return {
    start: (page - 1) * EXECUTE_PAGE_SIZE + 1,
    end: Math.min(page * EXECUTE_PAGE_SIZE, total),
    page,
    pages,
    total,
  };
}

function goExecutePage(key: string, page: number, total: number) {
  executePages[key] = Math.min(Math.max(1, page), executePageCount(total));
}

watch(
  () => documentUploadStore.executeResponse,
  () => {
    for (const key of Object.keys(executePages)) delete executePages[key];
  },
);

</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Management Document" brand-subtitle="Upload & validasi data GeoJSON spasial" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Back" @click="gotoDashboard"
          class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-light bg-surface text-icon shadow-sm transition-all duration-200 hover-border-navy hover-bg-slate-light hover-text-navy hover:scale-105 active:scale-95">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
            stroke="currentColor" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
        <p class="font-semibold tracking-wide text-subtitle">Dashboard</p>
      </div>

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-6">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h2 class="text-20 font-bold">Upload File GeoJSON</h2>
            <UploadTemplateDownload />
          </div>
          <p class="text-muted">
            Pilih kategori spasial, upload file GeoJSON, lalu review preview data
            sebelum submit.
          </p>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div class="mb-4">
            <div class="mb-4">
              <label class="mb-1 block text-label font-medium">Kategori Data GeoJSON (Spasial) <span class="text-error">*</span></label>
              <v-select :model-value="documentUploadStore.selectedCategory" :items="documentUploadStore.categories"
                :loading="documentUploadStore.isLoadingCategories" item-title="label" item-value="value"
                placeholder="Pilih kategori" variant="plain" density="comfortable"
                class="w-full px-3 border border-default rounded-xl h-[50px]"
                @update:model-value="onSelectCategory"></v-select>
              <p v-if="selectedCategoryDescription" class="mt-2 text-size-sm text-muted">
                {{ selectedCategoryDescription }}
              </p>
              <button v-if="canCreateTheme" type="button" class="mt-2 text-size-sm font-semibold text-brand underline"
                @click="isOpenCreateTheme = true">
                + Buat tema baru
              </button>
            </div>
          </div>

          <div class="">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="mb-1 block text-label font-medium">Bulan <span class="text-error">*</span></label>
                <v-select v-model="documentUploadStore.month" :items="[
                  { title: 'Januari', value: '01' },
                  { title: 'Februari', value: '02' },
                  { title: 'Maret', value: '03' },
                  { title: 'April', value: '04' },
                  { title: 'Mei', value: '05' },
                  { title: 'Juni', value: '06' },
                  { title: 'Juli', value: '07' },
                  { title: 'Agustus', value: '08' },
                  { title: 'September', value: '09' },
                  { title: 'Oktober', value: '10' },
                  { title: 'November', value: '11' },
                  { title: 'Desember', value: '12' }
                ]" placeholder="Pilih bulan" variant="plain" density="comfortable"
                  class="w-full px-3 border border-default rounded-xl h-[50px]"></v-select>
              </div>

              <div>
                <label class="mb-1 block text-label font-medium">Tahun <span class="text-error">*</span></label>
                <v-select v-model="documentUploadStore.year" :items="documentUploadStore.getYearList()"
                  placeholder="Pilih tahun" variant="plain" density="comfortable"
                  class="w-full px-3 border border-default rounded-xl h-[50px]"></v-select>
              </div>
            </div>
            <!-- <p class="mb-2 font-semibold text-brand">Daftar kategori & ketentuan:</p>
            <ul class="space-y-1 text-size-sm text-label">
              <li v-for="category in documentUploadStore.categories" :key="category.value">
                • {{ category.label }} — {{ category.description }}
              </li>
            </ul> -->
          </div>
        </div>

        <div class="mt-5 rounded-2xl border border-dashed border-tan-hover bg-cream-light p-6 text-center"
          @drop="onDrop" @dragover="onDragOver">
          <input ref="fileInputRef" type="file" accept=".geojson,.json,application/geo+json,application/json"
            class="hidden" @change="onFileChange" />
          <p class="text-15 font-semibold text-brand">
            Drag & Drop file GeoJSON di sini <span class="text-error">*</span>
          </p>
          <p class="mt-1 text-size-sm text-muted">atau</p>
          <button type="button"
            class="mt-3 rounded-xl bg-brand px-5 py-2.5 font-semibold text-on-brand disabled:opacity-50"
            :disabled="isBusy" @click="openFilePicker">
            Pilih File
          </button>
          <p v-if="documentUploadStore.selectedFile" class="mt-3 text-size-sm text-label">
            File: <span class="font-semibold">{{ documentUploadStore.selectedFile.name }}</span>
          </p>
        </div>

        <div v-if="documentUploadStore.isParsing" class="mt-5 rounded-xl border border-default bg-surface p-4">
          <div class="mb-2 flex items-center justify-between text-size-sm">
            <span class="font-semibold text-brand">Memvalidasi file...</span>
            <span class="text-muted">{{ documentUploadStore.uploadProgress }}%</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-progress-bar">
            <div class="h-full rounded-full bg-gradient-to-r gradient-brand-alt transition-all duration-500 ease-out"
              :style="{ width: `${documentUploadStore.uploadProgress}%` }" />
          </div>
        </div>

        <div v-else-if="documentUploadStore.isUploading" class="mt-5 rounded-xl border border-default bg-surface p-4">
          <div class="mb-1 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <span class="font-semibold text-brand">{{ activeJob ? jobTitle : "Mengirim file ke server..." }}</span>
            <span v-if="activeJob" class="text-size-sm text-muted">Berjalan {{ jobElapsed }}</span>
          </div>
          <p class="mb-2 text-size-sm text-label">
            {{ activeJob ? jobStatusText : "Mengunggah file" }}
            <span v-if="jobPercent !== null" class="text-muted"> ({{ jobPercent }}%)</span>
          </p>
          <div class="h-2 overflow-hidden rounded-full bg-progress-bar">
            <div v-if="jobPercent !== null"
              class="h-full rounded-full bg-gradient-to-r gradient-brand-alt transition-all duration-500 ease-out"
              :style="{ width: `${jobPercent}%` }" />
            <div v-else class="h-full w-full animate-pulse rounded-full bg-gradient-to-r gradient-brand-alt" />
          </div>
          <p class="mt-3 text-size-sm text-muted">
            File besar dipecah otomatis per 1.000 Feature lalu dianalisis/disimpan beruntun. Data berjumlah
            ribuan bisa memakan waktu beberapa menit. Halaman ini boleh ditinggal saat satu part sedang
            diproses; bila Anda membatalkan di tengah jalan, part berikutnya tidak dikirim.
          </p>
          <p v-if="jobQueuedTooLong" class="mt-2 rounded-lg bg-warning-light px-3 py-2 text-size-sm text-warning">
            Proses belum diambil server. Bila tetap menunggu, hubungi admin: worker upload mungkin belum berjalan.
          </p>
          <div v-if="activeJob" class="mt-3 flex justify-end">
            <button type="button"
              class="rounded-xl border border-tan bg-cream px-4 py-2 text-size-sm font-semibold text-brand disabled:opacity-50"
              :disabled="activeJob.cancel_requested || documentUploadStore.isCancellingJob" @click="onCancelJob">
              {{ activeJob.cancel_requested || documentUploadStore.isCancellingJob ? "Membatalkan..." : "Batalkan" }}
            </button>
          </div>
        </div>

        <p v-if="documentUploadStore.errorMessage" class="mt-4 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ documentUploadStore.errorMessage }}
        </p>

        <p v-if="documentUploadStore.successMessage" class="mt-4 rounded-xl bg-success-light px-4 py-3 text-success">
          {{ documentUploadStore.successMessage }}
        </p>

        <section v-if="documentUploadStore.hasPreview"
          class="mt-6 rounded-2xl border border-default bg-cream-white p-4">
          <div class="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 class="text-18 font-bold text-brand">Preview Data GeoJSON</h3>
              <p class="text-size-sm text-muted">
                Menampilkan {{ startItem }} - {{ endItem }} dari
                {{ totalPreviewRows }} feature
                <span v-if="searchQuery.trim()">
                  (hasil pencarian dari total {{ documentUploadStore.featureCount }} feature)
                </span>.
              </p>
            </div>

            <div class="w-full md:w-[320px]">
              <input v-model="searchQuery" type="text" placeholder="Cari nomor, geometry, atau semua kolom..."
                class="w-full rounded-xl border border-tan bg-surface px-3 py-2 text-size-sm text-brand outline-none focus-border-accent-brown" />
            </div>
          </div>

          <!-- Filter cepat kolom pengelompokan (gaya Excel) -->
          <div v-if="groupColumns.length || hasAnalysisColumns"
            class="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-default bg-surface px-3 py-2">
            <span class="text-size-sm font-semibold text-brand">Filter:</span>
            <template v-for="group in groupColumns" :key="group.column">
              <span class="text-size-xs text-muted">{{ group.label }}</span>
              <UploadColumnFilter :label="group.column" :model-value="columnFilters[group.column] ?? null"
                :load-options="() => filterOptions(group.column)"
                @update:model-value="(v) => setColumnFilter(group.column, v)" />
            </template>
            <template v-if="hasAnalysisColumns">
              <span class="text-size-xs text-muted">Status Analisa</span>
              <UploadColumnFilter label="status_analisa" :model-value="columnFilters.status_analisa ?? null"
                :load-options="() => filterOptions('status_analisa')"
                @update:model-value="(v) => setColumnFilter('status_analisa', v)" />
              <span class="text-size-xs text-muted">Kode Gagal</span>
              <UploadColumnFilter label="kode_gagal" :model-value="columnFilters.kode_gagal ?? null"
                :load-options="() => filterOptions('kode_gagal')"
                @update:model-value="(v) => setColumnFilter('kode_gagal', v)" />
            </template>
            <button v-if="activeFilterCount" type="button" class="ml-auto text-size-xs font-semibold text-brand underline"
              @click="clearAllFilters">
              Hapus semua filter ({{ activeFilterCount }})
            </button>
          </div>

          <p v-if="hasAnalysisColumns" class="mb-2 text-size-sm text-muted">
            Hasil analisa: {{ analysisStatusCounts.total.toLocaleString("id-ID") }} dari
            {{ documentUploadStore.featureCount.toLocaleString("id-ID") }} data sudah dianalisa —
            <span class="font-semibold text-success">{{ analysisStatusCounts.aman.toLocaleString("id-ID") }} aman</span>,
            <span class="font-semibold text-error-dark">{{ analysisStatusCounts.gagal.toLocaleString("id-ID") }} gagal</span>.
          </p>

          <div class="overflow-x-auto rounded-xl border border-default">
            <table class="min-w-full bg-surface text-size-sm">
              <thead class="bg-surface-warm text-left text-brand">
                <tr>
                  <th class="px-3 py-2 font-bold">No</th>
                  <template v-if="hasAnalysisColumns">
                    <th v-for="col in ANALYSIS_COLUMNS" :key="col.key" class="whitespace-nowrap px-3 py-2 font-bold">
                      <div class="flex items-center gap-1">
                        {{ col.label }}
                        <UploadColumnFilter compact :label="col.label" :model-value="columnFilters[col.key] ?? null"
                          :load-options="() => filterOptions(col.key)"
                          @update:model-value="(v) => setColumnFilter(col.key, v)" />
                      </div>
                    </th>
                  </template>
                  <th class="px-3 py-2 font-bold">
                    <div class="flex items-center gap-1">
                      Geometry
                      <UploadColumnFilter compact label="Geometry" :model-value="columnFilters[GEOMETRY_COLUMN] ?? null"
                        :load-options="() => filterOptions(GEOMETRY_COLUMN)"
                        @update:model-value="(v) => setColumnFilter(GEOMETRY_COLUMN, v)" />
                    </div>
                  </th>
                  <th v-for="header in previewHeaders" :key="header" class="whitespace-nowrap px-3 py-2 font-bold">
                    <div class="flex items-center gap-1">
                      {{ header }}
                      <UploadColumnFilter compact :label="header" :model-value="columnFilters[header] ?? null"
                        :load-options="() => filterOptions(header)"
                        @update:model-value="(v) => setColumnFilter(header, v)" />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="paginatedPreviewRows.length === 0">
                  <td :colspan="previewHeaders.length + 2 + (hasAnalysisColumns ? ANALYSIS_COLUMNS.length : 0)"
                    class="px-3 py-3 text-muted">Tidak ada data yang cocok.</td>
                </tr>
                <tr v-for="row in paginatedPreviewRows" :key="row.number" class="border-t border-row"
                  :class="documentUploadStore.previewAnalysis[row.number]?.status_analisa === 'GAGAL' ? 'bg-error-light' : ''">
                  <td class="px-3 py-2">{{ row.number }}</td>
                  <template v-if="hasAnalysisColumns">
                    <td class="whitespace-nowrap px-3 py-2 font-semibold"
                      :class="documentUploadStore.previewAnalysis[row.number]?.status_analisa === 'GAGAL'
                        ? 'text-error-dark' : documentUploadStore.previewAnalysis[row.number] ? 'text-success' : 'text-muted'">
                      {{ documentUploadStore.previewAnalysis[row.number]?.status_analisa ?? "Menunggu" }}
                    </td>
                    <td class="whitespace-nowrap px-3 py-2">{{ documentUploadStore.previewAnalysis[row.number]?.kode_gagal ?? "-" }}</td>
                    <td class="min-w-[320px] max-w-[560px] whitespace-normal break-words px-3 py-2 align-top"
                      :title="documentUploadStore.previewAnalysis[row.number]?.alasan_gagal ?? undefined">
                      {{ documentUploadStore.previewAnalysis[row.number]?.alasan_gagal ?? "-" }}
                    </td>
                  </template>
                  <td class="px-3 py-2">{{ row.feature.geometry?.type ?? "-" }}</td>
                  <td v-for="header in previewHeaders" :key="`${row.number}-${header}`" class="px-3 py-2">
                    {{ row.feature.properties?.[header] ?? "-" }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p class="text-size-sm text-muted">
              Menampilkan {{ startItem }} - {{ endItem }} dari {{ totalPreviewRows }} data
            </p>

            <div class="flex items-center gap-2">
              <button type="button"
                class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                :disabled="currentPage === 1" @click="goToPrevPage">
                Sebelumnya
              </button>

              <span class="text-size-sm text-label">
                Halaman {{ currentPage }} / {{ totalPages }}
              </span>

              <button type="button"
                class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                :disabled="currentPage === totalPages" @click="goToNextPage">
                Berikutnya
              </button>
            </div>
          </div>

          <div v-if="Object.keys(documentUploadStore.summaryAnalyze).length === 0" class="mt-4 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              :disabled="isBusy" @click="onCancelPreview">
              Cancel
            </button>
            <button type="button" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="isBusy" @click="onSubmitUpload">
              {{ documentUploadStore.isUploading ? "Menganalisa..." : "Submit Analisa" }}
            </button>
          </div>
        </section>

        <!-- Hasil part yang sudah selesai, tampil langsung selama analisa masih berjalan -->
        <div v-if="Object.keys(documentUploadStore.summaryAnalyze).length === 0 && documentUploadStore.analyzeParts.length"
          class="mt-6 bg-surface rounded-2xl border border-default p-6 shadow-sm">
          <h3 class="mb-4 text-18 font-bold text-brand">
            Hasil Analisis Sementara ({{ documentUploadStore.analyzeParts.length }} dari
            {{ liveAnalysis.total_part ?? documentUploadStore.analyzeParts.length }} part)
          </h3>
          <div v-if="analysisStatusCounts.gagal > 0" class="mb-4 flex justify-end">
            <UploadFailedRowsDownload :export-input="analyzeFailedExport" :count="analysisStatusCounts.gagal"
              label="Download Data Gagal sementara (.xlsx)" />
          </div>
          <UploadAnalysisGroups :analysis="liveAnalysis" :parts="documentUploadStore.analyzeParts" />
        </div>

        <div v-if="Object.keys(documentUploadStore.summaryAnalyze).length > 0" class="mt-6 space-y-6">

          <div class="bg-surface rounded-2xl border border-default p-6 shadow-sm">
            <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <h3 class="text-18 font-bold text-brand">Rincian Analisa Aman &amp; Analisa Gagal</h3>
              <UploadFailedRowsDownload :export-input="analyzeFailedExport" :count="analysisStatusCounts.gagal" />
            </div>
            <UploadAnalysisGroups :analysis="analysis" :parts="documentUploadStore.analyzeParts" />
          </div>

          <div v-if="!executeFinished" class="mt-4 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              :disabled="isBusy" @click="onCancelPreview">
              Cancel
            </button>
            <button type="button" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="isBusy || hasNoValidData" @click="onSubmitUpload">
              {{ documentUploadStore.isUploading ? "Menyimpan..." : "Submit Analisis" }}
            </button>
          </div>

          <div v-if="executeView" class="rounded-2xl border p-4"
            :class="executeView.tone === 'error' ? 'border-error bg-error-light' : executeView.tone === 'warning' ? 'border-default bg-warning-light' : 'border-default bg-success-light'">
            <p class="font-bold"
              :class="executeView.tone === 'error' ? 'text-error-dark' : executeView.tone === 'warning' ? 'text-warning' : 'text-success'">
              {{ executeView.title }}
            </p>
            <p class="mt-1 text-size-sm text-label">{{ executeView.message }}</p>
            <div v-if="executeFailedCount > 0" class="mt-3 flex justify-end">
              <UploadFailedRowsDownload :job-id="documentUploadStore.failedRowsJobId.execute"
                :count="executeFailedCount" label="Download Data Gagal Disimpan (.xlsx)" />
            </div>
            <p v-if="executeView.statusProses" class="mt-2 text-size-sm text-label">
              Status proses: <span class="font-semibold">{{ executeView.statusProses }}</span>
              <span v-if="executeView.total != null"> · {{ Number(executeView.total).toLocaleString('id-ID') }} data
                diproses</span>
            </p>
            <div v-if="executeView.scalarDetail.length" class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              <div v-for="row in executeView.scalarDetail" :key="row.key"
                class="flex items-center justify-between gap-3 rounded-xl border border-default-60 bg-surface px-3 py-2">
                <span class="text-size-sm text-label">{{ row.label }}</span>
                <span class="text-size-sm font-bold text-content-brown">{{ row.value }}</span>
              </div>
            </div>

            <div v-if="executeView.complexDetail.length" class="mt-3 space-y-3">
              <div v-for="row in executeView.complexDetail" :key="row.key"
                class="rounded-xl border border-default-60 bg-surface p-3">
                <p class="mb-2 text-size-sm font-semibold text-brand">{{ row.label }}</p>

                <div v-if="row.kind === 'table'">
                  <div class="overflow-x-auto rounded-lg border border-default">
                    <table class="min-w-full bg-surface text-size-sm">
                      <thead class="bg-surface-warm text-left text-brand">
                        <tr>
                          <th v-for="column in row.columns" :key="column" class="whitespace-nowrap px-3 py-2 font-bold">
                            {{ humanizeLabel(column) }}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-if="row.rows.length === 0">
                          <td :colspan="row.columns.length" class="px-3 py-3 text-muted">Tidak ada data.</td>
                        </tr>
                        <tr v-for="(tableRow, index) in executePaged(row.key, row.rows)"
                          :key="`${row.key}-${executeRange(row.key, row.rows.length).start + index}`"
                          class="border-t border-row">
                          <td v-for="column in row.columns" :key="`${row.key}-${index}-${column}`"
                            class="px-3 py-2 align-top">
                            {{ formatScalarValue(tableRow[column]) }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p class="text-size-sm text-muted">
                      Menampilkan {{ executeRange(row.key, row.rows.length).start }} -
                      {{ executeRange(row.key, row.rows.length).end }} dari
                      {{ row.rows.length.toLocaleString("id-ID") }} data
                    </p>
                    <div class="flex items-center gap-2">
                      <button type="button"
                        class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                        :disabled="executeRange(row.key, row.rows.length).page === 1"
                        @click="goExecutePage(row.key, executeRange(row.key, row.rows.length).page - 1, row.rows.length)">
                        Sebelumnya
                      </button>
                      <span class="text-size-sm text-label">
                        Halaman {{ executeRange(row.key, row.rows.length).page }} /
                        {{ executeRange(row.key, row.rows.length).pages }}
                      </span>
                      <button type="button"
                        class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                        :disabled="executeRange(row.key, row.rows.length).page === executeRange(row.key, row.rows.length).pages"
                        @click="goExecutePage(row.key, executeRange(row.key, row.rows.length).page + 1, row.rows.length)">
                        Berikutnya
                      </button>
                    </div>
                  </div>
                </div>

                <div v-else-if="row.kind === 'object'" class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div v-for="entry in row.entries" :key="`${row.key}-${entry.key}`"
                    class="flex items-center justify-between gap-3 rounded-lg border border-default-60 bg-surface-neutral px-3 py-2">
                    <span class="text-size-sm text-label">{{ entry.label }}</span>
                    <span class="text-size-sm font-bold text-content-brown">{{ entry.value }}</span>
                  </div>
                </div>

                <div v-else-if="row.kind === 'list'">
                  <div class="flex flex-wrap gap-2">
                    <span v-for="item in executePaged(`${row.key}-list`, row.items)" :key="`${row.key}-${item}`"
                      class="rounded-lg border border-default bg-surface-neutral px-2 py-1 text-size-xs text-label">
                      {{ item }}
                    </span>
                  </div>
                  <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p class="text-size-sm text-muted">
                      Menampilkan {{ executeRange(`${row.key}-list`, row.items.length).start }} -
                      {{ executeRange(`${row.key}-list`, row.items.length).end }} dari
                      {{ row.items.length.toLocaleString("id-ID") }} data
                    </p>
                    <div class="flex items-center gap-2">
                      <button type="button"
                        class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                        :disabled="executeRange(`${row.key}-list`, row.items.length).page === 1"
                        @click="goExecutePage(`${row.key}-list`, executeRange(`${row.key}-list`, row.items.length).page - 1, row.items.length)">
                        Sebelumnya
                      </button>
                      <span class="text-size-sm text-label">
                        Halaman {{ executeRange(`${row.key}-list`, row.items.length).page }} /
                        {{ executeRange(`${row.key}-list`, row.items.length).pages }}
                      </span>
                      <button type="button"
                        class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                        :disabled="executeRange(`${row.key}-list`, row.items.length).page === executeRange(`${row.key}-list`, row.items.length).pages"
                        @click="goExecutePage(`${row.key}-list`, executeRange(`${row.key}-list`, row.items.length).page + 1, row.items.length)">
                        Berikutnya
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="documentUploadStore.executeError"
            class="rounded-2xl border border-error bg-error-light px-4 py-3 text-error">
            {{ documentUploadStore.executeError }}
          </div>

          <div v-if="executeFinished" class="flex justify-end">
            <button type="button"
              class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand disabled:opacity-50"
              :disabled="isBusy" @click="onCancelPreview">
              Hapus Analisa File
            </button>
          </div>

          <!-- Cadangan untuk respons tanpa daftar peringatan -->
          <div v-if="!analysis.peringatan && analysis.data_tidak_valid > 0"
            class="p-4 bg-error-light border border-error rounded-xl text-size-sm text-error-dark flex gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2"
              stroke="currentColor" class="w-5 h-5 flex-shrink-0">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
            <span>Perhatian: Terdapat {{ analysis.data_tidak_valid }} data tidak valid yang
              terdeteksi.</span>
          </div>
        </div>

      </section>
    </div>
  </main>

  <CreateThemeModal v-if="isOpenCreateTheme" @close="isOpenCreateTheme = false" />

  <AppModalTeleport>
  <div v-if="isOpenModalValidasi" class="app-modal-backdrop bg-overlay-dark">
    <div class="app-modal-panel app-modal-size-sm w-full rounded-xl bg-surface shadow-2xl">
      <div class="flex items-center space-x-3 text-warning">
        <div class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-warning-light">
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h3 class="text-size-lg font-semibold text-gray-title-alt">
          Konfirmasi Analisis
        </h3>
      </div>

      <div class="mt-3 space-y-2 pl-13">
        <p v-if="analysis.kesimpulan" class="text-size-sm text-gray-body">{{ analysis.kesimpulan }}</p>
        <p v-if="isThereReplaceData" class="text-size-sm text-gray-body">
          Apakah Anda yakin untuk submit analisis ini? {{ replaceCount.toLocaleString("id-ID") }} data lama
          periode ini akan diganti dengan data dari file.
        </p>
        <p v-else class="text-size-sm text-gray-body">
          Apakah Anda yakin untuk submit analisis ini?
        </p>
      </div>

      <div class="mt-4 flex w-full justify-end space-x-3">
        <button type="button" @click="isOpenModalValidasi = false"
          class="rounded-lg border border-gray bg-surface px-4 py-2 text-size-sm font-medium text-gray-label-alt hover-bg-gray-light focus:outline-none focus:ring-2 focus-ring-gray focus:ring-offset-1 transition">
          Cancel
        </button>
        <button type="button" @click="actionSubmit"
          class="rounded-lg bg-blue-dark px-4 py-2 text-size-sm font-medium text-on-brand hover-bg-blue-darker focus:outline-none focus:ring-2 focus-ring-blue focus:ring-offset-1 transition shadow-sm">
          Submit
        </button>
      </div>
    </div>
  </div>
  </AppModalTeleport>

</template>
