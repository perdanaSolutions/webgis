<script setup lang="ts">
import { computed, ref, watch } from "vue";
import Header from "~/components/Header.vue";
import UploadAnalysisResult from "~/components/upload/AnalysisResult.vue";
import { useTrxUploadStore } from "~/stores/trxUploadStore";
import { TRX_KINDS, missingHeaderGroups } from "~/utils/trxUpload";

defineOptions({
  name: "TrxUploadPage",
});

const trxUploadStore = useTrxUploadStore();
const fileInputRef = ref<HTMLInputElement | null>(null);
const isOpenConfirm = ref(false);
const searchQuery = ref("");
const currentPage = ref(1);
const itemsPerPage = 8;

const kind = computed(() => trxUploadStore.kind);
const busyLabel = computed(() => {
  if (trxUploadStore.isReading) return "Membaca file...";
  if (trxUploadStore.isAnalyzing) return "Menganalisis, data belum disimpan...";
  return "Mengimpor data...";
});
const analysis = computed(() => trxUploadStore.analysis);
const hasNoValidData = computed(() => analysis.value?.status_analisis === "TIDAK_ADA_DATA_VALID");
const previewRows = computed(() => trxUploadStore.previewRows);

const missingHeaders = computed(() => {
  const spec = kind.value;
  if (!trxUploadStore.fileMode || !trxUploadStore.headers.length || !spec) return [];
  return missingHeaderGroups(trxUploadStore.headers, spec);
});

const filteredRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  return previewRows.value
    .map((row, index) => ({
      row,
      excelRow: trxUploadStore.fileMode === "json" ? index + 1 : index + 2,
    }))
    .filter(({ row, excelRow }) => {
      if (!query) return true;
      if (String(excelRow).includes(query)) return true;
      return Object.values(row).some((value) => value.toLowerCase().includes(query));
    });
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / itemsPerPage)));
const pageRows = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage;
  return filteredRows.value.slice(start, start + itemsPerPage);
});
const startItem = computed(() => (filteredRows.value.length ? (currentPage.value - 1) * itemsPerPage + 1 : 0));
const endItem = computed(() => Math.min(currentPage.value * itemsPerPage, filteredRows.value.length));

watch(previewRows, () => {
  currentPage.value = 1;
  searchQuery.value = "";
});

watch(searchQuery, () => {
  currentPage.value = 1;
});

watch(totalPages, (total) => {
  if (currentPage.value > total) currentPage.value = total;
});

const importDetails = computed<Record<string, unknown>>(() => {
  const details = trxUploadStore.importResult?.details;
  return details && typeof details === "object" ? details as Record<string, unknown> : {};
});

const PRIMARY_FIELDS: Array<{ key: string; label: string }> = [
  { key: "success_count", label: "Baris masuk" },
  { key: "data_baru", label: "Data baru" },
  { key: "data_diperbarui", label: "Data diperbarui" },
  { key: "data_tidak_berubah", label: "Data tidak berubah" },
  { key: "missing_blok_count", label: "Blok tidak ditemukan" },
  { key: "invalid_prop_count", label: "Nilai tidak valid" },
  { key: "karantina_count", label: "Masuk karantina" },
  { key: "duplicate_in_file", label: "Baris ganda digabung" },
];

const primaryStats = computed(() =>
  PRIMARY_FIELDS
    .filter((field) => typeof importDetails.value[field.key] === "number")
    .map((field) => ({ ...field, value: Number(importDetails.value[field.key]) })),
);

function humanize(key: string) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatScalar(value: unknown) {
  if (value == null || value === "") return "-";
  if (typeof value === "number") return value.toLocaleString("id-ID");
  if (typeof value === "boolean") return value ? "Ya" : "Tidak";
  return String(value);
}

type ImportExtraDetail =
  | { key: string; label: string; kind: "scalar"; value: string }
  | { key: string; label: string; kind: "list"; items: string[] }
  | { key: string; label: string; kind: "object"; entries: { key: string; label: string; value: string }[] };

