<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import Header from "~/components/Header.vue";
import {
  useUploadHistoryStore,
  type UploadHistoryItem,
  type UploadSourceType,
  type UploadStatus,
} from "~/stores/uploadHistoryStore";

defineOptions({
  name: "RiwayatUploadPage",
});

const STATUS_OPTIONS: { value: UploadStatus | ""; label: string }[] = [
  { value: "", label: "Semua status" },
  { value: "SUCCESS", label: "Berhasil" },
  { value: "PARTIAL_SUCCESS", label: "Berhasil Sebagian" },
  { value: "FAILED", label: "Gagal" },
  { value: "IN_PROGRESS", label: "Diproses" },
  { value: "ABANDONED", label: "Dibatalkan" },
];

const SOURCE_OPTIONS: { value: UploadSourceType | ""; label: string }[] = [
  { value: "", label: "Semua sumber" },
  { value: "GEOJSON_UPLOAD", label: "GeoJSON" },
  { value: "EXCEL_UPLOAD", label: "Excel" },
];

const uploadHistoryStore = useUploadHistoryStore();

const search = ref("");
const statusFilter = ref<UploadStatus | "">("");
const sourceFilter = ref<UploadSourceType | "">("");
const tanggalDari = ref("");
const tanggalSampai = ref("");
const showDetailModal = ref(false);
const detailError = ref("");
const selectedId = ref("");

const canGoPrev = computed(() => uploadHistoryStore.page > 1);
const canGoNext = computed(
  () => uploadHistoryStore.page < uploadHistoryStore.totalPage,
);

const detail = computed(() =>
  uploadHistoryStore.selectedItem?.id === selectedId.value
    ? uploadHistoryStore.selectedItem
    : null,
);

const detailMetadata = computed(() => {
  const metadata = detail.value?.metadata;
  if (!metadata || !Object.keys(metadata).length) return "";
  return JSON.stringify(metadata, null, 2);
});

function formatDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatPeriode(value?: string | null) {
  if (!value) return "-";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("id-ID", { month: "long", year: "numeric" });
}

function formatDurasi(detik?: number | null) {
  if (detik === null || detik === undefined) return "-";
  if (detik < 60) return `${detik.toFixed(1)} detik`;
  const menit = Math.floor(detik / 60);
  return `${menit} menit ${Math.round(detik % 60)} detik`;
}

function sourceLabel(value: string) {
  return SOURCE_OPTIONS.find((option) => option.value === value)?.label || value;
}

function statusLabel(status: string) {
  return (
    STATUS_OPTIONS.find((option) => option.value === status)?.label || status
  );
}

function statusClass(status: string) {
  if (status === "SUCCESS") return "bg-success-lighter text-success";
  if (status === "PARTIAL_SUCCESS") return "bg-warning-light text-warning";
  if (status === "FAILED") return "bg-error-light text-error";
  return "bg-slate-muted text-slate-muted";
}

function uploaderName(item: UploadHistoryItem) {
  return item.diupload_oleh?.nama_lengkap || "User terhapus";
}

async function loadUploadHistory(nextPage?: number) {
  await uploadHistoryStore.fetchUploadHistory({
    search: search.value.trim(),
    status: statusFilter.value,
    source_type: sourceFilter.value,
    tanggal_dari: tanggalDari.value,
    tanggal_sampai: tanggalSampai.value,
    page: nextPage ?? uploadHistoryStore.page,
    limit: uploadHistoryStore.limit,
  });
}

async function onSearch() {
  if (tanggalDari.value && tanggalSampai.value && tanggalSampai.value < tanggalDari.value) {
    uploadHistoryStore.errorMessage =
      "Tanggal sampai tidak boleh lebih awal dari tanggal dari.";
    return;
  }
  await loadUploadHistory(1);
}

async function onResetSearch() {
  search.value = "";
  statusFilter.value = "";
  sourceFilter.value = "";
  tanggalDari.value = "";
  tanggalSampai.value = "";
  await loadUploadHistory(1);
}

async function openDetailModal(item: UploadHistoryItem) {
  selectedId.value = item.id;
  detailError.value = "";
  showDetailModal.value = true;

  try {
    await uploadHistoryStore.fetchUploadHistoryById(item.id);
  } catch {
    detailError.value =
      uploadHistoryStore.errorMessage || "Gagal mengambil detail riwayat upload.";
    uploadHistoryStore.clearError();
  }
}

function closeDetailModal() {
  showDetailModal.value = false;
}

async function goPrev() {
  if (!canGoPrev.value) return;
  await loadUploadHistory(uploadHistoryStore.page - 1);
}

async function goNext() {
  if (!canGoNext.value) return;
  await loadUploadHistory(uploadHistoryStore.page + 1);
}

async function onLimitChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  const nextLimit = Number(target.value) || 10;
  uploadHistoryStore.limit = nextLimit;
  await loadUploadHistory(1);
}

