import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

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

export type UploadJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type UploadJob = {
  job_id: string;
  status: UploadJobStatus;
  kind: "analyze" | "execute";
  layer: string;
  bulan: number;
  tahun: number;
  filename: string | null;
  stage: string | null;
  message: string | null;
  current: number | null;
  total: number | null;
  elapsed_seconds: number;
  queue_ahead: number | null;
  cancel_requested: boolean;
  error_message: string | null;
  batch_id: string | null;
  result?: Record<string, any> | null;
};

const JOB_STORAGE_KEY = "document-upload-job-id";
const JOB_POLL_MS = 1500;
const JOB_POLL_MAX_ERRORS = 5;
const FINISHED_STATUSES: UploadJobStatus[] = ["succeeded", "failed", "cancelled"];

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

type GeoJsonFeature = GeoJSON.Feature<
  GeoJSON.Geometry,
  Record<string, string | number | boolean | null | undefined>
>;

type GeoJsonCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, string | number | boolean | null | undefined>
>;

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
      this.successMessage = "";
      this.summaryAnalyze = {};
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

      this.isUploading = true;

      try {
        const formData = new FormData();
        formData.append("file", this.selectedFile);
        formData.append("kind", isAnalyze ? "analyze" : "execute");
        formData.append("layer", dataFindOneCategory.value);
        formData.append("bulan", String(Number(this.month)));
        formData.append("tahun", String(Number(this.year)));

        // Server membalas 202 begitu file tersimpan di antrian; prosesnya dipantau lewat polling.
        const job = await $api<UploadJob>(`${getApiBaseUrl()}/v1/upload-jobs`, {
          method: "POST",
          body: formData,
        });
        this.trackJob(job);
      } catch (error) {
        const fallback = isAnalyze ? "Analisis GeoJSON gagal." : "Submit analisis gagal.";
        const message = readUploadError(error, fallback);
        if (isAnalyze) this.errorMessage = message;
        else this.executeError = message;
        this.isUploading = false;
      }
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
        const job = await $api<UploadJob>(`${getApiBaseUrl()}/v1/upload-jobs/${jobId}`);
        this.jobPollErrors = 0;
        this.activeJob = job;
        if (FINISHED_STATUSES.includes(job.status)) {
          this.finishJob(job);
          return;
        }
      } catch (error) {
        const status = (error as { response?: { status?: number } } | null)?.response?.status;
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

      const isAnalyze = job.kind === "analyze";
      if (job.status === "succeeded") {
        if (isAnalyze) this.summaryAnalyze = job.result ?? {};
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
      const message = job.error_message || (isAnalyze ? "Analisis GeoJSON gagal." : "Submit analisis gagal.");
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
      if (isAnalyze) this.errorMessage = message;
      else this.executeError = message;
    },

    async cancelJob() {
      const jobId = this.activeJob?.job_id;
      if (!jobId || this.isCancellingJob) return;
      const { $api } = useNuxtApp();
      this.isCancellingJob = true;
      try {
        const job = await $api<UploadJob>(`${getApiBaseUrl()}/v1/upload-jobs/${jobId}/cancel`, {
          method: "POST",
        });
        this.activeJob = job;
        if (FINISHED_STATUSES.includes(job.status)) this.finishJob(job);
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
      const savedId = import.meta.client ? sessionStorage.getItem(JOB_STORAGE_KEY) : null;
      try {
        let job: UploadJob | null = null;
        if (savedId) {
          job = await $api<UploadJob>(`${baseUrl}/v1/upload-jobs/${savedId}`).catch(() => null);
        }
        if (!job) {
          const active = await $api<UploadJob[]>(`${baseUrl}/v1/upload-jobs/active`);
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
