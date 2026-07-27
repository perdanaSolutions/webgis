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

      var dataFindOneCategory = this.categories.find(
        (category) => category.value === this.selectedCategory,
      );

      // console.log(
      //   `Data Find One Category : ${JSON.stringify(dataFindOneCategory)}`,
      // );
      if (dataFindOneCategory) {
        // Data DITEMUKAN
        this.isUploading = true;
        this.uploadProgress = 15;

        try {
          const apiBaseUrl = getApiBaseUrl();
          const formData = new FormData();

          const isAnalyze = Object.keys(this.summaryAnalyze).length === 0;
          const action = isAnalyze
            ? (dataFindOneCategory.endpoints.upload_analyze ?? "/")
            : (dataFindOneCategory.endpoints.upload_execute ?? "/");
          const urlUploadByCategory = `/v1/spatial${action}`;

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
      }
    },
  },
});
