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
  return config.public.apiBaseUrl || "/api";
}

export const useDocumentUploadStore = defineStore("document-upload", {
  state: () => ({
    categories: UPLOAD_CATEGORIES as UploadCategory[],
    selectedCategory: "" as string,
    selectedFile: null as File | null,
    parsedGeoJson: null as GeoJsonCollection | null,
    previewRows: [] as GeoJsonFeature[],
    errorMessage: "" as string,
    successMessage: "" as string,
    isParsing: false,
    isUploading: false,
    uploadProgress: 0,
  }),

  getters: {
    hasPreview(state): boolean {
      return Boolean(state.parsedGeoJson && state.previewRows.length > 0);
    },
    featureCount(state): number {
      return state.parsedGeoJson?.features?.length ?? 0;
    },
  },

  actions: {
    resetMessages() {
      this.errorMessage = "";
      this.successMessage = "";
    },

    resetSelection() {
      this.selectedFile = null;
      this.parsedGeoJson = null;
      this.previewRows = [];
      this.uploadProgress = 0;
      this.resetMessages();
    },

    setCategory(category: string) {
      this.selectedCategory = category;
      this.resetMessages();
    },

    async setFile(file: File | null) {
      this.resetMessages();
      this.selectedFile = file;
      this.parsedGeoJson = null;
      this.previewRows = [];

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
        this.previewRows = json.features.slice(0, 10) as GeoJsonFeature[];
        this.uploadProgress = 100;
      } catch (error) {
        this.parsedGeoJson = null;
        this.previewRows = [];
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
      this.resetMessages();

      if (!this.selectedCategory) {
        this.errorMessage = "Silakan pilih kategori data terlebih dahulu.";
        return;
      }

      if (!this.selectedFile || !this.parsedGeoJson) {
        this.errorMessage = "Silakan pilih file GeoJSON yang valid.";
        return;
      }

      this.isUploading = true;
      this.uploadProgress = 15;

      try {
        const apiBaseUrl = getApiBaseUrl();
        const formData = new FormData();
        formData.append("category", this.selectedCategory);
        formData.append("file", this.selectedFile);
        formData.append("feature_count", String(this.featureCount));

        this.uploadProgress = 45;

        await $fetch(`${apiBaseUrl}/spatial/upload`, {
          method: "POST",
          body: formData,
        });

        this.uploadProgress = 100;
        this.successMessage = "Upload GeoJSON berhasil diproses.";
      } catch (error) {
        this.errorMessage =
          error instanceof Error ? error.message : "Upload GeoJSON gagal.";
      } finally {
        this.isUploading = false;
      }
    },
  },
});
