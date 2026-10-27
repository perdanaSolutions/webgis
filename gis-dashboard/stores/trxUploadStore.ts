import { defineStore } from "pinia";
import { newUploadGroupId } from "~/utils/uploadGroupId";
import {
  mergeAnalyzeResults,
  mergeExecuteResults,
  indexTablePreview,
  isPartAnalyzeResponse,
  summarizePart,
  partToLegacyBody,
  type PartAnalyzeSummary,
  type PreviewAnalysisRow,
} from "~/utils/geojsonFeatureParts";
import { getErrorMessage } from "~/utils/getErrorMessage";
import { downloadExcelTemplate, downloadJsonTemplate, readExcelPreview } from "~/utils/trxExcelFile";
import {
  TRX_ROWS_PER_PART,
  chunkTrxRows,
  partRowOffset,
  rowsToExcelFile,
} from "~/utils/trxExcelParts";
import {
  buildJsonImport,
  collectHeaders,
  displayRows,
  fileModeFromName,
  findTrxKind,
  type JsonScalar,
  type TrxFileMode,
  type TrxKindId,
} from "~/utils/trxUpload";
import type { MultipartUploadProgress, UploadJob, UploadJobStatus } from "~/stores/documentUploadStore";

type JsonBody = {
  sumber: string;
  data: Record<string, JsonScalar>[];
};

type HeldPreview = {
  mode: TrxFileMode;
  headers: string[];
  rows: Record<string, string>[];
  jsonBody: JsonBody | null;
  sheetName: string;
};

let heldPreview: HeldPreview | null = null;

const JOB_STORAGE_KEY = "trx-upload-job-id";
const JOB_POLL_MS = 1500;
const JOB_POLL_MAX_ERRORS = 5;
const FINISHED_STATUSES: UploadJobStatus[] = ["succeeded", "failed", "cancelled"];

let jobPollTimer: ReturnType<typeof setTimeout> | null = null;

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython || "/api";
}

