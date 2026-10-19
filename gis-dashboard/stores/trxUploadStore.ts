import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import { downloadExcelTemplate, downloadJsonTemplate, readExcelPreview } from "~/utils/trxExcelFile";
import {
  TRX_UPLOAD_MAX_BYTES,
  buildJsonImport,
  collectHeaders,
  displayRows,
  fileModeFromName,
  findTrxKind,
  type JsonScalar,
  type TrxFileMode,
  type TrxKindId,
} from "~/utils/trxUpload";

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
    isAnalyzing: false,
    isImporting: false,
    analysis: null as Record<string, any> | null,
    importResult: null as Record<string, any> | null,
  }),

  getters: {
    kind(state) {
      return findTrxKind(state.kindId);
    },
    previewRows(state): Record<string, string>[] {
      void state.previewToken;
      return heldPreview?.rows ?? [];
    },
    isBusy(state): boolean {
      return state.isReading || state.isAnalyzing || state.isImporting;
    },
  },

  actions: {
    clearResult() {
      this.errorMessage = "";
      this.analysis = null;
      this.importResult = null;
    },

    resetFile() {
      heldPreview = null;
      this.selectedFile = null;
      this.fileMode = null;
      this.headers = [];
      this.rowCount = 0;
      this.sheetName = "";
      this.previewToken += 1;
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
      if (file.size > TRX_UPLOAD_MAX_BYTES) {
        this.selectedFile = null;
        this.errorMessage = "Ukuran file melebihi 50 MB.";
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

    async analyze() {
      if (this.fileMode !== "excel" || !this.selectedFile) {
        this.errorMessage = "Pilih file Excel terlebih dahulu.";
        return;
      }
      this.errorMessage = "";
      this.importResult = null;
      this.isAnalyzing = true;
      const { $api } = useNuxtApp();
      try {
        const formData = new FormData();
        formData.append("file", this.selectedFile);
        this.analysis = await $api<Record<string, any>>(
          `${getApiBaseUrl()}${this.kind.endpoints.analyze}`,
          { method: "POST", body: formData },
        );
      }
      catch (error) {
        this.analysis = null;
        this.errorMessage = readUploadError(error, "Analisis Excel gagal.");
      }
      finally {
        this.isAnalyzing = false;
      }
    },

    async importFile() {
      if (!this.selectedFile || !this.fileMode) {
        this.errorMessage = "Pilih file terlebih dahulu.";
        return;
      }
      if (this.fileMode === "excel" && !this.analysis) {
        this.errorMessage = "Analisis file terlebih dahulu sebelum mengimpor.";
        return;
      }
      this.errorMessage = "";
      this.isImporting = true;
      const { $api } = useNuxtApp();
      try {
        if (this.fileMode === "excel") {
          const formData = new FormData();
          formData.append("file", this.selectedFile);
          this.importResult = await $api<Record<string, any>>(
            `${getApiBaseUrl()}${this.kind.endpoints.excel}`,
            { method: "POST", body: formData },
          );
        }
        else {
          const body = heldPreview?.jsonBody;
          if (!body) {
            this.errorMessage = "Isi JSON tidak terbaca. Pilih ulang file.";
            return;
          }
          this.importResult = await $api<Record<string, any>>(
            `${getApiBaseUrl()}${this.kind.endpoints.json}`,
            { method: "POST", body },
          );
        }
      }
      catch (error) {
        this.importResult = null;
        this.errorMessage = readUploadError(error, "Import data transaksi gagal.");
      }
      finally {
        this.isImporting = false;
      }
    },
  },
});