const extraDetails = computed((): ImportExtraDetail[] => {
  const hidden = new Set([
    ...PRIMARY_FIELDS.map((field) => field.key),
    "batch_id",
    "failed_error_count",
    "last_error_msg",
    "parameter",
    "mode",
    "data_lama_ditemukan",
    "data_lama_dihapus",
  ]);
  return Object.entries(importDetails.value).flatMap(([key, value]): ImportExtraDetail[] => {
    if (hidden.has(key) || value == null || value === "") return [];
    if (Array.isArray(value)) {
      if (!value.length) return [];
      return [{ key, label: humanize(key), kind: "list" as const, items: value.map((item) => formatScalar(item)) }];
    }
    if (typeof value === "object") {
      const entries = Object.entries(value as Record<string, unknown>).filter(([, entry]) => entry != null && entry !== "");
      if (!entries.length) return [];
      return [{
        key,
        label: humanize(key),
        kind: "object" as const,
        entries: entries.map(([entryKey, entryValue]) => ({
          key: entryKey,
          label: humanize(entryKey),
          value: Array.isArray(entryValue)
            ? entryValue.map((item) => formatScalar(item)).join(", ") || "-"
            : formatScalar(entryValue),
        })),
      }];
    }
    return [{ key, label: humanize(key), kind: "scalar" as const, value: formatScalar(value) }];
  });
});

function openFilePicker() {
  fileInputRef.value?.click();
}

async function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  await trxUploadStore.setFile(target.files?.[0] ?? null);
  target.value = "";
}

async function onDrop(event: DragEvent) {
  event.preventDefault();
  await trxUploadStore.setFile(event.dataTransfer?.files?.[0] ?? null);
}

function clearFile() {
  trxUploadStore.resetFile();
  isOpenConfirm.value = false;
  if (fileInputRef.value) fileInputRef.value.value = "";
}

async function onAnalyze() {
  await trxUploadStore.analyze();
}

function askImport() {
  isOpenConfirm.value = true;
}

async function confirmImport() {
  isOpenConfirm.value = false;
  await trxUploadStore.importFile();
}

function selectKind(kindId: typeof TRX_KINDS[number]["id"]) {
  trxUploadStore.setKind(kindId);
}

