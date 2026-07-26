/* eslint-disable @typescript-eslint/no-explicit-any */
import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import { useAuthStore } from "./authStore";

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

type AksesDataItem = {
  kode_pt?: string;
  kode_est?: string;
  kode_area?: string;
  kode_afd?: string;
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

type GeoJSONFeatureCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, unknown>
>;

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const useMapStore = defineStore("map", () => {
  const { $api } = useNuxtApp();
  const authStore = useAuthStore();

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
  const loadingGeoJSON = ref(false);
  const errorMessage = ref("");
  const filteredGeoJSON = ref<GeoJSONFeatureCollection | null>(null);

  const areaCodeAliases = ref<Map<string, Set<string>>>(new Map());
  const ptCodeAliases = ref<Map<string, Set<string>>>(new Map());
  const estateCodeAliases = ref<Map<string, Set<string>>>(new Map());
  const afdelingCodeAliases = ref<Map<string, Set<string>>>(new Map());

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

  function getUserAksesData(): AksesDataItem[] {
    const aksesData = authStore.user?.akses_data;
    if (!Array.isArray(aksesData)) return [];
    return aksesData as AksesDataItem[];
  }

  function getAllowedAreaCodes(): Set<string> {
    const codes = new Set<string>();
    for (const item of getUserAksesData()) {
      const code = normalizeText(item.kode_area);
      if (code) codes.add(code);
    }
    return codes;
  }

  function getAllowedPtCodes(areaCode: string): Set<string> {
    const codes = new Set<string>();
    for (const item of getUserAksesData()) {
      if (!areaCodesMatch(areaCode, normalizeText(item.kode_area))) continue;
      const code = normalizeText(item.kode_pt);
      if (code) codes.add(code);
    }
    return codes;
  }

  function getAllowedEstateCodes(areaCode: string, ptCode = ""): Set<string> {
    const codes = new Set<string>();
    for (const item of getUserAksesData()) {
      if (!areaCodesMatch(areaCode, normalizeText(item.kode_area))) continue;
      if (
        ptCode &&
        !codesMatch(ptCodeAliases.value, ptCode, normalizeText(item.kode_pt))
      ) {
        continue;
      }
      const code = normalizeText(item.kode_est);
      if (code) codes.add(code);
    }
    return codes;
  }

  function getAllowedAfdelingCodes(
    areaCode: string,
    ptCode = "",
    estateCode = "",
  ): Set<string> {
    const codes = new Set<string>();
    for (const item of getUserAksesData()) {
      if (!areaCodesMatch(areaCode, normalizeText(item.kode_area))) continue;
      if (
        ptCode &&
        !codesMatch(ptCodeAliases.value, ptCode, normalizeText(item.kode_pt))
      ) {
        continue;
      }
      if (
        estateCode &&
        !codesMatch(
          estateCodeAliases.value,
          estateCode,
          normalizeText(item.kode_est),
        )
      ) {
        continue;
      }
      const code = normalizeText(item.kode_afd);
      if (code) codes.add(code);
    }
    return codes;
  }

  function filterOptionsByAllowedValues(
    options: OptionItem[],
    allowedValues: Set<string>,
  ): OptionItem[] {
    if (allowedValues.size === 0) return [];
    return options.filter((option) => allowedValues.has(option.value));
  }

  function registerCodeAliases(
    aliasMap: Map<string, Set<string>>,
    values: unknown[],
  ) {
    const aliases = new Set(
      values.map((value) => normalizeText(value)).filter(Boolean),
    );

    for (const alias of aliases) {
      aliasMap.set(alias, aliases);
    }
  }

  function codesMatch(
    aliasMap: Map<string, Set<string>>,
    left: string,
    right: string,
  ): boolean {
    const normalizedLeft = normalizeText(left);
    const normalizedRight = normalizeText(right);
    if (!normalizedLeft || !normalizedRight) return false;
    if (normalizedLeft === normalizedRight) return true;

    const leftAliases = aliasMap.get(normalizedLeft);
    if (leftAliases?.has(normalizedRight)) return true;

    const rightAliases = aliasMap.get(normalizedRight);
    return rightAliases?.has(normalizedLeft) ?? false;
  }

  function getPtIdentifiers(item: PtItem): Set<string> {
    return new Set(
      [
        normalizeText(item.id),
        normalizeText(item.kode_pt),
        normalizeText(item.kode),
      ].filter(Boolean),
    );
  }

  function getEstateIdentifiers(item: EstateItem): Set<string> {
    return new Set(
      [
        normalizeText(item.id),
        normalizeText(item.kode_est),
        normalizeText(item.kode),
      ].filter(Boolean),
    );
  }

  function getAfdelingIdentifiers(item: AfdelingItem): Set<string> {
    return new Set(
      [
        normalizeText(item.id),
        normalizeText(item.kode_afd),
        normalizeText(item.kode_afdeling),
        normalizeText(item.kode),
      ].filter(Boolean),
    );
  }

  function itemMatchesAllowedCodes(
    identifiers: Set<string>,
    allowedCodes: Set<string>,
  ): boolean {
    if (allowedCodes.size === 0) return false;
    for (const identifier of identifiers) {
      if (allowedCodes.has(identifier)) return true;
    }
    return false;
  }

  function sortOptionsByLabelAsc(options: OptionItem[]): OptionItem[] {
    return [...options].sort((a, b) =>
      a.label.localeCompare(b.label, "id", { sensitivity: "base" }),
    );
  }

  function applySingleOrAllDefault(
    options: OptionItem[],
    selectedRef: { value: string },
  ) {
    const singleOption = options[0];
    if (options.length === 1 && singleOption) {
      selectedRef.value = singleOption.value;
      return;
    }

    selectedRef.value = "";
  }

  async function loadEstateLevel() {
    selectedEstate.value = "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];

    if (!selectedArea.value) return;

    await fetchEstateOptions(selectedPt.value || undefined);
    applySingleOrAllDefault(estateOptions.value, selectedEstate);
    await loadAfdelingLevel();
  }

  async function loadAfdelingLevel() {
    selectedAfdeling.value = "";
    selectedBlok.value = "";
    afdelingOptions.value = [];
    blokOptions.value = [];

    if (!selectedArea.value) return;

    await fetchAfdelingOptions(selectedEstate.value || undefined);
    applySingleOrAllDefault(afdelingOptions.value, selectedAfdeling);
    await loadBlokLevel();
  }

  async function loadBlokLevel() {
    selectedBlok.value = "";
    blokOptions.value = [];

    if (!selectedArea.value) return;

    await fetchBlokOptions(selectedAfdeling.value || undefined);
    applySingleOrAllDefault(blokOptions.value, selectedBlok);
  }

  async function loadPtLevel() {
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
    applySingleOrAllDefault(ptOptions.value, selectedPt);
    await loadEstateLevel();
  }

  function registerAreaCodeAliases(item: AreaItem) {
    const aliases = new Set(
      [
        normalizeText(item.area_id),
        normalizeText(item.kode_area),
        normalizeText(item.id),
      ].filter(Boolean),
    );

    for (const alias of aliases) {
      areaCodeAliases.value.set(alias, aliases);
    }
  }

  function areaCodesMatch(left: string, right: string): boolean {
    const normalizedLeft = normalizeText(left);
    const normalizedRight = normalizeText(right);
    if (normalizedLeft === normalizedRight) return true;

    const leftAliases = areaCodeAliases.value.get(normalizedLeft);
    if (leftAliases?.has(normalizedRight)) return true;

    const rightAliases = areaCodeAliases.value.get(normalizedRight);
    return rightAliases?.has(normalizedLeft) ?? false;
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
      const allowedAreas = getAllowedAreaCodes();
      areaCodeAliases.value = new Map();

      const filteredItems = items.filter((item) => {
        if (allowedAreas.size === 0) return false;
        const areaId = normalizeText(item.area_id);
        const kodeArea = normalizeText(item.kode_area);
        return (
          allowedAreas.has(areaId) ||
          allowedAreas.has(kodeArea) ||
          allowedAreas.has(normalizeText(item.id))
        );
      });

      filteredItems.forEach(registerAreaCodeAliases);

      areaOptions.value = sortOptionsByLabelAsc(
        filteredItems.map(mapAreaToOption).filter((item) => !!item.value),
      );
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
      ptCodeAliases.value = new Map();
      items.forEach((item) =>
        registerCodeAliases(ptCodeAliases.value, [
          item.id,
          item.kode_pt,
          item.kode,
        ]),
      );

      const allowedPtCodes = areaId
        ? getAllowedPtCodes(areaId)
        : new Set<string>();
      ptOptions.value = sortOptionsByLabelAsc(
        items
          .filter((item) =>
            itemMatchesAllowedCodes(getPtIdentifiers(item), allowedPtCodes),
          )
          .map(mapPtToOption)
          .filter((item) => !!item.value),
      );
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
      estateCodeAliases.value = new Map();
      items.forEach((item) =>
        registerCodeAliases(estateCodeAliases.value, [
          item.id,
          item.kode_est,
          item.kode,
        ]),
      );

      const allowedEstateCodes = selectedArea.value
        ? getAllowedEstateCodes(selectedArea.value, kodePt ?? "")
        : new Set<string>();
      estateOptions.value = sortOptionsByLabelAsc(
        items
          .filter((item) =>
            itemMatchesAllowedCodes(
              getEstateIdentifiers(item),
              allowedEstateCodes,
            ),
          )
          .map(mapEstateToOption)
          .filter((item) => !!item.value),
      );
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
      afdelingCodeAliases.value = new Map();
      items.forEach((item) =>
        registerCodeAliases(afdelingCodeAliases.value, [
          item.id,
          item.kode_afd,
          item.kode_afdeling,
          item.kode,
        ]),
      );

      const allowedAfdelingCodes = selectedArea.value
        ? getAllowedAfdelingCodes(
            selectedArea.value,
            selectedPt.value,
            kodeEst ?? "",
          )
        : new Set<string>();
      afdelingOptions.value = sortOptionsByLabelAsc(
        items
          .filter((item) =>
            itemMatchesAllowedCodes(
              getAfdelingIdentifiers(item),
              allowedAfdelingCodes,
            ),
          )
          .map(mapAfdelingToOption)
          .filter((item) => !!item.value),
      );
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
      const mappedOptions = items
        .map(mapBlokToOption)
        .filter((item) => !!item.value);
      const allowedAfdelingCodes = selectedArea.value
        ? getAllowedAfdelingCodes(
            selectedArea.value,
            selectedPt.value,
            selectedEstate.value,
          )
        : new Set<string>();

      const isAfdelingAllowed =
        !kodeAfd ||
        itemMatchesAllowedCodes(
          new Set([normalizeText(kodeAfd)]),
          allowedAfdelingCodes,
        ) ||
        [...allowedAfdelingCodes].some((code) =>
          codesMatch(afdelingCodeAliases.value, kodeAfd, code),
        );

      blokOptions.value = isAfdelingAllowed
        ? sortOptionsByLabelAsc(mappedOptions)
        : [];
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
    await loadPtLevel();
  }

  async function setSelectedPt(value: string) {
    selectedPt.value = value || "";
    await loadEstateLevel();
  }

  async function setSelectedEstate(value: string) {
    selectedEstate.value = value || "";
    await loadAfdelingLevel();
  }

  async function setSelectedAfdeling(value: string) {
    selectedAfdeling.value = value || "";
    await loadBlokLevel();
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

  async function initDefaultSpatialSelection() {
    selectedPt.value = "";
    selectedEstate.value = "";
    selectedAfdeling.value = "";
    selectedBlok.value = "";

    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];

    await fetchAreaOptions();

    const defaultArea = areaOptions.value[0];
    if (defaultArea) {
      selectedArea.value = defaultArea.value;
      await loadPtLevel();
      return;
    }

    selectedArea.value = "";
  }

  async function loadGeoJSONData() {
    await initDefaultSpatialSelection();
  }

  async function fetchBlokPopupData(params: {
    kodePt?: string;
    kodeEst?: string;
    kodeAfd?: string;
    kodeBlok: string;
    bulan: string;
    tahun: string;
  }) {
    const baseUrl = getApiBaseUrl();
    const query = new URLSearchParams();

    if (params.kodePt) query.set("kode_pt", params.kodePt);
    if (params.kodeEst) query.set("kode_est", params.kodeEst);
    if (params.kodeAfd) query.set("kode_afd", params.kodeAfd);
    if (params.kodeBlok) query.set("kode_blok", params.kodeBlok);
    if (params.bulan) query.set("bulan", params.bulan);
    if (params.tahun) query.set("tahun", params.tahun);

    const response = await $api(
      `${baseUrl}/v1/spatial/geojson?${query.toString()}`,
      {
        method: "GET",
        headers: getAuthHeaders(),
      },
    );

    const featureCollection = normalizeGeoJSONResponse(response);
    return featureCollection.features[0] ?? null;
  }

  function getFilterLabel(
    options: OptionItem[],
    value: string,
    emptyLabel = "All",
  ) {
    if (!value) return emptyLabel;
    return options.find((item) => item.value === value)?.label ?? value;
  }

  function getPopupHierarchyLabels() {
    return {
      area: getFilterLabel(areaOptions.value, selectedArea.value, "-"),
      pt: getFilterLabel(ptOptions.value, selectedPt.value),
      estate: getFilterLabel(estateOptions.value, selectedEstate.value),
      afdeling: getFilterLabel(afdelingOptions.value, selectedAfdeling.value),
    };
  }

  function normalizeGeoJSONResponse(response: unknown): GeoJSONFeatureCollection {
    const data = (response as { data?: unknown })?.data ?? response;

    if (
      typeof data === "object" &&
      data !== null &&
      (data as GeoJSONFeatureCollection).type === "FeatureCollection" &&
      Array.isArray((data as GeoJSONFeatureCollection).features)
    ) {
      return data as GeoJSONFeatureCollection;
    }

    return {
      type: "FeatureCollection",
      features: [],
    };
  }

  async function applyFilters(nextFilters: MapFilters, selectedTahun: string) {
    loadingGeoJSON.value = true;
    clearError();

    try {
      selectedArea.value = nextFilters.area || "";
      selectedPt.value = nextFilters.pt || "";
      selectedEstate.value = nextFilters.estate || "";
      selectedAfdeling.value = nextFilters.afdeling || "";
      selectedBlok.value = nextFilters.blok || "";

      const baseUrl = getApiBaseUrl();
      const query = new URLSearchParams();

      query.set("kode_pt", nextFilters.pt || "");
      query.set("kode_est", nextFilters.estate || "");
      query.set("kode_afd", nextFilters.afdeling || "");
      query.set("kode_blok", nextFilters.blok || "");
      query.set("tahun", selectedTahun || "");

      const response = await $api(
        `${baseUrl}/v1/spatial/geojson?${query.toString()}`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      filteredGeoJSON.value = normalizeGeoJSONResponse(response);
    } catch (error: any) {
      filteredGeoJSON.value = null;
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data blok");
      throw error;
    } finally {
      loadingGeoJSON.value = false;
    }
  }

  async function resetFilters() {
    filteredGeoJSON.value = null;
    await initDefaultSpatialSelection();
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
      loadingBlok.value ||
      loadingGeoJSON.value,
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
    loadingGeoJSON,
    filteredGeoJSON,
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
    fetchBlokPopupData,
    getPopupHierarchyLabels,
  };
});
