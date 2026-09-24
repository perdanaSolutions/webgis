<script setup lang="ts">
import { computed, ref, watch, onMounted } from "vue";
import Header from "~/components/Header.vue";
import { useDocumentUploadStore } from "~/stores/documentUploadStore";

defineOptions({
  name: "DocumentUploadPage",
});

const documentUploadStore = useDocumentUploadStore();
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

const filteredPreviewRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  if (!query) return documentUploadStore.allPreviewRows;

  return documentUploadStore.allPreviewRows.filter((feature) => {
    const geometryType = String(feature.geometry?.type ?? "").toLowerCase();
    const propertiesValues = Object.values(feature.properties ?? {})
      .map((value) => String(value ?? "").toLowerCase())
      .join(" ");

    return (
      geometryType.includes(query) ||
      propertiesValues.includes(query)
    );
  });
});

onMounted(async () => {
  await documentUploadStore.initDataKategori();
});

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
    isThereReplaceData.value = true;
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
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
}

async function gotoDashboard() {
  await navigateTo("/dashboard");
}

const parsedDataObject = computed(() => {
  const rawData = documentUploadStore.summaryAnalyze.data;
  if (!rawData) return {};

  // Jika 'data' masih berupa string JSON, parse dulu. Jika sudah objek, langsung return.
  return typeof rawData === 'string' ? JSON.parse(rawData) : rawData;
});

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
          <h2 class="text-20 font-bold">Upload File GeoJSON</h2>
          <p class="text-muted">
            Pilih kategori spasial, upload file GeoJSON, lalu review preview data
            sebelum submit.
          </p>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div class="mb-4">
            <div class="mb-4">
              <label class="mb-1 block text-label font-medium">Kategori Data GeoJSON (Spasial)</label>
              <v-select :model-value="documentUploadStore.selectedCategory" :items="documentUploadStore.categories"
                :loading="documentUploadStore.isLoadingCategories" item-title="label" item-value="value"
                placeholder="Pilih kategori" variant="plain" density="comfortable"
                class="w-full px-3 border border-default rounded-xl h-[50px]"
                @update:model-value="onSelectCategory"></v-select>
              <p v-if="selectedCategoryDescription" class="mt-2 text-size-sm text-muted">
                {{ selectedCategoryDescription }}
              </p>
            </div>
          </div>

          <div class="">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="mb-1 block text-label font-medium">Bulan</label>
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
                <label class="mb-1 block text-label font-medium">Tahun</label>
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

        <div class="mt-5 rounded-2xl border border-dashed border-tan-hover bg-cream-light p-6 text-center" @drop="onDrop"
          @dragover="onDragOver">
          <input ref="fileInputRef" type="file" accept=".geojson,.json,application/geo+json,application/json"
            class="hidden" @change="onFileChange" />
          <p class="text-15 font-semibold text-brand">
            Drag & Drop file GeoJSON di sini
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

        <div v-if="isBusy" class="mt-5 rounded-xl border border-default bg-surface p-4">
          <div class="mb-2 flex items-center justify-between text-size-sm">
            <span class="font-semibold text-brand">
              {{ documentUploadStore.isUploading ? "Proses upload..." : "Memvalidasi file..." }}
            </span>
            <span class="text-muted">{{ documentUploadStore.uploadProgress }}%</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-progress-bar">
            <div
              class="h-full rounded-full bg-gradient-to-r gradient-brand-alt transition-all duration-500 ease-out"
              :style="{ width: `${documentUploadStore.uploadProgress}%` }" />
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
              <input v-model="searchQuery" type="text" placeholder="Cari di geometry / semua kolom..."
                class="w-full rounded-xl border border-tan bg-surface px-3 py-2 text-size-sm text-brand outline-none focus-border-accent-brown" />
            </div>
          </div>

          <div class="overflow-x-auto rounded-xl border border-default">
            <table class="min-w-full bg-surface text-size-sm">
              <thead class="bg-surface-warm text-left text-brand">
                <tr>
                  <th class="px-3 py-2 font-bold">No</th>
                  <th class="px-3 py-2 font-bold">Geometry</th>
                  <th v-for="header in previewHeaders" :key="header" class="px-3 py-2 font-bold">
                    {{ header }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(feature, index) in paginatedPreviewRows" :key="index" class="border-t border-row">
                  <td class="px-3 py-2">{{ (currentPage - 1) * itemsPerPage + index + 1 }}</td>
                  <td class="px-3 py-2">{{ feature.geometry?.type ?? "-" }}</td>
                  <td v-for="header in previewHeaders" :key="`${index}-${header}`" class="px-3 py-2">
                    {{ feature.properties?.[header] ?? "-" }}
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
            <button type="button"
              class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              :disabled="isBusy" @click="onCancelPreview">
              Cancel
            </button>
            <button type="button" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="isBusy" @click="onSubmitUpload">
              {{ documentUploadStore.isUploading ? "Uploading..." : "Submit" }}
            </button>
          </div>
        </section>

        <div v-if="Object.keys(documentUploadStore.summaryAnalyze).length > 0" class="mt-6 space-y-6">

          <div class="bg-surface rounded-2xl border border-default p-6 shadow-sm space-y-4">
            <!-- 3. Rincian Data (Di-unpack agar tidak berbentuk JSON mentah) -->
            <div class="pt-2">
              <p class="text-size-xs font-bold tracking-wider text-muted uppercase mb-2 px-1">Rincian Data</p>

              <div class="space-y-3">
                <template v-for="(value, key) in parsedDataObject" :key="key">
                  <div
                    class="flex items-center justify-between p-3.5 bg-surface-neutral hover-bg-surface-neutral-hover-60 border border-default-60 rounded-xl transition-all duration-200">
                    <!-- Key di Kiri -->
                    <div class="flex items-center gap-3 pr-4">
                      <div class="w-1.5 h-1.5 rounded-full bg-muted-dot"></div>
                      <span class="text-size-sm font-medium text-label capitalize">
                        {{ String(key).replace(/_/g, ' ').toLowerCase() }}
                      </span>
                    </div>

                    <!-- Value di Kanan -->
                    <div class="text-right shrink-0">
                      <span
                        class="text-size-sm font-bold text-content-brown bg-surface px-3 py-1.5 rounded-lg border border-default">
                        {{ typeof value === 'number' ? value.toLocaleString('id-ID') : value }}
                      </span>
                    </div>
                  </div>
                </template>
              </div>
            </div>

          </div>

          <div v-if="Object.keys(documentUploadStore.summaryAnalyze).length > 0" class="mt-4 flex justify-end gap-2">
            <button type="button"
              class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              :disabled="isBusy" @click="onCancelPreview">
              Cancel
            </button>
            <button type="button" class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="isBusy" @click="onSubmitUpload">
              {{ documentUploadStore.isUploading ? "Uploading..." : "Submit Analisis" }}
            </button>
          </div>

          <div v-if="documentUploadStore.summaryAnalyze.data_tidak_valid > 0"
            class="p-4 bg-error-light border border-error rounded-xl text-size-sm text-error-dark flex gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2"
              stroke="currentColor" class="w-5 h-5 flex-shrink-0">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
            <span>Perhatian: Terdapat {{ documentUploadStore.summaryAnalyze.data_tidak_valid }} data tidak valid yang
              terdeteksi.</span>
          </div>
        </div>

      </section>
    </div>
  </main>

  <div v-if="isOpenModalValidasi" class="fixed inset-0 z-50 flex items-center justify-center bg-overlay-dark p-4">
    <!-- Modal Card -->
    <div class="w-full max-w-md rounded-xl bg-surface p-6 shadow-2xl">
      <div class="fixed inset-0 z-50 flex items-center justify-center bg-overlay-dark p-4 transition-opacity duration-200">
        <!-- Dialog Card -->
        <div class="w-full max-w-md rounded-xl bg-surface p-6 shadow-2xl transition-all">
          <!-- Header Modal -->
          <div class="flex items-center space-x-3 text-warning">
            <div class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-warning-light">
              <!-- Icon Peringatan/Tanya -->
              <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
            </div>
            <h3 class="text-size-lg font-semibold text-gray-title-alt">
              Konfirmasi Analisis
            </h3>
          </div>

          <!-- Isi Pesan Pertanyaan -->
          <div class="mt-3 pl-13">
            <p v-if="isThereReplaceData" class="text-size-sm text-gray-body">
              Apakah Anda yakin untuk submit analisis ini? Data akan di replace menggunakan data terbaru.
            </p>
            <p v-else class="text-size-sm text-gray-body">
              Apakah Anda yakin untuk submit analisis ini?
            </p>
          </div>

          <div class="mt-4 w-full flex justify-end space-x-3">
            <button @click="isOpenModalValidasi = false"
              class="rounded-lg border border-gray bg-surface px-4 py-2 text-size-sm font-medium text-gray-label-alt hover-bg-gray-light focus:outline-none focus:ring-2 focus-ring-gray focus:ring-offset-1 transition">Cancel</button>
            <button @click="actionSubmit"
              class="rounded-lg bg-blue-dark px-4 py-2 text-size-sm font-medium text-on-brand hover-bg-blue-darker focus:outline-none focus:ring-2 focus-ring-blue focus:ring-offset-1 transition shadow-sm">Submit</button>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>
