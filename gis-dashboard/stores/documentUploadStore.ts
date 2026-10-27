import { defineStore } from "pinia";
import { newUploadGroupId } from "~/utils/uploadGroupId";
import { getErrorMessage } from "~/utils/getErrorMessage";
import {
  GEOJSON_FEATURES_PER_PART,
  chunkFeatureCollection,
  featureCollectionToFile,
  mergeAnalyzeResults,
  indexTablePreview,
  isPartAnalyzeResponse,
  partFeatureOffset,
  summarizePart,
  type PartAnalyzeSummary,
  type PreviewAnalysisRow,
  mergeExecuteResults,
  type GeoJsonCollection as PartGeoJsonCollection,
  type GeoJsonFeature as PartGeoJsonFeature,
} from "~/utils/geojsonFeatureParts";

type GeoCatalogEndpoints = {
  upload_analyze: string;
  upload_execute: string;
  geojson?: string;
  list?: string;
  cleanup_period?: string;
};

type GeoCatalogItem = {
  kode: string;
  nama: string;
  deskripsi: string | null;
  geometry_type: string;
  relasi_blok: boolean;
  handler_type: "LEGACY" | "GENERIC";
  endpoints: GeoCatalogEndpoints;
};

type UploadCategory = {
  value: string;
  label: string;
  description: string;
  is_dynamic: boolean;
  endpoints: GeoCatalogEndpoints;
};

export type ThemeColumn = {
  nama_properti: string;
  nama_kolom: string;
  tipe: "boolean" | "integer" | "float" | "date" | "text";
  nullable: boolean;
};

export type SampleAnalysis = {
  geometry_type: string;
  jumlah_data_dianalisis: number;
  jumlah_data_total_di_file: number;
  kolom: ThemeColumn[];
};

export type CreateThemePayload = {
  kode: string;
  nama: string;
  deskripsi: string | null;
  geometry_type: string;
  relasi_blok: boolean;
  kolom: ThemeColumn[];
};

export type UploadJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type UploadJob = {
  job_id: string;
  status: UploadJobStatus;
  kind: "analyze" | "execute";
  layer: string;
  bulan: number;
  tahun: number;
  filename: string | null;
  file_size?: number | null;
  stage: string | null;
  message: string | null;
  current: number | null;
  total: number | null;
  elapsed_seconds: number;
  queue_ahead: number | null;
  cancel_requested: boolean;
  error_message: string | null;
  batch_id: string | null;
  upload_group_id?: string | null;
  part_index?: number | null;
  part_total?: number | null;
  result?: Record<string, any> | null;
};

export type MultipartUploadProgress = {
  groupId: string;
  kind: "analyze" | "execute";
  partIndex: number;
  partTotal: number;
};

const JOB_STORAGE_KEY = "document-upload-job-id";
const JOB_POLL_MS = 1500;
const JOB_POLL_MAX_ERRORS = 5;
const FINISHED_STATUSES: UploadJobStatus[] = [
  "succeeded",
  "failed",
  "cancelled",
];

// Di luar state Pinia: timer tetap jalan saat pengguna pindah halaman di dalam SPA.
let jobPollTimer: ReturnType<typeof setTimeout> | null = null;

function rememberJob(jobId: string | null) {
  if (!import.meta.client) return;
  if (jobId) sessionStorage.setItem(JOB_STORAGE_KEY, jobId);
  else sessionStorage.removeItem(JOB_STORAGE_KEY);
}

function mapCatalogToCategory(item: GeoCatalogItem): UploadCategory {
  return {
    value: item.kode,
    label: item.nama,
    description: item.deskripsi ?? "",
    is_dynamic: item.handler_type === "GENERIC",
    endpoints: item.endpoints,
  };
}

type GeoJsonFeature = PartGeoJsonFeature;
type GeoJsonCollection = PartGeoJsonCollection;

