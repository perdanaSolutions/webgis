<script setup lang="ts">
import { computed, ref, watch } from "vue";
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
  if (parseInt(documentUploadStore.summaryAnalyze.data_akan_ditimpa_di_periode_ini) > 0) {
    isOpenModalValidasi.value = true;
  } else {
    await documentUploadStore.submitUpload();
  }

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
</script>

<template>
  <main class="min-h-screen bg-[#FBFAF8] text-[14px] text-[#2E1F18]">
    <Header brand-title="Management Document" brand-subtitle="Upload & validasi data GeoJSON spasial" />

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <div class="mb-4 flex items-center gap-3">
        <button type="button" aria-label="Back" @click="gotoDashboard"
          class="flex h-8 w-8 items-center justify-center rounded-full border border-[#D8DEE8] bg-white text-[#566074] shadow-sm transition-all duration-200 hover:border-[#1A315B] hover:bg-slate-50 hover:text-[#1A315B] hover:scale-105 active:scale-95">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
            stroke="currentColor" class="h-4 w-4">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
        <p class="font-semibold tracking-wide text-[#333d4e]">Dashboard</p>
      </div>

      <section class="rounded-2xl border border-[#EEE6DE] bg-white p-5">
        <div class="mb-6">
          <h2 class="text-[20px] font-bold">Upload File GeoJSON</h2>
          <p class="text-[#8A817A]">
            Pilih kategori spasial, upload file GeoJSON, lalu review preview data
            sebelum submit.
          </p>
        </div>

        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div class="mb-4">
            <div class="mb-4">
              <label class="mb-1 block text-[#6F645B] font-medium">Kategori Data GeoJSON (Spasial)</label>
              <v-select :model-value="documentUploadStore.selectedCategory" :items="documentUploadStore.categories"
                item-title="label" item-value="value" placeholder="Pilih kategori" variant="plain" density="comfortable"
                class="w-full px-3 border border-[#EEE6DE] rounded-xl h-[50px]"
                @update:model-value="onSelectCategory"></v-select>
              <p v-if="selectedCategoryDescription" class="mt-2 text-sm text-[#8A817A]">
                {{ selectedCategoryDescription }}
              </p>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="mb-1 block text-[#6F645B] font-medium">Bulan</label>
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
                  class="w-full px-3 border border-[#EEE6DE] rounded-xl h-[50px]"></v-select>
              </div>

              <div>
                <label class="mb-1 block text-[#6F645B] font-medium">Tahun</label>
                <v-select v-model="documentUploadStore.year" :items="documentUploadStore.getYearList()"
                  placeholder="Pilih tahun" variant="plain" density="comfortable"
                  class="w-full px-3 border border-[#EEE6DE] rounded-xl h-[50px]"></v-select>
              </div>
            </div>
          </div>



          <div class="rounded-xl border border-dashed border-[#D8CFC6] bg-[#FFF8F2] p-4">
            <p class="mb-2 font-semibold text-[#4D392A]">Daftar kategori & ketentuan:</p>
            <ul class="space-y-1 text-sm text-[#6F645B]">
              <li v-for="category in documentUploadStore.categories" :key="category.value">
                • {{ category.label }} — {{ category.description }}
              </li>
            </ul>
          </div>
        </div>

        <div class="mt-5 rounded-2xl border border-dashed border-[#D8CFC6] bg-[#FFFCF8] p-6 text-center" @drop="onDrop"
          @dragover="onDragOver">
          <input ref="fileInputRef" type="file" accept=".geojson,.json,application/geo+json,application/json"
            class="hidden" @change="onFileChange" />
          <p class="text-[15px] font-semibold text-[#4D392A]">
            Drag & Drop file GeoJSON di sini
          </p>
          <p class="mt-1 text-sm text-[#8A817A]">atau</p>
          <button type="button"
            class="mt-3 rounded-xl bg-[#4D392A] px-5 py-2.5 font-semibold text-white disabled:opacity-50"
            :disabled="isBusy" @click="openFilePicker">
            Pilih File
          </button>
          <p v-if="documentUploadStore.selectedFile" class="mt-3 text-sm text-[#6F645B]">
            File: <span class="font-semibold">{{ documentUploadStore.selectedFile.name }}</span>
          </p>
        </div>

        <div v-if="isBusy" class="mt-5 rounded-xl border border-[#EEE6DE] bg-white p-4">
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="font-semibold text-[#4D392A]">
              {{ documentUploadStore.isUploading ? "Proses upload..." : "Memvalidasi file..." }}
            </span>
            <span class="text-[#8A817A]">{{ documentUploadStore.uploadProgress }}%</span>
          </div>
          <div class="h-2 overflow-hidden rounded-full bg-[#F2EAE2]">
            <div
              class="h-full rounded-full bg-gradient-to-r from-[#8B5E3C] to-[#4D392A] transition-all duration-500 ease-out"
              :style="{ width: `${documentUploadStore.uploadProgress}%` }" />
          </div>
        </div>

        <p v-if="documentUploadStore.errorMessage" class="mt-4 rounded-xl bg-red-50 px-4 py-3 text-red-600">
          {{ documentUploadStore.errorMessage }}
        </p>

        <p v-if="documentUploadStore.successMessage" class="mt-4 rounded-xl bg-green-50 px-4 py-3 text-green-700">
          {{ documentUploadStore.successMessage }}
        </p>

        <div v-if="Object.keys(documentUploadStore.summaryAnalyze).length > 0" class="mt-6 space-y-6">

          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[#EEE6DE] pb-4">
            <div>
              <h3 class="text-lg font-bold text-[#6F645B]">Hasil Analisis Unggahan</h3>
              <p class="text-sm text-[#8A817A]">Periode Data: {{ documentUploadStore.summaryAnalyze.periode }}</p>
            </div>
            <span
              class="mt-2 sm:mt-0 inline-flex items-center rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20 w-fit">
              {{ documentUploadStore.summaryAnalyze.tipe_upload?.replace(/_/g, ' ') }}
            </span>
          </div>

          <div
            class="bg-gradient-to-br from-emerald-50 to-emerald-100/50 rounded-2xl border border-emerald-200 p-5 flex items-center justify-between shadow-sm">
            <div>
              <p class="text-sm font-medium text-emerald-800/80 uppercase tracking-wider">Data Baru di Periode Ini
              </p>
            </div>
            <div class="rounded-xl text-green shadow-sm">
              {{ documentUploadStore.summaryAnalyze.data_baru_di_periode_ini }} <span
                class="text-sm font-normal">Fitur</span>
              <!-- <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
                stroke="currentColor" class="w-6 h-6">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg> -->
            </div>
          </div>

          <div
            class="bg-gradient-to-br from-red-50 to-red-100/50 rounded-2xl border border-red-200 p-5 flex items-center justify-between shadow-sm">
            <div>
              <p class="text-sm font-medium text-red-800/80 uppercase tracking-wider">Data Replace di Periode Ini
              </p>
            </div>
            <div class="rounded-xl text-red shadow-sm">
              {{ documentUploadStore.summaryAnalyze.data_akan_ditimpa_di_periode_ini }} <span
                class="text-sm font-normal">Fitur</span>
              <!-- <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5"
                stroke="currentColor" class="w-6 h-6">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg> -->
            </div>
          </div>

          <div class="bg-white rounded-2xl border border-[#EEE6DE] p-5 shadow-sm">
            <p class="text-sm font-semibold text-[#6F645B] mb-4 uppercase tracking-wider">Struktur Data Spasial</p>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">

              <div class="flex items-center justify-between p-4 bg-[#FDFBF7] border border-[#EEE6DE] rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-blue-50 text-blue-600 rounded-lg font-bold text-xs">AREA</div>
                  <span class="text-sm font-medium text-[#6F645B]"> Jumlah Data Area</span>
                </div>
                <span class="text-base font-bold text-[#6F645B]">
                  {{ documentUploadStore.summaryAnalyze.ringkasan_struktur_data?.jumlah_master_area }}
                </span>
              </div>

              <div class="flex items-center justify-between p-4 bg-[#FDFBF7] border border-[#EEE6DE] rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-blue-50 text-blue-600 rounded-lg font-bold text-xs">PT</div>
                  <span class="text-sm font-medium text-[#6F645B]"> Jumlah Data Perusahaan</span>
                </div>
                <span class="text-base font-bold text-[#6F645B]">
                  {{ documentUploadStore.summaryAnalyze.ringkasan_struktur_data?.jumlah_perusahaan_pt }}
                </span>
              </div>

              <div class="flex items-center justify-between p-4 bg-[#FDFBF7] border border-[#EEE6DE] rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-amber-50 text-amber-600 rounded-lg font-bold text-xs">EST</div>
                  <span class="text-sm font-medium text-[#6F645B]">Jumlah Data Estate</span>
                </div>
                <span class="text-base font-bold text-[#6F645B]">
                  {{ documentUploadStore.summaryAnalyze.ringkasan_struktur_data?.jumlah_estate }}
                </span>
              </div>

              <div class="flex items-center justify-between p-4 bg-[#FDFBF7] border border-[#EEE6DE] rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-purple-50 text-purple-600 rounded-lg font-bold text-xs">AFD</div>
                  <span class="text-sm font-medium text-[#6F645B]">Jumlah Data Afdeling</span>
                </div>
                <span class="text-base font-bold text-[#6F645B]">
                  {{ documentUploadStore.summaryAnalyze.ringkasan_struktur_data?.jumlah_afdeling }}
                </span>
              </div>

              <div class="flex items-center justify-between p-4 bg-[#FDFBF7] border border-[#EEE6DE] rounded-xl">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-orange-50 text-orange-600 rounded-lg font-bold text-xs">BLK</div>
                  <span class="text-sm font-medium text-[#6F645B]">Jumlah Data Blok</span>
                </div>
                <span class="text-base font-bold text-[#6F645B]">
                  {{ documentUploadStore.summaryAnalyze.ringkasan_struktur_data?.jumlah_blok }}
                </span>
              </div>
            </div>

            <div class="mt-4 flex justify-end gap-2">
              <button v-if="Object.keys(documentUploadStore.summaryAnalyze).length > 0" type="button"
                class="rounded-xl bg-[#4D392A] px-4 py-2 font-semibold text-white disabled:opacity-50"
                :disabled="isBusy" @click="onSubmitUpload">
                {{ documentUploadStore.isUploading ? "Uploading..." : "Submit Analisis" }}
              </button>
            </div>

          </div>

          <div v-if="documentUploadStore.summaryAnalyze.data_tidak_valid > 0"
            class="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800 flex gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2"
              stroke="currentColor" class="w-5 h-5 flex-shrink-0">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
            </svg>
            <span>Perhatian: Terdapat {{ documentUploadStore.summaryAnalyze.data_tidak_valid }} data tidak valid yang
              terdeteksi.</span>
          </div>
        </div>

        <section v-if="documentUploadStore.hasPreview"
          class="mt-6 rounded-2xl border border-[#EEE6DE] bg-[#FFFEFC] p-4">
          <div class="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 class="text-[18px] font-bold text-[#4D392A]">Preview Data GeoJSON</h3>
              <p class="text-sm text-[#8A817A]">
                Menampilkan {{ startItem }} - {{ endItem }} dari
                {{ totalPreviewRows }} feature
                <span v-if="searchQuery.trim()">
                  (hasil pencarian dari total {{ documentUploadStore.featureCount }} feature)
                </span>.
              </p>
            </div>

            <div class="w-full md:w-[320px]">
              <input v-model="searchQuery" type="text" placeholder="Cari di geometry / semua kolom..."
                class="w-full rounded-xl border border-[#DDD1C7] bg-white px-3 py-2 text-sm text-[#4D392A] outline-none focus:border-[#8B5E3C]" />
            </div>
          </div>

          <div class="overflow-x-auto rounded-xl border border-[#EEE6DE]">
            <table class="min-w-full bg-white text-sm">
              <thead class="bg-[#F8F3EE] text-left text-[#4D392A]">
                <tr>
                  <th class="px-3 py-2 font-bold">No</th>
                  <th class="px-3 py-2 font-bold">Geometry</th>
                  <th v-for="header in previewHeaders" :key="header" class="px-3 py-2 font-bold">
                    {{ header }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(feature, index) in paginatedPreviewRows" :key="index" class="border-t border-[#F0E8E0]">
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
            <p class="text-sm text-[#8A817A]">
              Menampilkan {{ startItem }} - {{ endItem }} dari {{ totalPreviewRows }} data
            </p>

            <div class="flex items-center gap-2">
              <button type="button"
                class="rounded-lg border border-[#DDD1C7] bg-white px-3 py-1.5 text-sm font-semibold text-[#4D392A] disabled:opacity-50"
                :disabled="currentPage === 1" @click="goToPrevPage">
                Sebelumnya
              </button>

              <span class="text-sm text-[#6F645B]">
                Halaman {{ currentPage }} / {{ totalPages }}
              </span>

              <button type="button"
                class="rounded-lg border border-[#DDD1C7] bg-white px-3 py-1.5 text-sm font-semibold text-[#4D392A] disabled:opacity-50"
                :disabled="currentPage === totalPages" @click="goToNextPage">
                Berikutnya
              </button>
            </div>
          </div>

          <div class="mt-4 flex justify-end gap-2">
            <button type="button"
              class="rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-2 font-semibold text-[#4D392A]"
              :disabled="isBusy" @click="onCancelPreview">
              Cancel
            </button>
            <button v-if="Object.keys(documentUploadStore.summaryAnalyze).length === 0" type="button"
              class="rounded-xl bg-[#4D392A] px-4 py-2 font-semibold text-white disabled:opacity-50" :disabled="isBusy"
              @click="onSubmitUpload">
              {{ documentUploadStore.isUploading ? "Uploading..." : "Submit" }}
            </button>
          </div>
        </section>
      </section>
    </div>
  </main>

  <div v-if="isOpenModalValidasi" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <!-- Modal Card -->
    <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 transition-opacity duration-200">
        <!-- Dialog Card -->
        <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl transition-all">
          <!-- Header Modal -->
          <div class="flex items-center space-x-3 text-amber-600">
            <div class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-amber-100">
              <!-- Icon Peringatan/Tanya -->
              <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
            </div>
            <h3 class="text-lg font-semibold text-gray-900">
              Konfirmasi Analisis
            </h3>
          </div>

          <!-- Isi Pesan Pertanyaan -->
          <div class="mt-3 pl-13">
            <p class="text-sm text-gray-600">
              Apakah Anda yakin untuk submit analisis ini? Data yang sudah dikirim tidak dapat diubah kembali.
            </p>
          </div>

          <div class="mt-4 w-full flex justify-end space-x-3">
            <button @click="isOpenModalValidasi = false"
              class="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-1 transition">Cancel</button>
            <button @click="documentUploadStore.submitUpload()"
              class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 transition shadow-sm">Submit</button>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>