async function gotoDashboard() {
  await navigateTo("/dashboard");
}
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Upload Transaksi" brand-subtitle="Areal statement dan rotasi pusingan" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Kembali ke dashboard" @click="gotoDashboard"
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
          <h2 class="text-20 font-bold">Upload Data Transaksi</h2>
          <p class="text-muted">
            Pilih jenis data, unduh template, lalu unggah Excel. Analisis dijalankan dulu tanpa menyimpan data.
            Import memakai file yang sama setelah hasilnya sesuai.
          </p>
        </div>

        <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
          <button v-for="item in TRX_KINDS" :key="item.id" type="button"
            class="rounded-2xl border p-4 text-left transition"
            :class="trxUploadStore.kindId === item.id ? 'border-brand bg-cream-light' : 'border-default bg-surface'"
            :disabled="trxUploadStore.isBusy" @click="selectKind(item.id)">
            <p class="font-bold text-brand">{{ item.label }}</p>
            <p class="mt-1 text-size-sm text-muted">{{ item.description }}</p>
          </button>
        </div>

        <div class="mt-5 rounded-2xl border border-default bg-cream-white p-4">
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <h3 class="font-bold text-brand">{{ kind.label }}</h3>
              <p class="mt-1 text-size-sm text-muted">{{ kind.description }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <button type="button"
                class="rounded-xl border border-tan bg-surface px-4 py-2 text-size-sm font-semibold text-brand"
                :disabled="trxUploadStore.isBusy" @click="trxUploadStore.downloadExcel()">
                Unduh template Excel
              </button>
              <button type="button"
                class="rounded-xl border border-tan bg-surface px-4 py-2 text-size-sm font-semibold text-brand"
                :disabled="trxUploadStore.isBusy" @click="trxUploadStore.downloadJson()">
                Unduh contoh JSON
              </button>
            </div>
          </div>

          <p class="mt-3 text-size-sm text-label">
            Template Excel punya sheet <span class="font-semibold">Data</span> (yang diimpor),
            <span class="font-semibold">Contoh</span>, dan <span class="font-semibold">Petunjuk</span>.
            Isi data di sheet Data. Kolom:
            <span class="font-semibold">{{ kind.columns.join(", ") }}</span>.
          </p>

          <details class="mt-3 rounded-xl border border-default bg-surface">
            <summary class="cursor-pointer select-none px-4 py-3 text-size-sm font-semibold text-brand">
              Aturan import
            </summary>
            <ul class="list-disc space-y-2 border-t border-default px-8 py-3 text-size-sm text-label">
              <li v-for="rule in kind.rules" :key="rule">{{ rule }}</li>
            </ul>
          </details>
        </div>

        <div class="mt-5 rounded-2xl border border-dashed border-tan-hover bg-cream-light p-6 text-center"
          @drop="onDrop" @dragover.prevent>
          <input ref="fileInputRef" type="file" accept=".xlsx,.xls,.json,application/vnd.ms-excel,application/json"
            class="hidden" @change="onFileChange" />
          <p class="text-15 font-semibold text-brand">Drag & drop file Excel atau JSON di sini</p>
          <p class="mt-1 text-size-sm text-muted">.xlsx, .xls, atau .json · maksimal 50 MB</p>
          <button type="button"
            class="mt-3 rounded-xl bg-brand px-5 py-2.5 font-semibold text-on-brand disabled:opacity-50"
            :disabled="trxUploadStore.isBusy" @click="openFilePicker">
            Pilih File
          </button>
          <p v-if="trxUploadStore.selectedFile" class="mt-3 text-size-sm text-label">
            File: <span class="font-semibold">{{ trxUploadStore.selectedFile.name }}</span>
            <span v-if="trxUploadStore.fileMode === 'excel'"> · Excel<span v-if="trxUploadStore.sheetName"> / {{
              trxUploadStore.sheetName }}</span></span>
            <span v-else-if="trxUploadStore.fileMode === 'json'"> · JSON</span>
          </p>
        </div>

        <div v-if="trxUploadStore.isReading || trxUploadStore.isAnalyzing || trxUploadStore.isImporting"
          class="mt-5 rounded-xl border border-default bg-surface p-4">
          <p class="mb-2 font-semibold text-brand">{{ busyLabel }}</p>
          <div class="h-2 overflow-hidden rounded-full bg-progress-bar">
            <div class="h-full w-full animate-pulse rounded-full bg-gradient-to-r gradient-brand-alt" />
          </div>
        </div>

        <p v-if="trxUploadStore.errorMessage" class="mt-4 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ trxUploadStore.errorMessage }}
        </p>

        <section v-if="trxUploadStore.fileMode" class="mt-6 rounded-2xl border border-default bg-cream-white p-4">
          <div class="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 class="text-18 font-bold text-brand">Pratinjau data</h3>
              <p class="text-size-sm text-muted">
                {{ trxUploadStore.rowCount.toLocaleString("id-ID") }} baris
                <span v-if="trxUploadStore.fileMode === 'excel'">pada sheet pertama. Nomor baris sama dengan baris
                  Excel.</span>
                <span v-else>. Import JSON langsung disimpan; endpoint ini tidak punya uji coba.</span>
              </p>
            </div>
            <input v-model="searchQuery" type="text" placeholder="Cari nomor baris atau isi kolom..."
              class="w-full rounded-xl border border-tan bg-surface px-3 py-2 text-size-sm text-brand outline-none focus-border-accent-brown md:w-[320px]" />
          </div>

          <p v-if="missingHeaders.length" class="mb-3 rounded-xl bg-warning-light px-4 py-3 text-size-sm text-warning">
            Header yang belum terlihat: {{missingHeaders.map((item) => item.label).join("; ")}}.
            <template v-if="trxUploadStore.fileMode === 'excel'">
              Analisis tetap bisa dijalankan; laporan server yang menentukan baris mana yang masuk.
            </template>
            <template v-else>
              Periksa nama kolom sebelum impor. JSON tidak punya uji coba, jadi data langsung disimpan.
            </template>
          </p>

          <p v-if="trxUploadStore.rowCount === 0" class="text-size-sm text-muted">
            Sheet pertama hanya berisi header. Isi baris data sebelum mengimpor.
          </p>

          <div v-else class="overflow-x-auto rounded-xl border border-default">
            <table class="min-w-full bg-surface text-size-sm">
              <thead class="bg-surface-warm text-left text-brand">
                <tr>
                  <th class="px-3 py-2 font-bold">Baris</th>
                  <th v-for="header in trxUploadStore.headers" :key="header"
                    class="whitespace-nowrap px-3 py-2 font-bold">
                    {{ header }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="pageRows.length === 0">
                  <td :colspan="trxUploadStore.headers.length + 1" class="px-3 py-3 text-muted">Tidak ada data yang
                    cocok.</td>
                </tr>
                <tr v-for="item in pageRows" :key="item.excelRow" class="border-t border-row">
                  <td class="px-3 py-2">{{ item.excelRow }}</td>
                  <td v-for="header in trxUploadStore.headers" :key="`${item.excelRow}-${header}`" class="px-3 py-2">
                    {{ item.row[header] || "-" }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="filteredRows.length"
            class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p class="text-size-sm text-muted">
              Menampilkan {{ startItem }} - {{ endItem }} dari {{ filteredRows.length.toLocaleString("id-ID") }} data
            </p>
            <div class="flex items-center gap-2">
              <button type="button"
                class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                :disabled="currentPage === 1" @click="currentPage -= 1">
                Sebelumnya
              </button>
              <span class="text-size-sm text-label">Halaman {{ currentPage }} / {{ totalPages }}</span>
              <button type="button"
                class="rounded-lg border border-tan bg-surface px-3 py-1.5 text-size-sm font-semibold text-brand disabled:opacity-50"
                :disabled="currentPage === totalPages" @click="currentPage += 1">
                Berikutnya
              </button>
            </div>
          </div>

          <div v-if="!analysis && !trxUploadStore.importResult" class="mt-4 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              :disabled="trxUploadStore.isBusy" @click="clearFile">
              Batal
            </button>
            <button v-if="trxUploadStore.fileMode === 'excel'" type="button"
              class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="trxUploadStore.isBusy" @click="onAnalyze">
              Analisis
            </button>
            <button v-else type="button"
              class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="trxUploadStore.isBusy || trxUploadStore.rowCount === 0" @click="askImport">
              Impor JSON
            </button>
          </div>
        </section>

        <div v-if="analysis" class="mt-6 space-y-4">
          <div class="rounded-2xl border border-default bg-surface p-6 shadow-sm">
            <h3 class="mb-1 text-18 font-bold text-brand">Hasil analisis</h3>
            <p class="mb-4 text-size-sm text-muted">
              Uji coba ini tidak menyimpan data. Angkanya sama dengan hasil import sungguhan.
            </p>
            <UploadAnalysisResult :analysis="analysis" />
          </div>

          <div v-if="!trxUploadStore.importResult" class="flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              :disabled="trxUploadStore.isBusy" @click="clearFile">
              Batal
            </button>
            <button type="button" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="trxUploadStore.isBusy || hasNoValidData" @click="askImport">
              Impor data
            </button>
          </div>
        </div>

        <div v-if="trxUploadStore.importResult" class="mt-6 rounded-2xl border border-default bg-success-light p-4">
          <p class="font-bold text-success">Import selesai</p>
          <p class="mt-1 text-size-sm text-label">
            {{ trxUploadStore.importResult.message || "Proses impor selesai." }}
            Baris yang ditolak tersimpan di karantina, dan blok yang tidak ada di file tidak dihapus.
          </p>
          <div v-if="primaryStats.length" class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <div v-for="stat in primaryStats" :key="stat.key"
              class="flex items-center justify-between gap-3 rounded-xl border border-default-60 bg-surface px-3 py-2">
              <span class="text-size-sm text-label">{{ stat.label }}</span>
              <span class="text-size-sm font-bold text-content-brown">{{ stat.value.toLocaleString("id-ID") }}</span>
            </div>
          </div>
          <div v-if="extraDetails.length" class="mt-3 space-y-3">
            <div v-for="detail in extraDetails" :key="detail.key"
              class="rounded-xl border border-default-60 bg-surface p-3">
              <p class="mb-2 text-size-sm font-semibold text-brand">{{ detail.label }}</p>
              <p v-if="detail.kind === 'scalar'" class="text-size-sm text-label">{{ detail.value }}</p>
              <div v-else-if="detail.kind === 'list'" class="flex flex-wrap gap-2">
                <span v-for="item in detail.items" :key="item"
                  class="rounded-lg border border-default bg-surface-neutral px-2 py-1 text-size-xs text-label">
                  {{ item }}
                </span>
              </div>
              <div v-else class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div v-for="entry in detail.entries" :key="entry.key"
                  class="flex items-center justify-between gap-3 rounded-lg border border-default-60 bg-surface-neutral px-3 py-2">
                  <span class="text-size-sm text-label">{{ entry.label }}</span>
                  <span class="text-size-sm font-bold text-content-brown">{{ entry.value }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="mt-4 flex flex-wrap justify-end gap-2">
            <NuxtLink to="/riwayat-upload"
              class="rounded-xl border border-tan bg-surface px-4 py-2 font-semibold text-brand">
              Lihat riwayat upload
            </NuxtLink>
            <button type="button" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand" @click="clearFile">
              Upload file lain
            </button>
          </div>
        </div>
      </section>
    </div>
  </main>

  <div v-if="isOpenConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay-dark p-4">
    <div class="w-full max-w-md rounded-xl bg-surface p-6 shadow-2xl">
      <h3 class="text-size-lg font-semibold text-gray-title-alt">Konfirmasi import</h3>
      <div class="mt-3 space-y-2 text-size-sm text-gray-body">
        <p v-if="analysis?.kesimpulan">{{ analysis.kesimpulan }}</p>
        <p v-if="trxUploadStore.fileMode === 'excel'">
          File yang sama akan diimpor. Baris valid ditambah atau diperbarui per blok dan bulan.
          Baris yang ditolak masuk karantina. Blok yang tidak ada di file tidak dihapus.
        </p>
        <p v-else>
          Import JSON tidak punya uji coba. Validasi dan upsert-nya sama dengan Excel, dan data langsung disimpan.
        </p>
        <p v-if="Number(analysis?.data_diperbarui) > 0">
          {{ Number(analysis?.data_diperbarui).toLocaleString("id-ID") }} baris akan memperbarui data yang sudah ada
          karena nilainya berbeda.
        </p>
      </div>
      <div class="mt-4 flex justify-end gap-2">
        <button type="button"
          class="rounded-lg border border-gray bg-surface px-4 py-2 text-size-sm font-medium text-gray-label-alt"
          @click="isOpenConfirm = false">
          Batal
        </button>
        <button type="button" class="rounded-lg bg-blue-dark px-4 py-2 text-size-sm font-medium text-on-brand"
          @click="confirmImport">
          Impor
        </button>
      </div>
    </div>
  </div>
</template>
