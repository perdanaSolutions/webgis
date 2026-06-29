import { defineStore } from "pinia";

type FeatureProperties = Record<string, string | number | null | undefined>;

type GeoJSONFeature = GeoJSON.Feature<GeoJSON.Geometry, FeatureProperties>;

type Filters = {
  pt: string;
  estate: string;
  afdeling: string;
  blok: string;
  tahunTanam: string;
  statusTanam: string;
  jenisBibit: string;
};

type OptionItem = {
  label: string;
  value: string;
};

type FilterOptions = {
  pt: OptionItem[];
  estate: OptionItem[];
  afdeling: OptionItem[];
  blok: OptionItem[];
  tahunTanam: OptionItem[];
  statusTanam: OptionItem[];
  jenisBibit: OptionItem[];
};

type Summary = {
  totalBlok: number;
  totalLuasTanam: number;
  totalPokok: number;
  totalJalan: number;
  totalDrainase: number;
  totalJembatan: number;
};

const API_BASE_URL = "http://localhost:4000";

function toQuery(filters: Filters) {
  const searchParams = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value) searchParams.set(key, value);
  });

  return searchParams.toString();
}

export const useMapStore = defineStore("map", {
  state: () => ({
    rawFeatures: [] as GeoJSONFeature[],
    filters: {
      pt: "",
      estate: "",
      afdeling: "",
      blok: "",
      tahunTanam: "",
      statusTanam: "",
      jenisBibit: "",
    } as Filters,
    options: {
      pt: [],
      estate: [],
      afdeling: [],
      blok: [],
      tahunTanam: [],
      statusTanam: [],
      jenisBibit: [],
    } as FilterOptions,
    summaryData: {
      totalBlok: 0,
      totalLuasTanam: 0,
      totalPokok: 0,
      totalJalan: 0,
      totalDrainase: 0,
      totalJembatan: 0,
    } as Summary,
    isLoaded: false,
    isLoading: false,
  }),

  getters: {
    filteredFeatures(state): GeoJSONFeature[] {
      return state.rawFeatures;
    },

    filteredGeoJSON(): GeoJSON.FeatureCollection {
      return {
        type: "FeatureCollection",
        features: this.filteredFeatures,
      };
    },

    filterOptions(state): FilterOptions {
      return state.options;
    },

    summary(state): Summary {
      return state.summaryData;
    },
  },

  actions: {
    async fetchFilters() {
      const query = toQuery(this.filters);
      const url = query
        ? `${API_BASE_URL}/filters?${query}`
        : `${API_BASE_URL}/filters`;

      const response = await $fetch<{
        pt: string[];
        estate: string[];
        afdeling: string[];
        blok: string[];
        tahunTanam: string[];
        statusTanam: string[];
        jenisBibit: string[];
      }>(url);

      this.options = {
        pt: response.pt.map((value) => ({ label: value, value })),
        estate: response.estate.map((value) => ({ label: value, value })),
        afdeling: response.afdeling.map((value) => ({ label: value, value })),
        blok: response.blok.map((value) => ({ label: value, value })),
        tahunTanam: response.tahunTanam.map((value) => ({
          label: value,
          value,
        })),
        statusTanam: response.statusTanam.map((value) => ({
          label: value,
          value,
        })),
        jenisBibit: response.jenisBibit.map((value) => ({
          label: value,
          value,
        })),
      };
    },

    async fetchFeatures() {
      const query = toQuery(this.filters);
      const url = query
        ? `${API_BASE_URL}/features?${query}`
        : `${API_BASE_URL}/features`;

      const response = await $fetch<GeoJSON.FeatureCollection>(url);
      this.rawFeatures = (response.features ?? []) as GeoJSONFeature[];
    },

    async fetchSummary() {
      const query = toQuery(this.filters);
      const url = query
        ? `${API_BASE_URL}/summary?${query}`
        : `${API_BASE_URL}/summary`;

      const response = await $fetch<Summary>(url);
      this.summaryData = response;
    },

    async refreshData() {
      this.isLoading = true;
      try {
        await Promise.all([
          this.fetchFilters(),
          this.fetchFeatures(),
          this.fetchSummary(),
        ]);
        this.isLoaded = true;
      } finally {
        this.isLoading = false;
      }
    },

    async loadGeoJSONData() {
      if (this.isLoaded) return;
      await this.refreshData();
    },

    async setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
      this.filters[key] = value;

      if (key === "pt") {
        this.filters.estate = "";
        this.filters.afdeling = "";
        this.filters.blok = "";
      }

      if (key === "estate") {
        this.filters.afdeling = "";
        this.filters.blok = "";
      }

      if (key === "afdeling") this.filters.blok = "";

      await this.refreshData();
    },

    async applyFilters(nextFilters: Filters) {
      this.filters = {
        pt: nextFilters.pt || "",
        estate: nextFilters.estate || "",
        afdeling: nextFilters.afdeling || "",
        blok: nextFilters.blok || "",
        tahunTanam: nextFilters.tahunTanam || "",
        statusTanam: nextFilters.statusTanam || "",
        jenisBibit: nextFilters.jenisBibit || "",
      };

      if (!this.filters.pt) {
        this.filters.estate = "";
        this.filters.afdeling = "";
        this.filters.blok = "";
      }

      if (!this.filters.estate) {
        this.filters.afdeling = "";
        this.filters.blok = "";
      }

      if (!this.filters.afdeling) this.filters.blok = "";

      await this.refreshData();
    },

    async resetFilters() {
      this.filters = {
        pt: "",
        estate: "",
        afdeling: "",
        blok: "",
        tahunTanam: "",
        statusTanam: "",
        jenisBibit: "",
      };

      await this.refreshData();
    },
  },
});