function readUploadError(error: unknown, fallback: string) {
  const data = (error as { data?: unknown } | null)?.data;
  if (!data) return error instanceof Error && error.message ? error.message : fallback;
  try {
    return getErrorMessage(error, fallback);
  }
  catch {
    return fallback;
  }
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function rememberJob(jobId: string | null) {
  if (!import.meta.client) return;
  if (jobId) sessionStorage.setItem(JOB_STORAGE_KEY, jobId);
  else sessionStorage.removeItem(JOB_STORAGE_KEY);
}

export const useTrxUploadStore = defineStore("trx-upload", {
  state: () => ({
    kindId: "areal-statement" as TrxKindId,
    selectedFile: null as File | null,
    fileMode: null as TrxFileMode | null,
    headers: [] as string[],
    rowCount: 0,
    sheetName: "",
    previewToken: 0,
    errorMessage: "",
    isReading: false,
    isUploading: false,
    analysis: null as Record<string, any> | null,
    importResult: null as Record<string, any> | null,
    activeJob: null as UploadJob | null,
    isCancellingJob: false,
    jobPollErrors: 0,
    multipart: null as MultipartUploadProgress | null,
    multipartAbort: false,
    /** job_id terakhir per tahap (analyze/execute), untuk unduhan Excel data gagal semua part. */
    failedRowsJobId: { analyze: null, execute: null } as Record<"analyze" | "execute", string | null>,
    previewAnalysis: {} as Record<number, PreviewAnalysisRow>,
    analyzeParts: [] as PartAnalyzeSummary[],
    liveAnalyze: null as Record<string, any> | null,
  }),

  getters: {
    kind(state) {
      return findTrxKind(state.kindId);
    },
    previewRows(state): Record<string, string>[] {
      void state.previewToken;
      return heldPreview?.rows ?? [];
    },
    isAnalyzing(state): boolean {
      return state.isUploading && !state.analysis && state.multipart?.kind !== "execute";
    },
    isImporting(state): boolean {
      return state.isUploading && Boolean(state.analysis) && state.multipart?.kind === "execute";
    },
    isBusy(state): boolean {
      return state.isReading || state.isUploading;
    },
  },

  actions: {
    clearResult() {
      this.errorMessage = "";
      this.failedRowsJobId = { analyze: null, execute: null };
      this.analysis = null;
      this.importResult = null;
      this.previewAnalysis = {};
      this.analyzeParts = [];
      this.liveAnalyze = null;
    },

    resetFile() {
      heldPreview = null;
      this.selectedFile = null;
      this.fileMode = null;
      this.headers = [];
      this.rowCount = 0;
      this.sheetName = "";
      this.previewToken += 1;
      this.stopJobPolling();
      this.activeJob = null;
      this.multipart = null;
      this.multipartAbort = false;
      rememberJob(null);
      this.clearResult();
    },

    setKind(kindId: TrxKindId) {
      if (this.kindId === kindId) return;
      this.kindId = kindId;
      this.resetFile();
    },

    async downloadExcel() {
      try {
        await downloadExcelTemplate(this.kind);
      }
      catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "Template Excel gagal diunduh.";
      }
    },

    downloadJson() {
      downloadJsonTemplate(this.kind);
    },

    async setFile(file: File | null) {
      this.clearResult();
      heldPreview = null;
      this.selectedFile = file;
      this.fileMode = null;
      this.headers = [];
      this.rowCount = 0;
      this.sheetName = "";
      this.previewToken += 1;
      if (!file) return;

      const mode = fileModeFromName(file.name);
      if (!mode) {
        this.selectedFile = null;
        this.errorMessage = "File harus berformat .xlsx, .xls, atau .json.";
        return;
      }

      this.isReading = true;
      try {
        if (mode === "excel") {
          const preview = await readExcelPreview(file);
          heldPreview = {
            mode,
            headers: preview.headers,
            rows: preview.rows,
            jsonBody: null,
            sheetName: preview.sheetName,
          };
          this.sheetName = preview.sheetName;
          this.headers = preview.headers;
          this.rowCount = preview.rows.length;
        }
        else {
          const parsed = JSON.parse(await file.text()) as unknown;
          const body = buildJsonImport(parsed, file.name);
          const headers = collectHeaders(body.data, this.kind.columns);
          heldPreview = {
            mode,
            headers,
            rows: displayRows(body.data, headers),
            jsonBody: body,
            sheetName: "",
          };
          this.headers = headers;
          this.rowCount = body.data.length;
        }
        this.fileMode = mode;
        this.previewToken += 1;
      }
      catch (error) {
        heldPreview = null;
        this.selectedFile = null;
        this.previewToken += 1;
        this.errorMessage = error instanceof SyntaxError
          ? "File JSON tidak valid."
          : error instanceof Error
            ? error.message
            : "File tidak bisa dibaca.";
      }
      finally {
        this.isReading = false;
      }
    },

    applyAnalyzePart(result: unknown, allResults: Array<Record<string, any> | null | undefined>) {
      if (!isPartAnalyzeResponse(result)) return;
      this.previewAnalysis = indexTablePreview({ ...this.previewAnalysis }, result.data.table_preview);
      const summary = summarizePart(result);
      this.analyzeParts = [...this.analyzeParts.filter((p) => p.part !== summary.part), summary].sort(
        (a, b) => a.part - b.part,
      );
      this.liveAnalyze = mergeAnalyzeResults(allResults);
    },

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
          }
          catch {
            // 409 = sudah selesai
          }
        }

        await sleep(JOB_POLL_MS);
        try {
          current = await $api<UploadJob>(`${getApiBaseUrl()}/v1/upload-jobs/${current.job_id}`);
          this.jobPollErrors = 0;
          this.activeJob = current;
        }
        catch (error) {
          const status = (error as { response?: { status?: number } } | null)?.response?.status;
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

    async submitMultipart(isAnalyze: boolean) {
      if (this.fileMode !== "excel" || !this.selectedFile || !heldPreview?.rows.length) {
        this.errorMessage = "Pilih file Excel yang berisi data terlebih dahulu.";
        return;
      }
      if (!isAnalyze && !this.analysis) {
        this.errorMessage = "Analisis file terlebih dahulu sebelum mengimpor.";
        return;
      }

      const kind = isAnalyze ? "analyze" : "execute";
      const parts = chunkTrxRows(heldPreview.headers, heldPreview.rows, TRX_ROWS_PER_PART);
      if (!parts.length) {
        this.errorMessage = "File tidak berisi baris data.";
        return;
      }

      const groupId = newUploadGroupId();
      const partResults: Array<Record<string, any> | null | undefined> = [];
      this.isUploading = true;
      this.multipartAbort = false;
      this.errorMessage = "";
      if (isAnalyze) {
        this.analysis = null;
        this.importResult = null;
        this.previewAnalysis = {};
        this.analyzeParts = [];
        this.liveAnalyze = null;
      }
      else {
        this.importResult = null;
      }
      this.stopJobPolling();

      const { $api } = useNuxtApp();
      const layer = this.kind.uploadJobLayer;

      try {
        for (let i = 0; i < parts.length; i++) {
          if (this.multipartAbort) {
            this.errorMessage = isAnalyze
              ? "Analisis dibatalkan."
              : "Import dibatalkan. Part yang belum dijalankan tidak dikirim.";
            return;
          }

          const partIndex = i + 1;
          const partTotal = parts.length;
          this.multipart = { groupId, kind, partIndex, partTotal };

          const partFile = await rowsToExcelFile(
            parts[i]!,
            this.selectedFile.name,
            partIndex,
            partTotal,
          );

          const formData = new FormData();
          formData.append("file", partFile);
          formData.append("kind", kind);
          formData.append("layer", layer);
          formData.append("bulan", "1");
          formData.append("tahun", "2000");
          formData.append("upload_group_id", groupId);
          formData.append("part_index", String(partIndex));
          formData.append("part_total", String(partTotal));
          formData.append("feature_offset", String(partRowOffset(partIndex, TRX_ROWS_PER_PART)));

          const job = await $api<UploadJob>(`${getApiBaseUrl()}/v1/upload-jobs`, {
            method: "POST",
            body: formData,
          });

          const finished = await this.runJobToCompletion(job);
          if (finished.status === "cancelled" || this.multipartAbort) {
            this.errorMessage = isAnalyze ? "Analisis dibatalkan." : "Import dibatalkan.";
            return;
          }
          if (finished.status !== "succeeded") {
            this.errorMessage =
              finished.error_message ||
              (isAnalyze ? "Analisis Excel gagal." : "Import Excel gagal.") +
                ` (part ${partIndex}/${partTotal})`;
            return;
          }
          partResults.push(finished.result);
          this.failedRowsJobId = { ...this.failedRowsJobId, [kind]: finished.job_id };
          if (isAnalyze) this.applyAnalyzePart(finished.result, partResults);
        }

        if (isAnalyze) {
          this.analysis = mergeAnalyzeResults(partResults);
        }
        else {
          this.importResult = mergeExecuteResults(partResults);
        }
      }
      catch (error) {
        this.errorMessage = readUploadError(
          error,
          isAnalyze ? "Analisis Excel gagal." : "Import Excel gagal.",
        );
      }
      finally {
        this.isUploading = false;
        this.isCancellingJob = false;
        this.multipart = null;
        this.multipartAbort = false;
        this.activeJob = null;
        rememberJob(null);
      }
    },

    async analyze() {
      await this.submitMultipart(true);
    },

    async importFile() {
      if (this.fileMode === "json") {
        await this.importJsonDirect();
        return;
      }
      await this.submitMultipart(false);
    },

    async importJsonDirect() {
      if (!this.selectedFile || this.fileMode !== "json") {
        this.errorMessage = "Pilih file JSON terlebih dahulu.";
        return;
      }
      const body = heldPreview?.jsonBody;
      if (!body) {
        this.errorMessage = "Isi JSON tidak terbaca. Pilih ulang file.";
        return;
      }
      this.errorMessage = "";
      this.isUploading = true;
      const { $api } = useNuxtApp();
      try {
        this.importResult = await $api<Record<string, any>>(
          `${getApiBaseUrl()}${this.kind.endpoints.json}`,
          { method: "POST", body },
        );
      }
      catch (error) {
        this.importResult = null;
        this.errorMessage = readUploadError(error, "Import data transaksi gagal.");
      }
      finally {
        this.isUploading = false;
      }
    },

    stopJobPolling() {
      if (jobPollTimer) clearTimeout(jobPollTimer);
      jobPollTimer = null;
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
          { method: "POST" },
        );
        this.activeJob = job;
      }
      catch {
        this.isCancellingJob = false;
      }
    },

    async resumeActiveJob() {
      if (this.activeJob) return;
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
          job = active.find((j) => j.layer === this.kind.uploadJobLayer) ?? active[0] ?? null;
        }
        if (!job || FINISHED_STATUSES.includes(job.status)) return;
        this.isUploading = true;
        const finished = await this.runJobToCompletion(job);
        if (finished.status === "succeeded" && finished.result) {
          if (finished.kind === "analyze") {
            this.applyAnalyzePart(finished.result, [finished.result]);
            this.analysis = isPartAnalyzeResponse(finished.result)
              ? partToLegacyBody(finished.result)
              : (finished.result as Record<string, any>);
          }
          else {
            this.importResult = finished.result;
          }
        }
      }
      catch {
        // abaikan; pengguna bisa unggah ulang
      }
      finally {
        this.isUploading = false;
        this.activeJob = null;
        rememberJob(null);
      }
    },
  },
});
