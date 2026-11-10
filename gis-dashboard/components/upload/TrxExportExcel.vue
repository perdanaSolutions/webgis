<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { blobErrorMessage, filenameFromDisposition, saveBlob } from "~/utils/failedRowsDownload";
import type { TrxKindSpec } from "~/utils/trxUpload";

defineOptions({ name: "UploadTrxExportExcel" });

/**
 * Export data transaksi yang SUDAH tersimpan ke Excel (GET {kind.endpoints.export}).
 * Header file sama dengan template import, jadi bisa diedit lalu diunggah ulang.
 * Wilayah otomatis dibatasi hak akses data role di backend.
 */
const props = defineProps<{ kind: TrxKindSpec; disabled?: boolean }>();

const MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
  "November", "Desember"];
const currentYear = new Date().getFullYear();
const YEARS = Array.from({ length: currentYear - 2015 + 1 }, (_, i) => currentYear - i);

const year = ref<number | "">(currentYear);
const month = ref<number | "">("");
const isDownloading = ref(false);
const errorMessage = ref("");

watch(year, (value) => {
  if (value === "") month.value = "";
});
watch(() => props.kind.id, () => {
  errorMessage.value = "";
});

const periodLabel = computed(() => {
  if (year.value === "") return "semua periode";
  return month.value === "" ? `tahun ${year.value}` : `${MONTHS[Number(month.value) - 1]} ${year.value}`;
});

async function download() {
  if (isDownloading.value) return;
  isDownloading.value = true;
  errorMessage.value = "";
  try {
    const { $api } = useNuxtApp();
    const baseUrl = useRuntimeConfig().public.apiBaseUrlPython || "/api";
    const query: Record<string, number> = {};
    if (year.value !== "") query.tahun = Number(year.value);
    if (year.value !== "" && month.value !== "") query.bulan = Number(month.value);
    const response = await ($api as any).raw(`${baseUrl}${props.kind.endpoints.export}`, {
      method: "GET",
      query,
      responseType: "blob",
      headers: { accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/json" },
    });
    saveBlob(response._data as Blob,
      filenameFromDisposition(response.headers.get("content-disposition"), `${props.kind.id}.xlsx`));
  } catch (error: unknown) {
    errorMessage.value = await blobErrorMessage(error, "Gagal mengekspor data. Silakan coba lagi.");
  } finally {
    isDownloading.value = false;
  }
}
</script>

<template>
  <div class="mt-3 rounded-xl border border-default bg-surface p-4">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p class="text-size-sm font-semibold text-brand">Export data tersimpan ({{ kind.label }})</p>
        <p class="mt-1 text-size-sm text-muted">
          Unduh data yang sudah ada di sistem sebagai Excel. Kolomnya sama dengan template, jadi file bisa diedit
          lalu diunggah ulang. Data mengikuti wilayah yang boleh Anda akses.
        </p>
      </div>
      <div class="flex flex-wrap items-end gap-2">
        <label class="flex flex-col gap-1 text-size-xs text-label">
          Tahun
          <select v-model="year" :disabled="isDownloading"
            class="rounded-lg border border-tan bg-surface px-2 py-1.5 text-size-sm text-brand">
            <option value="">Semua tahun</option>
            <option v-for="y in YEARS" :key="y" :value="y">{{ y }}</option>
          </select>
        </label>
        <label class="flex flex-col gap-1 text-size-xs text-label">
          Bulan
          <select v-model="month" :disabled="isDownloading || year === ''"
            class="rounded-lg border border-tan bg-surface px-2 py-1.5 text-size-sm text-brand disabled:opacity-50">
            <option value="">Semua bulan</option>
            <option v-for="(name, index) in MONTHS" :key="name" :value="index + 1">{{ name }}</option>
          </select>
        </label>
        <button type="button"
          class="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-size-sm font-semibold text-on-brand disabled:opacity-50"
          :disabled="disabled || isDownloading" :aria-busy="isDownloading" @click="download">
          <svg v-if="isDownloading" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" opacity="0.25" />
            <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" stroke-width="3" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24"
            stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
          </svg>
          {{ isDownloading ? "Menyiapkan file..." : "Export Excel" }}
        </button>
      </div>
    </div>
    <p v-if="isDownloading && year === ''" class="mt-2 text-size-xs text-muted">
      Export semua periode bisa memakan waktu sekitar satu menit.
    </p>
    <p v-if="errorMessage" class="mt-2 rounded-lg bg-error-light px-3 py-2 text-size-sm text-error">{{ errorMessage }}</p>
    <p class="sr-only" aria-live="polite">{{ isDownloading ? `Menyiapkan export ${periodLabel}` : "" }}</p>
  </div>
</template>