function getAuthHeaders() {
  return {
    accept: "application/json",
    "Content-Type": "application/json",
  };
}

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython || "/api";
}

function readUploadError(error: unknown, fallback: string) {
  const data = (error as { data?: unknown } | null)?.data;
  if (data) {
    try {
      return getErrorMessage(error, fallback);
    } catch {
      return fallback;
    }
  }
  return error instanceof Error && error.message ? error.message : fallback;
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export const useDocumentUploadStore = defineStore("document-upload", {
  state: () => ({
    categories: [] as UploadCategory[],
    isLoadingCategories: false,
    selectedCategory: "" as string,
    month: "" as string,
    year: "" as string,
    selectedFile: null as File | null,
    parsedGeoJson: null as GeoJsonCollection | null,
    allPreviewRows: [] as GeoJsonFeature[],
    errorMessage: "" as string,
    successMessage: "" as string,
    summaryAnalyze: {} as Record<string, any>,
    executeResponse: null as Record<string, any> | null,
    executeError: "" as string,
    isParsing: false,
    isUploading: false,
    uploadProgress: 0,
    activeJob: null as UploadJob | null,
    isCancellingJob: false,
    jobPollErrors: 0,
    /** Progress part Feature (1.000/feature) saat analyze/execute beruntun. */
    multipart: null as MultipartUploadProgress | null,
    multipartAbort: false,
    /** job_id terakhir per tahap (analyze/execute), untuk unduhan Excel data gagal semua part. */
    failedRowsJobId: { analyze: null, execute: null } as Record<"analyze" | "execute", string | null>,
    /** Hasil analisa per baris preview (key = no_preview global), terisi bertahap per part. */
    previewAnalysis: {} as Record<number, PreviewAnalysisRow>,
    /** Ringkasan analisa_aman/analisa_gagal tiap part yang sudah selesai (tampil langsung). */
    analyzeParts: [] as PartAnalyzeSummary[],
    /** Gabungan sementara part yang sudah selesai saat analyze masih berjalan. */
    liveAnalyze: {} as Record<string, any>,
  }),

  getters: {
    hasPreview(state): boolean {
      return Boolean(state.parsedGeoJson && state.allPreviewRows.length > 0);
    },
    featureCount(state): number {
      return state.parsedGeoJson?.features?.length ?? 0;
    },
  },

  actions: {
    resetMessages() {
      this.errorMessage = "";
      this.failedRowsJobId = { analyze: null, execute: null };
      this.successMessage = "";
      this.summaryAnalyze = {};
      this.previewAnalysis = {};
      this.analyzeParts = [];
      this.liveAnalyze = {};
      this.executeResponse = null;
      this.executeError = "";
    },

    resetSelection() {
      this.selectedFile = null;
      this.parsedGeoJson = null;
      this.allPreviewRows = [];
      this.uploadProgress = 0;
      this.resetMessages();
    },

    getYearList() {
      const currentYear = new Date().getFullYear(); // Mendapatkan tahun sekarang (2026)
      const years = [];

      // Looping untuk mengambil tahun sekarang sampai 10 tahun ke belakang
      for (let i = 0; i <= 10; i++) {
        years.push(String(currentYear - i));
      }

      return years;
    },

    setCategory(category: string) {
      this.selectedCategory = category;
      this.resetMessages();
    },

    async setFile(file: File | null) {
      this.resetMessages();
      this.selectedFile = file;
      this.parsedGeoJson = null;
      this.allPreviewRows = [];

      if (!file) return;

      const lowerName = file.name.toLowerCase();
      const isGeoJsonName =
        lowerName.endsWith(".geojson") || lowerName.endsWith(".json");
      if (!isGeoJsonName) {
        this.errorMessage = "File harus berformat .geojson atau .json";
        return;
      }
      this.isParsing = true;
      this.uploadProgress = 10;

      try {
        const text = await file.text();
        this.uploadProgress = 40;
        const json = JSON.parse(text) as GeoJsonCollection;

        if (
          json.type !== "FeatureCollection" ||
          !Array.isArray(json.features)
        ) {
          throw new Error(
            "Format GeoJSON tidak valid (harus FeatureCollection).",
          );
        }

        this.uploadProgress = 75;
        this.parsedGeoJson = json;
        this.allPreviewRows = json.features as GeoJsonFeature[];
        this.uploadProgress = 100;
      } catch (error) {
        this.parsedGeoJson = null;
        this.allPreviewRows = [];
        this.uploadProgress = 0;
        this.errorMessage =
          error instanceof Error
            ? error.message
            : "Gagal membaca file GeoJSON.";
      } finally {
        this.isParsing = false;
      }
    },

    cancelPreview() {
      this.resetSelection();
    },

    /** Unduh standar format GeoJSON (template .geojson / petunjuk .md) untuk satu kategori. */
    async downloadTemplate(kode: string, format: "geojson" | "md" = "geojson") {
      const { $api } = useNuxtApp();
      try {
        const blob = await $api<Blob>(
          `${getApiBaseUrl()}/v1/spatial/geo/template/${encodeURIComponent(kode)}`,
          { method: "GET", headers: getAuthHeaders(), query: { format }, responseType: "blob" },
        );
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = format === "md" ? `petunjuk_standar_${kode}.md` : `standar_${kode}.geojson`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (error: unknown) {
        throw new Error(getErrorMessage(error, "Gagal mengunduh standar format GeoJSON."));
      }
    },

    async initDataKategori() {
      const { $api } = useNuxtApp();
      this.isLoadingCategories = true;
      this.errorMessage = "";
      try {
        const baseUrl = getApiBaseUrl();
        const response = await $api<GeoCatalogItem[]>(
          `${baseUrl}/v1/spatial/geo/catalog`,
          {
            method: "GET",
            headers: getAuthHeaders(),
          },
        );

        this.categories = Array.isArray(response)
          ? response.map(mapCatalogToCategory)
          : [];

        return this.categories;
      } catch (error: unknown) {
        this.errorMessage = getErrorMessage(
          error,
          "Terjadi kesalahan saat memuat kategori data. Silakan coba lagi.",
        );
        throw error;
      } finally {
        this.isLoadingCategories = false;
      }
    },

    async analyzeSample(file: File): Promise<SampleAnalysis> {
      const { $api } = useNuxtApp();
      const formData = new FormData();
      formData.append("file", file);
      return await $api<SampleAnalysis>(
        `${getApiBaseUrl()}/v1/spatial/geo/jenis/analyze-sample`,
        { method: "POST", body: formData },
      );
    },

    async createTheme(payload: CreateThemePayload) {
      const { $api } = useNuxtApp();
      const created = await $api<{ kode: string }>(
        `${getApiBaseUrl()}/v1/spatial/geo/jenis`,
        { method: "POST", headers: getAuthHeaders(), body: payload },
      );
      await this.initDataKategori();
      this.setCategory(created.kode);
      return created;
    },

    async submitUpload() {
      const isAnalyze = Object.keys(this.summaryAnalyze).length === 0;
      const kind = isAnalyze ? "analyze" : "execute";
      if (isAnalyze) {
        this.resetMessages();
      } else {
        this.executeResponse = null;
        this.executeError = "";
        this.errorMessage = "";
        this.successMessage = "";
      }

      const { $api } = useNuxtApp();

      if (!this.selectedCategory) {
        this.errorMessage = "Silakan pilih kategori data terlebih dahulu.";
        return;
      }

      if (!this.month || !this.year) {
        this.errorMessage = "Silakan pilih bulan dan tahun.";
        return;
      }

      if (!this.selectedFile || !this.parsedGeoJson) {
        this.errorMessage = "Silakan pilih file GeoJSON yang valid.";
        return;
      }

      const dataFindOneCategory = this.categories.find(
        (category) => category.value === this.selectedCategory,
      );

      if (!dataFindOneCategory) {
        this.errorMessage = "Kategori data tidak ditemukan.";
        return;
      }

      const action = isAnalyze
        ? dataFindOneCategory.endpoints.upload_analyze
        : dataFindOneCategory.endpoints.upload_execute;

      if (!action) {
        const message = isAnalyze
          ? "Endpoint analisis tidak tersedia pada kategori ini."
          : "Endpoint submit analisis tidak tersedia pada kategori ini.";
        if (isAnalyze) this.errorMessage = message;
        else this.executeError = message;
        return;
      }

      const parts = chunkFeatureCollection(this.parsedGeoJson, GEOJSON_FEATURES_PER_PART);
      if (!parts.length) {
        this.errorMessage = "File GeoJSON tidak berisi data Feature.";
        return;
      }

      const groupId = newUploadGroupId();
      const partResults: Array<Record<string, any> | null | undefined> = [];
      this.isUploading = true;
      this.multipartAbort = false;
      this.stopJobPolling();

      try {
        for (let i = 0; i < parts.length; i++) {
          if (this.multipartAbort) {
            const message = isAnalyze
              ? "Analisis dibatalkan."
              : "Penyimpanan dibatalkan. Part yang belum dijalankan tidak dikirim.";
            if (isAnalyze) this.errorMessage = message;
            else this.executeError = message;
            return;
          }

          const partIndex = i + 1;
          const partTotal = parts.length;
          this.multipart = { groupId, kind, partIndex, partTotal };

          const partFile = featureCollectionToFile(
            parts[i]!,
            this.selectedFile.name,
            partIndex,
            partTotal,
          );

          const formData = new FormData();
          formData.append("file", partFile);
          formData.append("kind", kind);
          formData.append("layer", dataFindOneCategory.value);
          formData.append("bulan", String(Number(this.month)));
          formData.append("tahun", String(Number(this.year)));
          formData.append("upload_group_id", groupId);
          formData.append("part_index", String(partIndex));
          formData.append("part_total", String(partTotal));
          // no_preview dari backend = feature_offset + nomor feature di part (nomor baris preview global).
          formData.append("feature_offset", String(partFeatureOffset(partIndex, GEOJSON_FEATURES_PER_PART)));

          const job = await $api<UploadJob>(`${getApiBaseUrl()}/v1/upload-jobs`, {
            method: "POST",
            body: formData,
          });

          const finished = await this.runJobToCompletion(job);
          if (finished.status === "cancelled" || this.multipartAbort) {
            const message = isAnalyze
              ? "Analisis dibatalkan."
              : "Penyimpanan dibatalkan. Part yang belum dijalankan tidak dikirim.";
            if (isAnalyze) this.errorMessage = message;
            else this.executeError = message;
            return;
          }
          if (finished.status !== "succeeded") {
            const message =
              finished.error_message ||
              (isAnalyze ? "Analisis GeoJSON gagal." : "Submit analisis gagal.") +
                ` (part ${partIndex}/${partTotal})`;
            if (isAnalyze) this.errorMessage = message;
            else this.executeError = message;
            return;
          }
          partResults.push(finished.result);
          this.failedRowsJobId = { ...this.failedRowsJobId, [kind]: finished.job_id };
          if (isAnalyze) this.applyAnalyzePart(finished.result, partResults);
        }

        if (isAnalyze) {
          this.summaryAnalyze = mergeAnalyzeResults(partResults);
          if (!this.selectedFile) {
            this.errorMessage =
              "Halaman sempat dimuat ulang, jadi file perlu dipilih ulang sebelum data bisa disimpan.";
          }
        } else {
          this.executeResponse = mergeExecuteResults(partResults);
        }
      } catch (error) {
        const fallback = isAnalyze ? "Analisis GeoJSON gagal." : "Submit analisis gagal.";
        const message = readUploadError(error, fallback);
        if (isAnalyze) this.errorMessage = message;
        else this.executeError = message;
      } finally {
        this.isUploading = false;
        this.isCancellingJob = false;
        this.multipart = null;
        this.multipartAbort = false;
        this.activeJob = null;
        rememberJob(null);
      }
    },

    /** Tempel hasil satu part ke tabel preview & ringkasan aman/gagal langsung (tanpa menunggu semua part). */
    applyAnalyzePart(result: unknown, allResults: Array<Record<string, any> | null | undefined>) {
      if (!isPartAnalyzeResponse(result)) return;
      this.previewAnalysis = indexTablePreview({ ...this.previewAnalysis }, result.data.table_preview);
      const summary = summarizePart(result);
      this.analyzeParts = [...this.analyzeParts.filter((p) => p.part !== summary.part), summary].sort(
        (a, b) => a.part - b.part,
      );
      this.liveAnalyze = mergeAnalyzeResults(allResults);
    },

    /** Poll satu job sampai selesai (dipakai loop part Feature). */
    async runJobToCompletion(job: UploadJob): Promise<UploadJob> {
      const { $api } = useNuxtApp();
      this.activeJob = job;
      this.jobPollErrors = 0;
      rememberJob(job.job_id);
      if (FINISHED_STATUSES.includes(job.status)) return job;

      let current = job;
      while (!FINISHED_STATUSES.includes(current.status)) {
        if (this.multipartAbort) {
          try {
            current = await $api<UploadJob>(
              `${getApiBaseUrl()}/v1/upload-jobs/${current.job_id}/cancel`,
              { method: "POST" },
            );
            this.activeJob = current;
          } catch {
            // 409 = sudah selesai; lanjut baca status akhir.
          }
        }

        await sleep(JOB_POLL_MS);
        try {
          current = await $api<UploadJob>(
            `${getApiBaseUrl()}/v1/upload-jobs/${current.job_id}`,
            { skipServerErrorRedirect: true },
          );
          this.jobPollErrors = 0;
          this.activeJob = current;
        } catch (error) {
          const status = (error as { response?: { status?: number } } | null)?.response
            ?.status;
          this.jobPollErrors += 1;
          if (status === 404 || this.jobPollErrors >= JOB_POLL_MAX_ERRORS) {
            throw new Error(
              readUploadError(
                error,
                "Status proses tidak bisa dibaca. Cek Riwayat Upload untuk melihat hasilnya.",
              ),
            );
          }
        }
      }
      return current;
    },

    trackJob(job: UploadJob) {
      this.activeJob = job;
      this.isUploading = true;
      this.jobPollErrors = 0;
      rememberJob(job.job_id);
      if (FINISHED_STATUSES.includes(job.status)) {
        this.finishJob(job);
        return;
      }
      this.scheduleJobPoll();
    },

    scheduleJobPoll() {
      if (jobPollTimer) clearTimeout(jobPollTimer);
      jobPollTimer = setTimeout(() => this.pollJob(), JOB_POLL_MS);
    },

    stopJobPolling() {
      if (jobPollTimer) clearTimeout(jobPollTimer);
      jobPollTimer = null;
    },

    async pollJob() {
      const jobId = this.activeJob?.job_id;
      if (!jobId) return;
      const { $api } = useNuxtApp();
      try {
        const job = await $api<UploadJob>(
          `${getApiBaseUrl()}/v1/upload-jobs/${jobId}`,
          { skipServerErrorRedirect: true },
        );
        this.jobPollErrors = 0;
        this.activeJob = job;
        if (FINISHED_STATUSES.includes(job.status)) {
          this.finishJob(job);
          return;
        }
      } catch (error) {
        const status = (error as { response?: { status?: number } } | null)
          ?.response?.status;
        this.jobPollErrors += 1;
        if (status === 404 || this.jobPollErrors >= JOB_POLL_MAX_ERRORS) {
          const message = readUploadError(
            error,
            "Status proses tidak bisa dibaca. Cek Riwayat Upload untuk melihat hasilnya.",
          );
          this.abandonJob(message);
          return;
        }
      }
      this.scheduleJobPoll();
    },

    finishJob(job: UploadJob) {
      this.stopJobPolling();
      rememberJob(null);
      this.activeJob = null;
      this.isUploading = false;
      this.isCancellingJob = false;
      this.multipart = null;

      const isAnalyze = job.kind === "analyze";
      if (job.status === "succeeded") {
        if (isAnalyze) {
          this.applyAnalyzePart(job.result, [job.result]);
          this.summaryAnalyze = job.result ? mergeAnalyzeResults([job.result]) : {};
        }
        else this.executeResponse = job.result ?? {};
        if (isAnalyze && !this.selectedFile) {
          this.errorMessage =
            "Halaman sempat dimuat ulang, jadi file perlu dipilih ulang sebelum data bisa disimpan.";
        }
        return;
      }
      if (job.status === "cancelled") {
        this.errorMessage = isAnalyze
          ? "Analisis dibatalkan."
          : "Penyimpanan dibatalkan. Tidak ada data yang disimpan.";
        return;
      }
      const message =
        job.error_message ||
        (isAnalyze ? "Analisis GeoJSON gagal." : "Submit analisis gagal.");
      if (isAnalyze) this.errorMessage = message;
      else this.executeError = message;
    },

    abandonJob(message: string) {
      const isAnalyze = this.activeJob?.kind !== "execute";
      this.stopJobPolling();
      rememberJob(null);
      this.activeJob = null;
      this.isUploading = false;
      this.isCancellingJob = false;
      this.multipart = null;
      if (isAnalyze) this.errorMessage = message;
      else this.executeError = message;
    },

    async cancelJob() {
      this.multipartAbort = true;
      const jobId = this.activeJob?.job_id;
      if (!jobId || this.isCancellingJob) return;
      const { $api } = useNuxtApp();
      this.isCancellingJob = true;
      try {
        const job = await $api<UploadJob>(
          `${getApiBaseUrl()}/v1/upload-jobs/${jobId}/cancel`,
          {
            method: "POST",
          },
        );
        this.activeJob = job;
        // Multipart: loop submitUpload yang menunggu runJobToCompletion akan menutup UI.
        if (!this.multipart && FINISHED_STATUSES.includes(job.status)) this.finishJob(job);
      } catch {
        // 409 = proses sudah selesai lebih dulu; hasil akhirnya tetap diambil oleh polling.
        this.isCancellingJob = false;
      }
    },

    /** Lanjutkan memantau job setelah halaman dibuka lagi (pindah halaman atau dimuat ulang). */
    async resumeActiveJob() {
      if (this.activeJob) {
        if (!jobPollTimer) this.scheduleJobPoll();
        return;
      }
      const { $api } = useNuxtApp();
      const baseUrl = getApiBaseUrl();
      const savedId = import.meta.client
        ? sessionStorage.getItem(JOB_STORAGE_KEY)
        : null;
      try {
        let job: UploadJob | null = null;
        if (savedId) {
          job = await $api<UploadJob>(
            `${baseUrl}/v1/upload-jobs/${savedId}`,
            { skipServerErrorRedirect: true },
          ).catch(() => null);
        }
        if (!job) {
          const active = await $api<UploadJob[]>(
            `${baseUrl}/v1/upload-jobs/active`,
          );
          job = active.at(-1) ?? null;
        }
        if (!job) {
          rememberJob(null);
          return;
        }
        if (!this.selectedCategory) this.selectedCategory = job.layer;
        if (!this.month) this.month = String(job.bulan).padStart(2, "0");
        if (!this.year) this.year = String(job.tahun);
        this.trackJob(job);
      } catch {
        // Pengguna tanpa izin upload atau server tidak terjangkau: halaman tetap bisa dipakai.
      }
    },
  },
});
