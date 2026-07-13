<script setup lang="ts">
import { computed, ref } from "vue";
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
  const firstFeature = documentUploadStore.previewRows[0];
  if (!firstFeature) return [];
  return Object.keys(firstFeature.properties ?? {});
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

function onSelectCategory(event: Event) {
  const target = event.target as HTMLSelectElement;
  documentUploadStore.setCategory(target.value);
}

async function onSubmitUpload() {
  await documentUploadStore.submitUpload();
}

function onCancelPreview() {
  documentUploadStore.cancelPreview();
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
          <div>
            <label class="mb-1 block text-[#6F645B]">Kategori Data GeoJSON (Spasial)</label>
            <select :value="documentUploadStore.selectedCategory"
              class="h-11 w-full rounded-xl border border-[#EEE6DE] bg-white px-3 outline-none"
              @change="onSelectCategory">
              <option value="" disabled>Pilih kategori</option>
              <option v-for="category in documentUploadStore.categories" :key="category.value" :value="category.value">
                {{ category.label }}
              </option>
            </select>
            <p v-if="selectedCategoryDescription" class="mt-2 text-sm text-[#8A817A]">
              {{ selectedCategoryDescription }}
            </p>
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

        <section v-if="documentUploadStore.hasPreview"
          class="mt-6 rounded-2xl border border-[#EEE6DE] bg-[#FFFEFC] p-4">
          <div class="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 class="text-[18px] font-bold text-[#4D392A]">Preview Data GeoJSON</h3>
              <p class="text-sm text-[#8A817A]">
                Menampilkan {{ documentUploadStore.previewRows.length }} dari
                {{ documentUploadStore.featureCount }} feature.
              </p>
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
                <tr v-for="(feature, index) in documentUploadStore.previewRows" :key="index"
                  class="border-t border-[#F0E8E0]">
                  <td class="px-3 py-2">{{ index + 1 }}</td>
                  <td class="px-3 py-2">{{ feature.geometry?.type ?? "-" }}</td>
                  <td v-for="header in previewHeaders" :key="`${index}-${header}`" class="px-3 py-2">
                    {{ feature.properties?.[header] ?? "-" }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="mt-4 flex justify-end gap-2">
            <button type="button"
              class="rounded-xl border border-[#DDD1C7] bg-[#FFF8F2] px-4 py-2 font-semibold text-[#4D392A]"
              :disabled="isBusy" @click="onCancelPreview">
              Cancel
            </button>
            <button type="button" class="rounded-xl bg-[#4D392A] px-4 py-2 font-semibold text-white disabled:opacity-50"
              :disabled="isBusy" @click="onSubmitUpload">
              {{ documentUploadStore.isUploading ? "Uploading..." : "Submit" }}
            </button>
          </div>
        </section>
      </section>
    </div>
  </main>
</template>