onMounted(async () => {
  await loadUploadHistory(1);
});

async function gotoDashboard() {
  await navigateTo("/dashboard");
}
</script>

<template>
  <main class="min-h-screen bg-page text-14 text-content">
    <Header brand-title="Riwayat Upload" brand-subtitle="Jejak file GeoJSON & Excel yang diunggah beserta pengunggahnya" />
    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <button type="button" aria-label="Back" @click="gotoDashboard"
            class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-light bg-surface text-icon shadow-sm transition-all duration-200 hover-border-navy hover-text-navy hover-bg-slate-light hover:scale-105 active:scale-95">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
              stroke="currentColor" class="h-4 w-4">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>

          <p class="font-semibold tracking-wide text-subtitle">Dashboard</p>
        </div>
      </div>

      <section class="rounded-2xl border border-default bg-surface p-5">
        <div class="mb-4">
          <h2 class="text-20 font-bold">Daftar Riwayat Upload</h2>
          <p class="text-muted">
            Siapa mengunggah file apa, ke data mana, kapan, dan bagaimana hasilnya.
          </p>
        </div>

        <div class="mb-4 grid grid-cols-1 gap-3 md:grid-cols-6">
          <input v-model="search" type="text" placeholder="Cari nama file, tabel tujuan, atau pengunggah..."
            class="h-11 rounded-xl border border-default px-4 outline-none placeholder-text-placeholder md:col-span-2"
            @keyup.enter="onSearch" />
          <select v-model="statusFilter"
            class="h-11 rounded-xl border border-default bg-surface px-3 outline-none md:col-span-1"
            @change="onSearch">
            <option v-for="option in STATUS_OPTIONS" :key="option.label" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <select v-model="sourceFilter"
            class="h-11 rounded-xl border border-default bg-surface px-3 outline-none md:col-span-1"
            @change="onSearch">
            <option v-for="option in SOURCE_OPTIONS" :key="option.label" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <input v-model="tanggalDari" type="date" title="Tanggal upload dari"
            class="h-11 rounded-xl border border-default px-3 outline-none md:col-span-1" @change="onSearch" />
          <input v-model="tanggalSampai" type="date" title="Tanggal upload sampai"
            class="h-11 rounded-xl border border-default px-3 outline-none md:col-span-1" @change="onSearch" />
          <div class="flex items-center gap-2 md:col-span-6 md:justify-end">
            <button class="h-11 rounded-xl bg-brand px-6 font-semibold text-on-brand" @click="onSearch">
              Cari
            </button>
            <button class="h-11 rounded-xl border border-tan bg-cream px-6 font-semibold text-brand"
              @click="onResetSearch">
              Reset
            </button>
          </div>
        </div>

        <p v-if="uploadHistoryStore.errorMessage && !showDetailModal"
          class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ uploadHistoryStore.errorMessage }}
        </p>

        <div class="overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-4 py-3 font-bold">Waktu Upload</th>
                <th class="px-4 py-3 font-bold">Nama File</th>
                <th class="px-4 py-3 font-bold">Tujuan</th>
                <th class="px-4 py-3 font-bold">Periode</th>
                <th class="px-4 py-3 font-bold">Jumlah Data</th>
                <th class="px-4 py-3 font-bold">Status</th>
                <th class="px-4 py-3 font-bold">Diupload Oleh</th>
                <th class="px-4 py-3 font-bold">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="uploadHistoryStore.loadingList" class="border-t border-row">
                <td colspan="8" class="px-4 py-8 text-center text-muted">
                  Memuat riwayat upload...
                </td>
              </tr>

              <tr v-for="item in uploadHistoryStore.items" :key="item.id" class="border-t border-row align-top">
                <td class="px-4 py-3 whitespace-nowrap">{{ formatDateTime(item.mulai) }}</td>
                <td class="max-w-xs px-4 py-3">
                  <p class="break-all font-semibold">{{ item.nama_file || "-" }}</p>
                  <p class="text-12 text-muted">{{ sourceLabel(item.jenis_sumber) }}</p>
                </td>
                <td class="px-4 py-3">
                  <p>{{ item.layer || item.tabel_tujuan }}</p>
                  <p v-if="item.layer" class="text-12 text-muted">{{ item.tabel_tujuan }}</p>
                </td>
                <td class="px-4 py-3 whitespace-nowrap">{{ formatPeriode(item.periode) }}</td>
                <td class="px-4 py-3">{{ item.jumlah_data.toLocaleString("id-ID") }}</td>
                <td class="px-4 py-3">
                  <span class="whitespace-nowrap rounded-full px-3 py-1 text-size-xs font-semibold"
                    :class="statusClass(item.status)">
                    {{ statusLabel(item.status) }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <p>{{ uploaderName(item) }}</p>
                  <p v-if="item.diupload_oleh" class="text-12 text-muted">@{{ item.diupload_oleh.username }}</p>
                </td>
                <td class="px-4 py-3">
                  <button class="rounded-lg border border-tan bg-cream px-3 py-1.5 font-semibold text-brand"
                    @click="openDetailModal(item)">
                    Detail
                  </button>
                </td>
              </tr>

              <tr v-if="!uploadHistoryStore.loadingList && !uploadHistoryStore.hasItems"
                class="border-t border-row">
                <td colspan="8" class="px-4 py-8 text-center text-muted">
                  Belum ada riwayat upload.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <p class="text-muted">
            Total: <span class="font-bold text-content">{{ uploadHistoryStore.totalData }}</span>
            data • Halaman
            <span class="font-bold text-content">{{ uploadHistoryStore.page }}</span>
            dari
            <span class="font-bold text-content">{{ uploadHistoryStore.totalPage }}</span>
          </p>

          <div class="flex items-center gap-2">
            <label class="text-muted">Limit</label>
            <select :value="uploadHistoryStore.limit" class="h-10 rounded-lg border border-tan bg-surface px-2"
              @change="onLimitChange">
              <option :value="5">5</option>
              <option :value="10">10</option>
              <option :value="20">20</option>
              <option :value="50">50</option>
            </select>

            <button
              class="rounded-lg border border-tan bg-surface px-3 py-2 font-semibold text-brand disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canGoPrev" @click="goPrev">
              Prev
            </button>
            <button
              class="rounded-lg border border-tan bg-surface px-3 py-2 font-semibold text-brand disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canGoNext" @click="goNext">
              Next
            </button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="showDetailModal" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4"
      @click.self="closeDetailModal">
      <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-18 font-bold">Detail Riwayat Upload</h3>
          <button class="text-muted" @click="closeDetailModal">✕</button>
        </div>

        <p v-if="uploadHistoryStore.loadingDetail" class="mb-3 text-muted">
          Memuat detail riwayat upload...
        </p>

        <p v-if="detailError" class="mb-3 rounded-xl bg-error-light px-4 py-3 text-error">
          {{ detailError }}
        </p>

        <template v-if="detail">
          <dl class="grid grid-cols-1 gap-x-6 gap-y-3 md:grid-cols-2">
            <div class="md:col-span-2">
              <dt class="text-label">Nama File</dt>
              <dd class="break-all font-semibold">{{ detail.nama_file || "-" }}</dd>
            </div>
            <div>
              <dt class="text-label">Diupload Oleh</dt>
              <dd>
                {{ uploaderName(detail) }}
                <span v-if="detail.diupload_oleh" class="text-muted">(@{{ detail.diupload_oleh.username }})</span>
              </dd>
            </div>
            <div>
              <dt class="text-label">Status</dt>
              <dd>
                <span class="rounded-full px-3 py-1 text-size-xs font-semibold" :class="statusClass(detail.status)">
                  {{ statusLabel(detail.status) }}
                </span>
              </dd>
            </div>
            <div>
              <dt class="text-label">Sumber</dt>
              <dd>{{ sourceLabel(detail.jenis_sumber) }}</dd>
            </div>
            <div>
              <dt class="text-label">Tujuan</dt>
              <dd>{{ detail.layer ? `${detail.layer} (${detail.tabel_tujuan})` : detail.tabel_tujuan }}</dd>
            </div>
            <div>
              <dt class="text-label">Periode Data</dt>
              <dd>{{ formatPeriode(detail.periode) }}</dd>
            </div>
            <div>
              <dt class="text-label">Jumlah Data</dt>
              <dd>{{ detail.jumlah_data.toLocaleString("id-ID") }}</dd>
            </div>
            <div>
              <dt class="text-label">Mulai</dt>
              <dd>{{ formatDateTime(detail.mulai) || "-" }}</dd>
            </div>
            <div>
              <dt class="text-label">Selesai</dt>
              <dd>{{ formatDateTime(detail.selesai) || "-" }} ({{ formatDurasi(detail.durasi_detik) }})</dd>
            </div>
          </dl>

          <div v-if="detail.pesan_error" class="mt-4">
            <p class="mb-1 text-label">Pesan Error</p>
            <p class="whitespace-pre-wrap rounded-xl bg-error-light px-4 py-3 text-error">{{ detail.pesan_error }}</p>
          </div>

          <div v-if="detailMetadata" class="mt-4">
            <p class="mb-1 text-label">Metadata Proses</p>
            <pre
              class="max-h-72 overflow-auto rounded-xl border border-default bg-surface-warm px-4 py-3 text-12">{{ detailMetadata }}</pre>
          </div>
        </template>

        <div class="mt-5 flex justify-end">
          <button class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
            @click="closeDetailModal">
            Tutup
          </button>
        </div>
      </div>
    </div>
  </main>
</template>
