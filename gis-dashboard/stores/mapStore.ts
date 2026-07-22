import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

type OptionItem = {
  label: string;
  value: string;
};

type AreaItem = {
  id?: string | number;
  area_id?: string;
  kode_area?: string;
  nama_area?: string;
  nama?: string;
};

type PtItem = {
  id?: string | number;
  kode_pt?: string;
  kode?: string;
  nama_pt?: string;
  nama_perusahaan?: string;
  nama?: string;
};

type EstateItem = {
  id?: string | number;
  kode_est?: string;
  kode?: string;
  nama_estate?: string;
  nama?: string;
};

type AfdelingItem = {
  id?: string | number;
  kode_afd?: string;
  kode_afdeling?: string;
  kode?: string;
  nama_afdeling?: string;
  nama?: string;
};

type BlokItem = {
  id?: string | number;
  blok_id?: string;
  kode_blok?: string;
  kode?: string;
  nama_blok?: string;
  nama?: string;
};

type MapFilters = {
  area?: string;
  pt: string;
  estate: string;
  afdeling: string;
  blok: string;
};

type MapSummary = {
  totalBlok: number;
  totalLuasTanam: number;
  totalPokok: number;
  totalJalan: number;
  totalDrainase: number;
  totalJembatan: number;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const useMapStore = defineStore("map", () => {
  const { $api } = useNuxtApp();

  const areaOptions = ref<OptionItem[]>([]);
  const ptOptions = ref<OptionItem[]>([]);
  const estateOptions = ref<OptionItem[]>([]);
  const afdelingOptions = ref<OptionItem[]>([]);
  const blokOptions = ref<OptionItem[]>([]);

  const selectedArea = ref("");
  const selectedPt = ref("");
  const selectedEstate = ref("");
  const selectedAfdeling = ref("");
  const selectedBlok = ref("");

  const loadingArea = ref(false);
  const loadingPt = ref(false);
  const loadingEstate = ref(false);
  const loadingAfdeling = ref(false);
  const loadingBlok = ref(false);
  const errorMessage = ref("");

  const hasArea = computed(() => areaOptions.value.length > 0);
  const hasPt = computed(() => ptOptions.value.length > 0);
  const hasEstate = computed(() => estateOptions.value.length > 0);
  const hasAfdeling = computed(() => afdelingOptions.value.length > 0);
  const hasBlok = computed(() => blokOptions.value.length > 0);

  function clearError() {
    errorMessage.value = "";
  }

  function getAuthHeaders() {
    return {
      accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  function normalizeText(value: unknown): string {
    return String(value ?? "").trim();
  }

  function mapAreaToOption(item: AreaItem): OptionItem {
    const value = normalizeText(
      item.area_id ?? item.kode_area ?? item.id ?? "",
    );
    const label = normalizeText(item.nama_area ?? item.nama ?? value);
    return { label, value };
  }

  function mapPtToOption(item: PtItem): OptionItem {
    const value = normalizeText(item.kode_pt ?? item.kode ?? item.id ?? "");
    const label = normalizeText(
      item.nama_pt ?? item.nama_perusahaan ?? item.nama ?? value,
    );
    return { label, value };
  }

  function mapEstateToOption(item: EstateItem): OptionItem {
    const value = normalizeText(item.kode_est ?? item.kode ?? item.id ?? "");
    const label = normalizeText(item.nama_estate ?? item.nama ?? value);
    return { label, value };
  }

  function mapAfdelingToOption(item: AfdelingItem): OptionItem {
    const value = normalizeText(
      item.kode_afd ?? item.kode_afdeling ?? item.kode ?? item.id ?? "",
    );
    const label = normalizeText(item.nama_afdeling ?? item.nama ?? value);
    return { label, value };
  }

  function mapBlokToOption(item: BlokItem): OptionItem {
    const value = normalizeText(
      item.blok_id ?? item.kode_blok ?? item.kode ?? item.id ?? "",
    );
    const label = normalizeText(item.nama_blok ?? item.nama ?? value);
    return { label, value };
  }

  function normalizeApiArray<T>(response: unknown): T[] {
    if (Array.isArray(response)) return response as T[];
    const data = (response as any)?.data;
    if (Array.isArray(data)) return data as T[];
    return [];
  }

  async function fetchAreaOptions() {
    loadingArea.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api(`${baseUrl}/v1/spatial/area?limit=100`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      const items = normalizeApiArray<AreaItem>(response);
      areaOptions.value = items
        .map(mapAreaToOption)
        .filter((item) => !!item.value);
      return areaOptions.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data area.");
      throw error;
    } finally {
      loadingArea.value = false;
    }
  }

  async function fetchPtOptions(areaId?: string) {
    loadingPt.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const query = new URLSearchParams();
      query.set("limit", "100");
      if (areaId) query.set("area_id", areaId);

      const response = await $api(
        `${baseUrl}/v1/spatial/pt?${query.toString()}`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      const items = normalizeApiArray<PtItem>(response);
      ptOptions.value = items.map(mapPtToOption).filter((item) => !!item.value);
      return ptOptions.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data PT.");
      throw error;
    } finally {
      loadingPt.value = false;
    }
  }

  async function fetchEstateOptions(kodePt?: string) {
    loadingEstate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const query = new URLSearchParams();
      query.set("limit", "100");
      if (kodePt) query.set("kode_pt", kodePt);

      const response = await $api(
        `${baseUrl}/v1/spatial/estate?${query.toString()}`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      const items = normalizeApiArray<EstateItem>(response);
      estateOptions.value = items
        .map(mapEstateToOption)
        .filter((item) => !!item.value);
      return estateOptions.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil data estate.",
      );
      throw error;
    } finally {
      loadingEstate.value = false;
    }
  }

  async function fetchAfdelingOptions(kodeEst?: string) {
    loadingAfdeling.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const query = new URLSearchParams();
      query.set("limit", "100");
      if (kodeEst) query.set("kode_est", kodeEst);

      const response = await $api(
        `${baseUrl}/v1/spatial/afdeling?${query.toString()}`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      const items = normalizeApiArray<AfdelingItem>(response);
      afdelingOptions.value = items
        .map(mapAfdelingToOption)
        .filter((item) => !!item.value);
      return afdelingOptions.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil data afdeling.",
      );
      throw error;
    } finally {
      loadingAfdeling.value = false;
    }
  }

  async function fetchBlokOptions(kodeAfd?: string) {
    loadingBlok.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const query = new URLSearchParams();
      query.set("limit", "100");
      if (kodeAfd) query.set("kode_afd", kodeAfd);

      const response = await $api(
        `${baseUrl}/v1/spatial/blok?${query.toString()}`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      const items = normalizeApiArray<BlokItem>(response);
      blokOptions.value = items
        .map(mapBlokToOption)
        .filter((item) => !!item.value);
      return blokOptions.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data blok.");
      throw error;
    } finally {
      loadingBlok.value = false;
    }
  }

  async function setSelectedArea(value: string) {
    selectedArea.value = value || "";
    selectedPt.value = "";
    selectedEstate.value = "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";

    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];

    await fetchPtOptions(selectedArea.value || undefined);
  }

  async function setSelectedPt(value: string) {
    selectedPt.value = value || "";
    selectedEstate.value = "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";

    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];

    await fetchEstateOptions(selectedPt.value || undefined);
  }

  async function setSelectedEstate(value: string) {
    selectedEstate.value = value || "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";

    afdelingOptions.value = [];
    blokOptions.value = [];

    await fetchAfdelingOptions(selectedEstate.value || undefined);
  }

  async function setSelectedAfdeling(value: string) {
    selectedAfdeling.value = value || "";
    selectedBlok.value = "";

    blokOptions.value = [];

    await fetchBlokOptions(selectedAfdeling.value || undefined);
  }

  function setSelectedBlok(value: string) {
    selectedBlok.value = value || "";
  }

  async function initSpatialOptions() {
    await fetchAreaOptions();
    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];
  }

  async function loadGeoJSONData() {
    await initSpatialOptions();
  }

  async function applyFilters(nextFilters: MapFilters) {
    selectedArea.value = nextFilters.area || "";
    selectedPt.value = "";
    selectedEstate.value = "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";

    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];

    if (!selectedArea.value) return;

    await fetchPtOptions(selectedArea.value);

    if (!nextFilters.pt) return;
    selectedPt.value = nextFilters.pt;

    await fetchEstateOptions(selectedPt.value);

    if (!nextFilters.estate) return;
    selectedEstate.value = nextFilters.estate;

    await fetchAfdelingOptions(selectedEstate.value);

    if (!nextFilters.afdeling) return;
    selectedAfdeling.value = nextFilters.afdeling;

    await fetchBlokOptions(selectedAfdeling.value);

    if (!nextFilters.blok) return;
    selectedBlok.value = nextFilters.blok;
  }

  async function resetFilters() {
    selectedArea.value = "";
    selectedPt.value = "";
    selectedEstate.value = "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";

    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];

    await fetchAreaOptions();
  }

  const filters = computed<MapFilters>(() => ({
    area: selectedArea.value,
    pt: selectedPt.value,
    estate: selectedEstate.value,
    afdeling: selectedAfdeling.value,
    blok: selectedBlok.value,
  }));

  const filterOptions = computed(() => ({
    area: areaOptions.value,
    pt: ptOptions.value,
    estate: estateOptions.value,
    afdeling: afdelingOptions.value,
    blok: blokOptions.value,
    tahunTanam: [] as OptionItem[],
    statusTanam: [] as OptionItem[],
    jenisBibit: [] as OptionItem[],
  }));

  const summary = computed<MapSummary>(() => ({
    totalBlok: blokOptions.value.length,
    totalLuasTanam: 0,
    totalPokok: 0,
    totalJalan: 0,
    totalDrainase: 0,
    totalJembatan: 0,
  }));

  const isLoading = computed(
    () =>
      loadingArea.value ||
      loadingPt.value ||
      loadingEstate.value ||
      loadingAfdeling.value ||
      loadingBlok.value,
  );

  return {
    areaOptions,
    ptOptions,
    estateOptions,
    afdelingOptions,
    blokOptions,
    selectedArea,
    selectedPt,
    selectedEstate,
    selectedAfdeling,
    selectedBlok,
    loadingArea,
    loadingPt,
    loadingEstate,
    loadingAfdeling,
    loadingBlok,
    errorMessage,
    hasArea,
    hasPt,
    hasEstate,
    hasAfdeling,
    hasBlok,
    clearError,
    fetchAreaOptions,
    fetchPtOptions,
    fetchEstateOptions,
    fetchAfdelingOptions,
    fetchBlokOptions,
    setSelectedArea,
    setSelectedPt,
    setSelectedEstate,
    setSelectedAfdeling,
    setSelectedBlok,
    initSpatialOptions,
    resetFilters,
    filters,
    filterOptions,
    summary,
    isLoading,
    loadGeoJSONData,
    applyFilters,
  };
});
