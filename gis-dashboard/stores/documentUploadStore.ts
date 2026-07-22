import { defineStore } from "pinia";

type UploadCategory = {
  value: string;
  label: string;
  description: string;
};

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

const UPLOAD_CATEGORIES: UploadCategory[] = [
  {
    value: "blok",
    label: "Blok",
    description:
      "Mencakup informasi spasial dari level Area hingga tingkat Blok.",
  },
  {
    value: "tph",
    label: "TPH (Tempat Pengumpulan Hasil)",
    description: "Data titik/lokasi tempat pengumpulan hasil panen.",
  },
  {
    value: "pokok_sawit",
    label: "Pokok Sawit",
    description: "Data sebaran titik atau area pokok tanaman sawit.",
  },
  {
    value: "landuse",
    label: "Landuse",
    description: "Data penggunaan lahan (land use).",
  },
  {
    value: "jalan",
    label: "Jalan",
    description: "Data jaringan jalan kebun dan akses pendukung.",
  },
  {
    value: "slope",
    label: "Slope (Kemiringan Lereng)",
    description: "Data kemiringan lereng untuk analisa topografi.",
  },
  {
    value: "drainase",
    label: "Drainase",
    description: "Data saluran drainase dan aliran air.",
  },
  {
    value: "jembatan",
    label: "Jembatan",
    description: "Data titik/segmen infrastruktur jembatan.",
  },
];

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython || "/api";
}

export const useDocumentUploadStore = defineStore("document-upload", {
  state: () => ({
    categories: UPLOAD_CATEGORIES as UploadCategory[],
    selectedCategory: "" as string,
    month: "" as string,
    year: "" as string,
    selectedFile: null as File | null,
    parsedGeoJson: null as GeoJsonCollection | null,
    allPreviewRows: [] as GeoJsonFeature[],
    errorMessage: "" as string,
    successMessage: "" as string,
    summaryAnalyze: {} as Record<string, any>,
    isParsing: false,
    isUploading: false,
    uploadProgress: 0,
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

    async submitUpload() {
      if (Object.keys(this.summaryAnalyze).length === 0) {
        this.resetMessages();
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

      // const apiBaseUrl = getApiBaseUrl();
      // console.log("Selected Category :", this.selectedCategory);
      // console.log("base url :", apiBaseUrl);

      this.isUploading = true;
      this.uploadProgress = 15;

      try {
        const apiBaseUrl = getApiBaseUrl();
        const formData = new FormData();

        const isAnalyze = Object.keys(this.summaryAnalyze).length === 0;
        const actionType = isAnalyze ? "analyze" : "execute";

        // 2. Mapping base URL untuk setiap kategori
        const urlMapping: Record<string, string> = {
          blok: `/v1/spatial/blok-geometry/upload-${actionType}`,
          tph: `/v1/spatial/tph/upload-${actionType}`,
          pokok_sawit: `/v1/spatial/sawit/spatial/sawit/${isAnalyze ? "analyze" : "upload"}`,
          landuse: `/v1/spatial/landuse/${isAnalyze ? "analyze" : "upload"}`,
          jalan: `/v1/spatial/jalan/${isAnalyze ? "analyze" : "upload"}`,
          slope: `/v1/spatial/slope/${isAnalyze ? "analyze" : "upload"}`,
          drainase: `/v1/spatial/drainase/${isAnalyze ? "analyze" : "upload"}`,
          jembatan: `/v1/spatial/jembatan/${isAnalyze ? "analyze" : "upload"}`,
        };

        // 3. Ambil URL berdasarkan kategori yang dipilih (berikan fallback string kosong jika tidak cocok)
        const urlUploadByCategory = urlMapping[this.selectedCategory] || "";

        formData.append("file", this.selectedFile);
        // formData.append("feature_count", String(this.featureCount));

        this.uploadProgress = 45;

        var response = await $api(
          `${apiBaseUrl}${urlUploadByCategory}?bulan=${this.month}&tahun=${this.year}`,
          {
            method: "POST",
            body: formData,
          },
        );

        this.uploadProgress = 100;
        if (Object.keys(this.summaryAnalyze).length > 0) {
          this.successMessage = "Upload GeoJSON berhasil diproses.";
          this.summaryAnalyze = {};
          this.selectedFile = null;
          this.parsedGeoJson = null;
          this.selectedCategory = "";
          this.month = "";
          this.year = "";
        } else {
          this.summaryAnalyze = response as any;
        }
      } catch (error) {
        this.errorMessage =
          error instanceof Error ? error.message : "Upload GeoJSON gagal.";
      } finally {
        this.isUploading = false;
      }
    },
  },
});
