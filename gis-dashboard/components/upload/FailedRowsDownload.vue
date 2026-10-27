<script setup lang="ts">
import { ref } from "vue";
import {
  blobErrorMessage,
  failedRowsUrl,
  filenameFromDisposition,
  saveBlob,
} from "~/utils/failedRowsDownload";

defineOptions({ name: "UploadFailedRowsDownload" });

/** Tombol unduh SEMUA data gagal (semua part) sebagai Excel. Tampil hanya bila count > 0 dan jobId ada. */
const props = withDefaults(defineProps<{
  jobId: string | null | undefined;
  count: number;
  label?: string;
}>(), { label: "Download Data Gagal (.xlsx)" });

const isDownloading = ref(false);
const errorMessage = ref("");

async function download() {
  if (!props.jobId || isDownloading.value) return;
  const { $api } = useNuxtApp();
  isDownloading.value = true;
  errorMessage.value = "";
  try {
    const baseUrl = useRuntimeConfig().public.apiBaseUrlPython || "/api";
    const response = await ($api as any).raw(failedRowsUrl(String(baseUrl), props.jobId), {
      method: "GET",
      responseType: "blob",
      headers: { accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/json" },
    });
    const filename = filenameFromDisposition(response.headers.get("content-disposition"), "data_gagal.xlsx");
    saveBlob(response._data as Blob, filename);
  } catch (error: unknown) {
    errorMessage.value = await blobErrorMessage(error, "Gagal mengunduh data gagal. Silakan coba lagi.");
  } finally {
    isDownloading.value = false;
  }
}
</script>

<template>
  <div v-if="jobId && count > 0" class="flex flex-col items-end gap-2">
    <button type="button"
      class="inline-flex items-center gap-2 rounded-xl border border-error bg-error-light px-4 py-2 text-size-sm font-semibold text-error-dark disabled:opacity-50"
      :disabled="isDownloading" :aria-busy="isDownloading" @click="download">
      <svg v-if="isDownloading" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.25" />
        <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" stroke-width="3" />
      </svg>
      <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24"
        stroke="currentColor" stroke-width="2" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
      </svg>
      {{ isDownloading ? "Menyiapkan file..." : `${label} · ${count.toLocaleString("id-ID")} data` }}
    </button>
    <p v-if="errorMessage" class="rounded-xl bg-error-light px-3 py-2 text-size-sm text-error">{{ errorMessage }}</p>
  </div>
</template>
