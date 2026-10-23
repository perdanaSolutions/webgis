import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { useAuthStore } from "~/stores/authStore";
import { expandTransactionGrants, grantCovers } from "~/utils/accessGrants";
import { fetchMapCached } from "~/utils/mapCacheSchema";
import { popupPeriodFromProperties } from "~/utils/mapBlokPopup";
import { readBudgetCategory } from "~/utils/mapLayers";

/**
 * State halaman Blok Profile (peta layar penuh).
 *
 * Hierarki filter: Ownership -> Grup -> Perusahaan (PT) -> Area -> Estate -> Afdeling -> Blok
 * -> Periode (bulan + tahun, plus Year to Date) -> Periode pembanding.
 * Level master mengikuti API: GET /spatial/pt?kode_grup, /area?kode_grup&kode_pt,
 * /estate?kode_grup&kode_pt&area_id, /afdeling?kode_grup&kode_pt&kode_est, /blok.
 * Ownership tidak menyaring daftar master; ikut ke GeoJSON, detail, dan histori.
 * - Grup (TPA/SGA) opsional untuk semua user ("Semua grup"). Mengganti grup memuat
 *   ulang perusahaan pada grup itu; `kode_grup` ikut ke semua opsi, GeoJSON, layer, dan histori.
 * - Mengubah field mengisi opsi berjenjang, lalu peta dan transaksi langsung dimuat.
 *   Satu pilihan (misalnya grup) menunggu opsi di bawahnya selesai, baru diterapkan sekali.
 * - Penerapan menyalin draft ke filter terapan, lalu memuat GeoJSON peta (wilayah)
 *   dan kartu transaksi. Ownership masuk API history, detail, dan setiap GeoJSON.
 *   Setiap GeoJSON membawa tahun dari field Periode, plus bulan bila dipilih.
 *   Tahun default = tahun periode terakhir yang sudah diupload (GET /spatial/periode-terakhir);
 *   bulan periode selalu kosong saat load pertama dan reset.
 * - Year to date tanpa bulan = produksi Januari s/d bulan berjalan (tahun lalu: s/d Desember).
 *   Mencentang Year to Date mengosongkan bulan periode. Year to date dan periode
 *   pembanding hanya dikirim ke GeoJSON batas blok
 *   (`year_to_date`, `bulan_comparison` + `tahun_comparison`), bukan ke layer lain.
 * - Popup blok dibuka pada bulan produksi yang mewarnai blok itu (produksi_tbs.periode).
 * - Blok hanya MEMILIH satu blok di dalam scope (peta tidak difilter ulang ke
 *   satu poligon), sehingga tetangga tetap terlihat.
 * Pilihan dibatasi `akses_data` user (superadmin bebas).
 * Muatan awal: satu perusahaan terpilih, lalu area pertama perusahaan itu.
 * Estate, afdeling, dan blok memuat seluruh data pada area itu (tanpa memilih satu).
 */

export type Option = { label: string; value: string };
export type ScopeLevel =
  | "semua"
  | "area"
  | "pt"
  | "estate"
  | "afdeling"
  | "blok";
export type StatusNotice = {
  kind: "loading" | "success" | "error";
  message: string;
};

type CompanyItem = {
  id: number;
  kode_pt: string;
  nama_pt: string;
  short_name_pt?: string | null;
};
type EstateItem = {
  id: number;
  kode_est: string;
  nama_estate: string;
  kode_pt: string;
};
type AksesData = {
  kode_area?: string | null;
  kode_pt?: string | null;
  kode_est?: string | null;
  kode_afd?: string | null;
};

export type BlockFeature = GeoJSON.Feature<
  GeoJSON.Geometry,
  Record<string, any>
>;
export type BlockCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, any>
>;

export type ProductionYear = {
  periode: number | string;
  tahun: number;
  bulan: number | null;
  ton: number;
  luas: number;
  ton_ha: number;
  bjr: number;
  jjg_ppk: number;
  kg_ppk: number;
};
export type ProductionGapCategory = {
  kategori: string;
  keterangan: string;
  luas: number;
  jumlah_blok: number;
  persen_blok: number;
};
export type ProductionGapSummary = {
  periode: { tahun: number | null; bulan: number | null };
  pembanding: string;
  kategori: ProductionGapCategory[];
  grand_total: { luas: number; jumlah_blok: number; persen_blok: number };
};
export type SlopeShare = {
  key: string;
  label: string;
  range: string;
  value: number;
  ha?: number;
};

export type AreaStatementYearRow = {
  tahun_tanam: number;
  luas_tanam: number;
};
export type AreaStatementDivisionRow = {
  division_code: string;
  luas_tanam: number;
};
export type AreaStatementBucket<T> = {
  area_code?: string | null;
  details?: T[];
  total_luas_tanam?: number;
};
export type ArealLanduseRow = {
  kode: string;
  label: string;
  luas: number;
  persen: number;
};
export type ArealPopulationClass = {
  kode: string;
  label: string;
  jumlah_blok: number;
  luas_tanam: number;
  persen: number;
};
/** GET /spatial/layer-data/areal (snapshot areal statement + landuse). Bagian tanpa hak akses = null. */
export type ArealSummary = {
  periode?: { areal_statement: string | null; landuse: string | null };
  areal_tanam?: {
    total_luas_tanam: number;
    per_status: Array<{ status: string; label: string; luas_tanam: number }>;
    per_tahun_tanam: Array<{
      tahun_tanam: number;
      warna: string | null;
      luas_tanam: number;
      persen: number;
    }>;
  } | null;
  populasi?: { kelas: ArealPopulationClass[] } | null;
  areal_non_tanam?: { total_luas: number; per_baris: ArealLanduseRow[] } | null;
  total?: { grand_total_areal: number } | null;
};
export type AreaStatementHistory = {
  status?: string;
  message?: string;
  data?: {
    group_tahun_tanam?: AreaStatementBucket<AreaStatementYearRow>;
    group_divisi?: AreaStatementBucket<AreaStatementDivisionRow>;
  };
  /** Ditempel dari /spatial/layer-data/areal untuk card Informasi Areal Statement. */
  ringkasan_areal?: ArealSummary | null;
};
export type RotationYear = {
  tahun: number;
  bulan: number | null;
  total_rotasi: number;
  rotasi_terakhir: number;
  avg_pusingan_hari: number;
  total_luas_rotasi: number;
  total_pokok_rotasi: number;
};
export type RotationActivity = {
  tanggal: string;
  rotasi: string;
  hari: number;
  status: string;
  luas: number;
  pokok: number;
};
export type RotationHistory = {
  label?: string;
  mode_akumulasi?: string;
  total_periode?: number;
  data?: RotationYear[];
  /** Isi dari GET /spatial/blok/detail. Kalau ada, kartu tidak memakai agregat /history. */
  kegiatan?: RotationActivity[];
};
const SLOPE_CLASSES: Array<{
  key: string;
  label: string;
  range: string;
  historyKey: string;
  detailKey: string;
}> = [
  {
    key: "datar",
    label: "Datar",
    range: "0–3%",
    historyKey: "0-3%",
    detailKey: "pct_tanah_datar",
  },
  {
    key: "gelombang",
    label: "Bergelombang",
    range: "3–8%",
    historyKey: "3-8%",
    detailKey: "pct_gelombang",
  },
  {
    key: "berbukit",
    label: "Berbukit",
    range: "8–15%",
    historyKey: "8-15%",
    detailKey: "pct_berbukit",
  },
  {
    key: "curam",
    label: "Curam",
    range: "15–25%",
    historyKey: "15-25%",
    detailKey: "pct_curam",
  },
  {
    key: "sangat",
    label: "Sangat curam",
    range: ">25%",
    historyKey: ">25%",
    detailKey: "",
  },
];

function norm(value: unknown) {
  return String(value ?? "")
    .trim()
    .toUpperCase();
}

function currentYear() {
  return String(new Date().getFullYear());
}

/** Periode batas blok di properties GeoJSON (`bulan` + `tahun`). */
function readFeaturePeriod(props: Record<string, any> | undefined) {
  const bulan = Number(props?.bulan);
  const tahun = Number(props?.tahun);
  if (!Number.isInteger(tahun) || tahun < 1900) return null;
  const month =
    Number.isInteger(bulan) && bulan >= 1 && bulan <= 12 ? bulan : null;
  return { bulan: month, tahun };
}

export const useBlokProfileStore = defineStore("blokProfile", () => {
  const authStore = useAuthStore();

  const groupOptions = ref<Option[]>([]);
  const areaOptions = ref<Option[]>([]);
  const ptOptions = ref<Option[]>([]);
  const estateOptions = ref<Option[]>([]);
  const afdelingOptions = ref<Option[]>([]);
  const estatesByCode = ref(new Map<string, EstateItem>());

  const grup = ref("");
  const area = ref("");
  const pt = ref("");
  const estate = ref("");
  const afdeling = ref("");
  const blokId = ref("");
  const ownership = ref("");
  const bulan = ref("");
  const tahun = ref(currentYear());
  const yearToDate = ref(false);
  const bulanComparison = ref("");
  const tahunComparison = ref("");
  /** Periode terakhir yang sudah diupload (default filter Periode). */
  const defaultPeriod = ref<{ bulan: string; tahun: string } | null>(null);
  const blokOptions = ref<Option[]>([]);

  /** Filter yang sedang aktif di peta/kartu (hasil Apply terakhir). */
  type AppliedFilter = {
    grup: string;
    area: string;
    pt: string;
    estate: string;
    afdeling: string;
    blokId: string;
    ownership: string;
    bulan: string;
    tahun: string;
    yearToDate: boolean;
    bulanComparison: string;
    tahunComparison: string;
  };
  function emptyApplied(): AppliedFilter {
    return {
      grup: "",
      area: "",
      pt: "",
      estate: "",
      afdeling: "",
      blokId: "",
      ownership: "",
      bulan: "",
      tahun: currentYear(),
      yearToDate: false,
      bulanComparison: "",
      tahunComparison: "",
    };
  }
  const applied = ref<AppliedFilter>(emptyApplied());
  const applying = ref(false);

  const blocks = ref<BlockCollection | null>(null);
  const detail = ref<Record<string, any> | null>(null);
  const production = ref<Record<string, any> | null>(null);
  const areaStatement = ref<AreaStatementHistory | null>(null);
  const rotation = ref<RotationHistory | null>(null);

  const loadingOptions = ref(false);
  const loadingBlocks = ref(false);
  const loadingDetail = ref(false);
  const loadingProduction = ref(false);
  const loadingAreaStatement = ref(false);
  const loadingRotation = ref(false);
  const errorMessage = ref("");
  const statusNotice = ref<StatusNotice | null>(null);

  let blocksSeq = 0;
  let detailSeq = 0;
  let historySeq = 0;
  let applySeq = 0;
  let filterEpoch = 0;
  const filterGeneration = ref(0);
  let detailKey = "";
  let detailFlight: {
    key: string;
    promise: Promise<Record<string, any>>;
  } | null = null;
  /** True saat kartu kanan sedang menampilkan blok yang diklik di peta, bukan hasil Filter Kebun. */
  let mapDrillActive = false;
  let statusTimer: ReturnType<typeof setTimeout> | null = null;

  function clearStatusTimer() {
    if (!statusTimer) return;
    clearTimeout(statusTimer);
    statusTimer = null;
  }

  function setStatus(
    kind: StatusNotice["kind"],
    message: string,
    autoHideMs = 0,
  ) {
    clearStatusTimer();
    statusNotice.value = { kind, message };
    if (autoHideMs <= 0) return;
    statusTimer = setTimeout(() => {
      if (statusNotice.value?.message === message) statusNotice.value = null;
      statusTimer = null;
    }, autoHideMs);
  }

  function clearStatus() {
    clearStatusTimer();
    statusNotice.value = null;
  }

  const LAST_SEARCH_KEY = "blok-profile-last-search";
  type SavedSearch = {
    grup?: string;
    area: string;
    pt: string;
    estate: string;
    afdeling: string;
    blokId: string;
    ownership: string;
    bulan: string;
    tahun: string;
    yearToDate?: boolean;
    bulanComparison?: string;
    tahunComparison?: string;
    detail: Record<string, any> | null;
    production: Record<string, any> | null;
    areaStatement: AreaStatementHistory | null;
    rotation: RotationHistory | null;
  };
  let memorySearch: SavedSearch | null = null;

  function cloneData<T>(value: T): T {
    if (value == null) return value;
    return JSON.parse(JSON.stringify(value)) as T;
  }

  function persistSearch(snapshot: SavedSearch) {
    memorySearch = snapshot;
    if (!import.meta.client) return;
    try {
      localStorage.setItem(LAST_SEARCH_KEY, JSON.stringify(snapshot));
    } catch {
      /* penyimpanan penuh atau mode privat */
    }
  }

  /** Hasil Filter Kebun terakhir: filter terapan (bukan isian yang belum di-Apply) + data kartu kanan. */
  function captureSearch() {
    const current = applied.value;
    persistSearch({
      grup: current.grup,
      area: current.area,
      pt: current.pt,
      estate: current.estate,
      afdeling: current.afdeling,
      blokId: current.blokId,
      ownership: current.ownership,
      bulan: current.bulan,
      tahun: current.tahun || currentYear(),
      yearToDate: current.yearToDate,
      bulanComparison: current.bulanComparison,
      tahunComparison: current.tahunComparison,
      detail: cloneData(detail.value),
      production: cloneData(production.value),
      areaStatement: cloneData(areaStatement.value),
      rotation: cloneData(rotation.value),
    });
  }

  /** Histori scope Filter Kebun yang selesai setelah klik peta disimpan untuk pemulihan, tanpa menimpa kartu blok. */
  function patchSavedHistories() {
    if (!mapDrillActive || !memorySearch) return;
    memorySearch.production = cloneData(production.value);
    memorySearch.areaStatement = cloneData(areaStatement.value);
    memorySearch.rotation = cloneData(rotation.value);
    persistSearch(memorySearch);
  }

  function rememberScopeHistory(table: string, value: unknown) {
    if (!mapDrillActive || !memorySearch) return;
    if (table === "trx_produksi_tbs")
      memorySearch.production = cloneData(value) as SavedSearch["production"];
    else if (table === "trx_areal_statement")
      memorySearch.areaStatement = cloneData(
        value,
      ) as SavedSearch["areaStatement"];
    else if (table === "trx_rotasi_pusingan")
      memorySearch.rotation = cloneData(value) as SavedSearch["rotation"];
    else return;
    persistSearch(memorySearch);
  }

  function readSavedSearch(): SavedSearch | null {
    if (memorySearch) return memorySearch;
    if (!import.meta.client) return null;
    try {
      const raw = localStorage.getItem(LAST_SEARCH_KEY);
      if (!raw) return null;
      memorySearch = JSON.parse(raw) as SavedSearch;
      return memorySearch;
    } catch {
      return null;
    }
  }

  // ------------------------------------------------------------------ API
  function baseUrl() {
    return useRuntimeConfig().public.apiBaseUrlPython as string;
  }

  async function get<T>(
    path: string,
    params: Record<string, string | number | undefined> = {},
    keepEmpty: string[] = [],
  ) {
    const { $api } = useNuxtApp();
    const query = new URLSearchParams();
    const always = new Set(keepEmpty);
    Object.entries(params).forEach(([key, value]) => {
      if (always.has(key)) {
        query.set(key, value == null ? "" : String(value));
        return;
      }
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    const qs = query.toString();
    const url = `${baseUrl()}/v1${path}${qs ? `?${qs}` : ""}`;
    const userId = String(authStore.user?.id ?? "");
    return fetchMapCached(userId, url, () => $api<T>(url));
  }

  // ------------------------------------------------------------------ hak akses
  const isSuperAdmin = computed(() => authStore.isSuperAdmin);
  /** Hanya akun ini yang boleh memilih "semua" di filter kebun (Area s.d. Blok). */
  const allowAllScope = computed(
    () =>
      (authStore.user?.email ?? "").trim().toLowerCase() ===
      "superadmin@plantation.com",
  );
  const aksesData = computed(
    () => (authStore.user?.akses_data ?? []) as AksesData[],
  );
  const transactionGrants = computed(() =>
    isSuperAdmin.value
      ? null
      : expandTransactionGrants(authStore.user?.akses_transaksi),
  );
  const canViewProduction = computed(() =>
    grantCovers(
      transactionGrants.value,
      "trx.block_productions",
      "trx_produksi_tbs",
    ),
  );
  const canViewAreaStatement = computed(() =>
    grantCovers(
      transactionGrants.value,
      "trx.area_statements",
      "trx_areal_statement",
    ),
  );
  const canViewRotation = computed(() =>
    grantCovers(
      transactionGrants.value,
      "trx.harvest_rotations",
      "trx_rotasi_pusingan",
    ),
  );
  const canViewLanduse = computed(() =>
    grantCovers(transactionGrants.value, "spatial.landuse_polygons", "landuse"),
  );

  function scopeRows(): AksesData[] {
    return Array.isArray(aksesData.value) ? aksesData.value : [];
  }

  /** `"all"` = superadmin atau grant tanpa kode area. `"none"` = tidak ada wilayah. */
  function areaAllowance(): "all" | "none" | Set<string> {
    if (isSuperAdmin.value) return "all";
    const codes = scopeRows()
      .map((row) => norm(row.kode_area))
      .filter(Boolean);
    if (codes.length) return new Set(codes);
    if (
      scopeRows().some(
        (row) => norm(row.kode_pt) || norm(row.kode_est) || norm(row.kode_afd),
      )
    )
      return "all";
    return "none";
  }

  function grantTouches(
    row: AksesData,
    place: { area?: string; pt?: string; est?: string; afd?: string },
  ) {
    const rowArea = norm(row.kode_area);
    const rowPt = norm(row.kode_pt);
    const rowEst = norm(row.kode_est);
    const rowAfd = norm(row.kode_afd);
    if (!(rowArea || rowPt || rowEst || rowAfd)) return false;
    if (rowArea && rowArea !== norm(place.area)) return false;
    if (rowPt && place.pt !== undefined && rowPt !== norm(place.pt))
      return false;
    if (rowEst && place.est !== undefined && rowEst !== norm(place.est))
      return false;
    if (rowAfd && place.afd !== undefined && rowAfd !== norm(place.afd))
      return false;
    return true;
  }

  function isCompanyAllowed(item: CompanyItem): boolean {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) => {
      if (norm(row.kode_pt)) return norm(row.kode_pt) === norm(item.kode_pt);
      return Boolean(
        norm(row.kode_area) || norm(row.kode_est) || norm(row.kode_afd),
      );
    });
  }

  /** Grant induk (area/PT/estate tanpa anak) mencakup level di bawahnya. Baris ganda diabaikan. */
  function isEstateAllowed(item: EstateItem): boolean {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) => {
      if (norm(row.kode_area) && norm(row.kode_area) !== norm(area.value))
        return false;
      if (norm(row.kode_est)) return norm(row.kode_est) === norm(item.kode_est);
      if (norm(row.kode_pt)) return norm(row.kode_pt) === norm(item.kode_pt);
      if (norm(row.kode_afd)) return false;
      return Boolean(norm(row.kode_area));
    });
  }

  function isAfdelingAllowed(item: {
    kode_afd: string;
    kode_est?: string;
  }): boolean {
    if (isSuperAdmin.value) return true;
    const estatePt = estatesByCode.value.get(estate.value)?.kode_pt ?? pt.value;
    return scopeRows().some((row) => {
      if (
        norm(row.kode_area) &&
        area.value &&
        norm(row.kode_area) !== norm(area.value)
      )
        return false;
      if (norm(row.kode_est)) {
        const target = estate.value || item.kode_est || "";
        if (target && norm(row.kode_est) !== norm(target)) return false;
      }
      if (
        !norm(row.kode_est) &&
        norm(row.kode_pt) &&
        norm(row.kode_pt) !== norm(estatePt)
      )
        return false;
      if (norm(row.kode_afd)) return norm(row.kode_afd) === norm(item.kode_afd);
      return Boolean(
        norm(row.kode_area) || norm(row.kode_pt) || norm(row.kode_est),
      );
    });
  }

  function featureAllowed(props: Record<string, any>) {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) =>
      grantTouches(row, {
        area: props.kode_area,
        pt: props.kode_pt,
        est: props.kode_est,
        afd: props.kode_afd,
      }),
    );
  }

  function redactProperties(props: Record<string, any>) {
    const next = { ...props };
    const produksi = asPlain(next.produksi_tbs);
    if (produksi) next.produksi_tbs = produksi;
    const category = readBudgetCategory(next);
    // Warna peta hanya butuh kategori, tetap disimpan meski rincian produksi disembunyikan.
    if (category) next.kategori_budget = category;
    if (!canViewAreaStatement.value) delete next.areal_statement;
    if (!canViewProduction.value) {
      delete next.produksi_tbs;
      delete next.produksi_tbs_comparison;
    }
    if (!canViewRotation.value) delete next.rotasi_terakhir;
    return next;
  }

  function asPlain(value: unknown): Record<string, any> | null {
    if (!value) return null;
    if (typeof value === "string") {
      try {
        const parsed = JSON.parse(value) as unknown;
        return parsed && typeof parsed === "object"
          ? (parsed as Record<string, any>)
          : null;
      } catch {
        return null;
      }
    }
    return typeof value === "object" ? (value as Record<string, any>) : null;
  }

  function redactDetail(payload: Record<string, any> | null) {
    if (!payload) return payload;
    const next = { ...payload };
    const info =
      next.informasi_blok && typeof next.informasi_blok === "object"
        ? { ...next.informasi_blok }
        : null;
    if (info) {
      if (!canViewAreaStatement.value) {
        info.luas_tanam = null;
        info.luas_tanah = null;
        info.pokok = null;
        info.sph = null;
      }
      if (!canViewProduction.value) {
        info.tbs = null;
        info.jjg = null;
        info.bjr = null;
        info.yield = null;
        info.gap_act_bgt = null;
        info.gap_act_sns = null;
      }
      next.informasi_blok = info;
    }
    if (!canViewAreaStatement.value) next.areal_statement = null;
    if (!canViewProduction.value) next.produksi_tbs = null;
    if (!canViewRotation.value) next.rotasi_pusingan = null;
    return next;
  }

  // ------------------------------------------------------------------ opsi filter
  function filterAlive(epoch: number) {
    return epoch === filterEpoch;
  }

  /** Tahun default = tahun periode terakhir yang sudah diupload. Bulan tetap kosong. */
  async function loadDefaultPeriod() {
    try {
      const res = await get<{ bulan: number | null; tahun: number | null }>(
        "/spatial/periode-terakhir",
      );
      defaultPeriod.value = res?.tahun
        ? { bulan: String(res.bulan ?? ""), tahun: String(res.tahun) }
        : null;
    } catch {
      defaultPeriod.value = null;
    }
    if (defaultPeriod.value?.tahun) tahun.value = defaultPeriod.value.tahun;
  }

  /** Opsi grup tidak ikut dikosongkan clearMap (daftar tetap sama selama sesi). */
  async function loadGroups() {
    const res = await get<{
      data: Array<{ kode_grup: string; nama_grup: string }>;
    }>("/spatial/grup", { limit: 100 });
    groupOptions.value = (res?.data ?? []).map((item) => ({
      label: item.nama_grup || item.kode_grup,
      value: item.kode_grup,
    }));
  }

  async function loadAreas() {
    const epoch = filterEpoch;
    loadingOptions.value = true;
    try {
      const res = await get<{ data: Array<{ area_id: string; nama: string }> }>(
        "/spatial/area",
        {
          kode_grup: grup.value || undefined,
          kode_pt: pt.value || undefined,
          limit: 100,
        },
      );
      if (!filterAlive(epoch)) return;
      const allowed = areaAllowance();
      areaOptions.value = (res?.data ?? [])
        .filter(
          (item) =>
            allowed === "all" ||
            (allowed instanceof Set && allowed.has(norm(item.area_id))),
        )
        .map((item) => ({ label: item.nama, value: item.area_id }));
    } finally {
      if (filterAlive(epoch)) loadingOptions.value = false;
    }
  }

  async function loadCompanies() {
    const epoch = filterEpoch;
    ptOptions.value = [];
    const res = await get<{ data: CompanyItem[] }>("/spatial/pt", {
      kode_grup: grup.value || undefined,
      limit: 100,
    });
    if (!filterAlive(epoch)) return;
    ptOptions.value = (res?.data ?? [])
      .filter(isCompanyAllowed)
      .map((item) => ({
        label: item.short_name_pt || item.kode_pt,
        value: item.kode_pt,
      }));
  }

  async function loadPage<T>(
    path: string,
    params: Record<string, string | number | undefined>,
    epoch: number,
  ) {
    const pageSize = 100;
    const first = await get<{ data: T[]; total_data?: number }>(path, {
      ...params,
      page: 1,
      limit: pageSize,
    });
    if (!filterAlive(epoch)) return [] as T[];
    const rows = [...(first?.data ?? [])];
    const total = Number(first?.total_data ?? rows.length);
    const pages = Math.min(Math.ceil(total / pageSize), 30);
    for (let page = 2; page <= pages; page += 1) {
      const next = await get<{ data: T[] }>(path, {
        ...params,
        page,
        limit: pageSize,
      });
      if (!filterAlive(epoch)) return [] as T[];
      rows.push(...(next?.data ?? []));
    }
    return rows;
  }

  async function loadEstates() {
    const epoch = filterEpoch;
    estateOptions.value = [];
    estatesByCode.value = new Map();
    if (!grup.value && !pt.value && !area.value) return;
    const items = (
      await loadPage<EstateItem>(
        "/spatial/estate",
        {
          kode_grup: grup.value || undefined,
          area_id: area.value || undefined,
          kode_pt: pt.value || undefined,
        },
        epoch,
      )
    ).filter(isEstateAllowed);
    if (!filterAlive(epoch)) return;
    estatesByCode.value = new Map(items.map((item) => [item.kode_est, item]));
    estateOptions.value = items.map((item) => ({
      label: item.nama_estate,
      value: item.kode_est,
    }));
  }

  async function loadAfdelings() {
    const epoch = filterEpoch;
    afdelingOptions.value = [];
    if (!pt.value && !estate.value && !area.value) return;
    const estateCodes = new Set(
      estateOptions.value.map((option) => norm(option.value)),
    );
    const items = await loadPage<{ kode_afd: string; kode_est?: string }>(
      "/spatial/afdeling",
      {
        kode_grup: grup.value || undefined,
        kode_est: estate.value || undefined,
        kode_pt: pt.value || undefined,
      },
      epoch,
    );
    if (!filterAlive(epoch)) return;
    afdelingOptions.value = items
      .filter((item) => isAfdelingAllowed(item))
      .filter(
        (item) =>
          Boolean(estate.value) ||
          !area.value ||
          !estateCodes.size ||
          estateCodes.has(norm(item.kode_est)),
      )
      .map((item) => ({ label: item.kode_afd, value: item.kode_afd }));
  }

  // ------------------------------------------------------------------ scope & data
  const scopeLevel = computed<ScopeLevel>(() => {
    if (blokId.value) return "blok";
    if (afdeling.value) return "afdeling";
    if (estate.value) return "estate";
    if (pt.value) return "pt";
    if (area.value) return "area";
    return "semua";
  });

  function syncAppliedFromDraft() {
    applied.value = {
      grup: grup.value,
      area: area.value,
      pt: pt.value,
      estate: estate.value,
      afdeling: afdeling.value,
      blokId: blokId.value,
      ownership: ownership.value,
      bulan: bulan.value,
      tahun: tahun.value || currentYear(),
      yearToDate: yearToDate.value,
      bulanComparison: bulanComparison.value,
      tahunComparison: tahunComparison.value,
    };
  }

  /** Query GeoJSON/layer dari filter terapan (hasil Apply). Tahun selalu dikirim; bulan dan ownership hanya bila dipilih. */
  const scopeParams = computed(() => ({
    kode_grup: applied.value.grup || undefined,
    area_id: applied.value.area || undefined,
    kode_pt: applied.value.pt || undefined,
    kode_est: applied.value.estate || undefined,
    kode_afd: applied.value.afdeling || undefined,
    ownership: applied.value.ownership || undefined,
    bulan: applied.value.bulan,
    tahun: applied.value.tahun || currentYear(),
  }));

  /** GeoJSON batas blok = scopeParams + year to date + pembanding (pembanding hanya bila bulan & tahun diisi). */
  const blocksParams = computed(() => {
    const current = applied.value;
    const comparison = current.bulanComparison && current.tahunComparison;
    return {
      ...scopeParams.value,
      year_to_date: current.yearToDate ? "true" : undefined,
      bulan_comparison: comparison ? current.bulanComparison : undefined,
      tahun_comparison: comparison ? current.tahunComparison : undefined,
    };
  });

  /** Akhir rentang Year to Date: bulan berjalan pada tahun ini, Desember pada tahun lain. */
  function yearToDateEndMonth(year: string) {
    return year === currentYear() ? String(new Date().getMonth() + 1) : "12";
  }

  /** Periode cadangan popup bila blok tidak punya produksi: bulan filter, akhir YTD, atau periode default. */
  function filterPeriod() {
    const year = applied.value.tahun || currentYear();
    if (applied.value.bulan) return { bulan: applied.value.bulan, tahun: year };
    if (applied.value.yearToDate)
      return { bulan: yearToDateEndMonth(year), tahun: year };
    if (defaultPeriod.value?.tahun === year && defaultPeriod.value.bulan)
      return defaultPeriod.value;
    return { bulan: yearToDateEndMonth(year), tahun: year };
  }

  function popupPeriod(properties?: Record<string, any>) {
    return popupPeriodFromProperties(properties, filterPeriod());
  }

  const blockFeatures = computed<BlockFeature[]>(
    () => blocks.value?.features ?? [],
  );

  const visibleBlocks = computed<BlockCollection>(() => ({
    type: "FeatureCollection",
    features: blockFeatures.value,
  }));

  const ownershipOptions: Option[] = [
    { label: "inti", value: "inti" },
    { label: "plasma", value: "plasma" },
  ];

  async function loadBloks() {
    const epoch = filterEpoch;
    blokOptions.value = [];
    if (!pt.value && !estate.value && !afdeling.value && !area.value) return;
    const estateCodes = new Set(
      estateOptions.value.map((option) => norm(option.value)),
    );
    const items = await loadPage<{
      id?: number | string;
      blok_id?: string;
      kode_blok?: string;
      nama_blok?: string;
      kode_est?: string;
    }>(
      "/spatial/blok",
      {
        kode_grup: grup.value || undefined,
        kode_afd: afdeling.value || undefined,
        kode_est: estate.value || undefined,
        kode_pt: pt.value || undefined,
      },
      epoch,
    );
    if (!filterAlive(epoch)) return;
    blokOptions.value = items
      .filter(
        (item) =>
          Boolean(estate.value) ||
          Boolean(afdeling.value) ||
          !area.value ||
          !estateCodes.size ||
          estateCodes.has(norm(item.kode_est)),
      )
      .map((item) => {
        const value = String(item.blok_id ?? item.id ?? "").trim();
        const label = String(item.kode_blok ?? item.nama_blok ?? value).trim();
        return { label, value };
      })
      .filter((option) => option.value)
      .sort((a, b) => a.label.localeCompare(b.label, "id"));
  }

  /** Blok yang aktif di peta dan kartu: hasil Apply atau klik peta, bukan isian Blok yang belum di-Apply. */
  const selectedBlokId = computed(() => applied.value.blokId);
  const selectedFeature = computed<BlockFeature | null>(
    () =>
      blockFeatures.value.find(
        (f) => String(f.properties?.blok_id) === selectedBlokId.value,
      ) ?? null,
  );

  /** Isian Filter Kebun berbeda dari filter terapan, jadi perlu Apply. */
  const filterDirty = computed(() => {
    const current = applied.value;
    return (
      current.grup !== grup.value ||
      current.area !== area.value ||
      current.pt !== pt.value ||
      current.estate !== estate.value ||
      current.afdeling !== afdeling.value ||
      current.blokId !== blokId.value ||
      current.ownership !== ownership.value ||
      current.bulan !== bulan.value ||
      current.tahun !== (tahun.value || currentYear()) ||
      current.yearToDate !== yearToDate.value ||
      current.bulanComparison !== bulanComparison.value ||
      current.tahunComparison !== tahunComparison.value
    );
  });

  async function loadBlocks() {
    if (
      !isSuperAdmin.value &&
      !area.value &&
      !pt.value &&
      !estate.value &&
      !afdeling.value
    ) {
      blocks.value = { type: "FeatureCollection", features: [] };
      loadingBlocks.value = false;
      return;
    }
    const seq = ++blocksSeq;
    loadingBlocks.value = true;
    errorMessage.value = "";
    try {
      const res = await get<BlockCollection>(
        "/spatial/geojson",
        blocksParams.value,
        ["tahun"],
      );
      if (seq !== blocksSeq) return;
      const features = (Array.isArray(res?.features) ? res.features : [])
        .filter((feature) =>
          featureAllowed((feature.properties ?? {}) as Record<string, any>),
        )
        .map((feature) => ({
          ...feature,
          properties: redactProperties(
            (feature.properties ?? {}) as Record<string, any>,
          ),
        }));
      blocks.value = { type: "FeatureCollection", features };
    } catch {
      if (seq !== blocksSeq) return;
      blocks.value = { type: "FeatureCollection", features: [] };
      errorMessage.value = "Gagal memuat batas blok.";
    } finally {
      if (seq === blocksSeq) loadingBlocks.value = false;
    }
  }

  /**
   * Satu-satunya sumber kartu kanan saat satu blok dipilih.
   * Klik peta dan penerapan filter berbagi request yang sama (bulan+tahun sama tidak diulang).
   */
  async function loadSelectedDetail(id: string, bulan: string, tahun: string) {
    const key = [id, bulan, tahun, applied.value.ownership].join("|");
    if (detailFlight?.key === key) return detailFlight.promise;
    if (detailKey === key && detail.value && selectedBlokId.value === id)
      return detail.value;

    const seq = ++detailSeq;
    loadingDetail.value = true;
    detail.value = null;
    const flight: { key: string; promise: Promise<Record<string, any>> } = {
      key,
      promise: Promise.resolve({}),
    };
    flight.promise = (async () => {
      try {
        const res = await get<Record<string, any>>("/spatial/blok/detail", {
          blok_id: id,
          bulan,
          tahun,
          ownership: applied.value.ownership || undefined,
        });
        const next = redactDetail(res) ?? {};
        if (seq === detailSeq) {
          detail.value = next;
          detailKey = key;
        }
        return next;
      } catch (error) {
        if (seq === detailSeq) {
          detail.value = null;
          detailKey = "";
        }
        throw error;
      } finally {
        if (seq === detailSeq) loadingDetail.value = false;
        if (detailFlight === flight) detailFlight = null;
      }
    })();
    detailFlight = flight;
    return flight.promise;
  }

  /** Parameter GET /spatial/history: hierarki Filter Kebun yang terapan, plus blok yang sedang dipilih. */
  function historyParams(overrides?: { tahun?: string }) {
    const kodeBlok = String(
      selectedFeature.value?.properties?.kode_blok ?? "",
    ).trim();
    // Sementara hanya `tahun` yang dikirim; `bulan` di-hide dulu.
    const tahun = String(overrides?.tahun ?? applied.value.tahun ?? "").trim();
    return {
      kode_grup: applied.value.grup || undefined,
      area_id: applied.value.area || undefined,
      kode_pt: applied.value.pt || undefined,
      kode_est: applied.value.estate || undefined,
      kode_afd: applied.value.afdeling || undefined,
      blok_id: applied.value.blokId || undefined,
      kode_blok: kodeBlok || undefined,
      ownership: applied.value.ownership || undefined,
      tahun: tahun || undefined,
    };
  }

  /**
   * Tiga histori scope yang sama; histori areal statement ikut membawa /spatial/layer-data/areal.
   * `patchSaved` false saat klik peta: kartu mengikuti blok, snapshot Filter Kebun tidak ditimpa.
   * `tahun` mengikuti periode popup bila dikirim; selain itu memakai tahun Filter Kebun terapan.
   * Param `bulan` sengaja tidak dikirim ke histori. Layer areal memakainya sebagai batas snapshot.
   */
  async function loadHistories(options?: {
    patchSaved?: boolean;
    tahun?: string;
    bulan?: string;
  }) {
    const seq = ++historySeq;
    const patchSaved = options?.patchSaved !== false;
    const params = historyParams({ tahun: options?.tahun });
    const layerBulan = String(
      options?.bulan ?? applied.value.bulan ?? "",
    ).trim();
    const jobs: Array<Promise<void>> = [];

    function track<T>(
      allowed: boolean,
      table: string,
      loading: { value: boolean },
      target: { value: T | null },
      load: () => Promise<T> = () =>
        get<T>("/spatial/history", { table, ...params }),
    ) {
      if (!allowed) {
        target.value = null;
        loading.value = false;
        return;
      }
      loading.value = true;
      jobs.push(
        load()
          .then((res) => {
            if (seq !== historySeq) {
              if (patchSaved) rememberScopeHistory(table, res);
              return;
            }
            target.value = res;
            if (patchSaved) patchSavedHistories();
          })
          .catch(() => {
            if (seq === historySeq) target.value = null;
          })
          .finally(() => {
            if (seq === historySeq) loading.value = false;
          }),
      );
    }

    track(
      canViewProduction.value,
      "trx_produksi_tbs",
      loadingProduction,
      production,
    );
    // Ringkasan tanam/populasi/landuse ikut objek histori areal statement, jadi ikut tersimpan dan dipulihkan bersamanya.
    track(
      canViewAreaStatement.value,
      "trx_areal_statement",
      loadingAreaStatement,
      areaStatement,
      () =>
        Promise.all([
          get<AreaStatementHistory>("/spatial/history", {
            table: "trx_areal_statement",
            ...params,
          }),
          get<ArealSummary>("/spatial/layer-data/areal", {
            ...params,
            bulan: layerBulan || undefined,
          }).catch(
            () => null,
          ),
        ]).then(([history, ringkasan]) =>
          history ? { ...history, ringkasan_areal: ringkasan } : history,
        ),
    );
    track(
      canViewRotation.value,
      "trx_rotasi_pusingan",
      loadingRotation,
      rotation,
    );
    await Promise.all(jobs);
  }

  async function refreshScope() {
    await applyFilters();
  }

  function clearAttributeFilters() {
    ownership.value = "";
  }

  // ------------------------------------------------------------------ aksi filter
  function firstOf(options: Option[]) {
    return options[0]?.value ?? "";
  }

  /** Perusahaan dan area wajib satu nilai. Level di bawahnya boleh kosong (= semua data). */
  function resolveChoice(
    current: string,
    incoming: string,
    options: Option[],
    allowEmpty = false,
  ) {
    if (allowAllScope.value || allowEmpty) return incoming || "";
    return incoming || current || firstOf(options);
  }

  /** Periode dan pembanding sama-sama punya bulan serta tahun, jadi Year to Date dilepas. */
  function comparingFixedPeriods() {
    return Boolean(
      bulan.value &&
      tahun.value &&
      bulanComparison.value &&
      tahunComparison.value,
    );
  }

  /** Terapkan semua field form ke peta (GeoJSON) dan kartu transaksi. Panggilan lama dibatalkan. */
  async function applyFilters() {
    if (comparingFixedPeriods()) yearToDate.value = false;
    const ticket = ++applySeq;
    const epoch = filterEpoch;
    mapDrillActive = false;
    if (!filterAlive(epoch)) return;
    syncAppliedFromDraft();
    applying.value = true;
    detailKey = "";
    detailSeq += 1;
    setStatus("loading", "Sedang menerapkan filter...");
    const current = () => ticket === applySeq && filterAlive(epoch);
    try {
      await loadBlocks();
      if (!current()) return;
      if (errorMessage.value) {
        setStatus("error", errorMessage.value, 3500);
        return;
      }
      if (blokId.value) {
        const period = popupPeriod(selectedFeature.value?.properties);
        await Promise.all([
          loadSelectedDetail(blokId.value, period.bulan, period.tahun).catch(
            () => {
              detail.value = null;
            },
          ),
          loadHistories({ tahun: period.tahun, bulan: period.bulan }),
        ]);
      } else {
        detail.value = null;
        await loadHistories();
      }
      if (!current()) return;
      captureSearch();
      setStatus("success", "Selesai menerapkan filter.", 2500);
    } catch {
      if (!current()) return;
      setStatus("error", "Gagal menerapkan filter.", 3500);
    } finally {
      if (current()) applying.value = false;
    }
  }

  /** Estate yang dipilih menyaring afdeling dan blok. Kosong = semua data pada area. */
  async function refillFromEstate(epoch: number) {
    afdeling.value = "";
    blokId.value = "";
    await loadAfdelings();
    if (!filterAlive(epoch)) return;
    await loadBloks();
  }

  /** Area terpilih: muat seluruh estate, afdeling, dan blok area itu tanpa memilih satu. */
  async function refillFromArea(epoch: number) {
    estate.value = "";
    estateOptions.value = [];
    estatesByCode.value = new Map();
    afdeling.value = "";
    blokId.value = "";
    afdelingOptions.value = [];
    blokOptions.value = [];
    if (grup.value || pt.value || area.value) await loadEstates();
    if (!filterAlive(epoch)) return;
    await loadAfdelings();
    if (!filterAlive(epoch)) return;
    await loadBloks();
  }

  async function setArea(value: string) {
    const epoch = filterEpoch;
    const next = resolveChoice(area.value, value || "", areaOptions.value);
    if (next === area.value) return;
    area.value = next;
    await refillFromArea(epoch);
  }

  /** Grup opsional. Perusahaan yang hilang diganti perusahaan pertama, lalu area pertama perusahaan itu. */
  async function setGrup(value: string) {
    const epoch = filterEpoch;
    const next = value || "";
    if (next === grup.value) return;
    grup.value = next;
    await loadCompanies();
    if (!filterAlive(epoch)) return;
    if (
      !(pt.value && ptOptions.value.some((option) => option.value === pt.value))
    ) {
      pt.value = firstOf(ptOptions.value);
    }
    await loadAreas();
    if (!filterAlive(epoch)) return;
    area.value = firstOf(areaOptions.value);
    await refillFromArea(epoch);
  }

  async function setPt(value: string) {
    const epoch = filterEpoch;
    const next = resolveChoice(pt.value, value || "", ptOptions.value);
    if (next === pt.value) return;
    pt.value = next;
    await loadAreas();
    if (!filterAlive(epoch)) return;
    area.value = firstOf(areaOptions.value);
    await refillFromArea(epoch);
  }

  async function setEstate(value: string) {
    const epoch = filterEpoch;
    const next = resolveChoice(
      estate.value,
      value || "",
      estateOptions.value,
      true,
    );
    if (next === estate.value) return;
    estate.value = next;
    await refillFromEstate(epoch);
  }

  async function setAfdeling(value: string) {
    const next = resolveChoice(
      afdeling.value,
      value || "",
      afdelingOptions.value,
      true,
    );
    if (next === afdeling.value) return;
    afdeling.value = next;
    blokId.value = "";
    await loadBloks();
  }

  // Setter isian Filter Kebun hanya mengubah draft (dan opsi bertingkat); peta & kartu dimuat saat Apply.
  function setBlok(value: string) {
    const next = resolveChoice(
      blokId.value,
      value || "",
      blokOptions.value,
      true,
    );
    if (next === blokId.value) return;
    blokId.value = next;
  }

  function setOwnership(value: string) {
    ownership.value = value || "";
  }

  function setBulan(value: string) {
    bulan.value = value || "";
  }

  function setTahun(value: string) {
    tahun.value = value || currentYear();
  }

  function setYearToDate(value: boolean) {
    if (comparingFixedPeriods()) return;
    yearToDate.value = Boolean(value);
    if (yearToDate.value) bulan.value = "";
  }

  function setBulanComparison(value: string) {
    bulanComparison.value = value || "";
  }

  function setTahunComparison(value: string) {
    tahunComparison.value = value || "";
  }

  /** Klik peta: muat detail blok dan histori tiga transaksi pada scope Filter Kebun + blok ini. */
  async function selectBlock(
    value: string,
    source: "filter" | "map" = "filter",
  ) {
    if (source !== "map") {
      setBlok(value);
      return;
    }
    if (!mapDrillActive) captureSearch();
    mapDrillActive = true;
    if (!value) {
      if (!allowAllScope.value) return;
      await clearBlockSelection();
      return;
    }
    // Hanya blok yang berganti: scope tetap filter terapan, isian Filter Kebun yang belum di-Apply tidak ikut.
    blokId.value = value;
    applied.value = { ...applied.value, blokId: value };
    const period = popupPeriod(
      blockFeatures.value.find((f) => String(f.properties?.blok_id) === value)
        ?.properties,
    );
    await Promise.all([
      loadSelectedDetail(value, period.bulan, period.tahun).catch(() => {
        detail.value = null;
      }),
      loadHistories({
        patchSaved: false,
        tahun: period.tahun,
        bulan: period.bulan,
      }),
    ]);
  }

  /**
   * Detail popup plus tiga histori scope (areal statement membawa layer areal).
   * Dipakai saat buka/apply periode di popup agar `tahun` history mengikuti pilihan di dalam popup.
   * Param `bulan` tidak dikirim ke histori; layer areal memakainya sebagai batas snapshot.
   */
  async function loadPopupDetail(id: string, bulan: string, tahun: string) {
    const [next] = await Promise.all([
      loadSelectedDetail(id, bulan, tahun),
      loadHistories({ patchSaved: false, tahun, bulan }),
    ]);
    return next;
  }

  /** Tutup popup peta: kembalikan Filter Kebun dan kartu kanan ke pencarian terakhir, tanpa menggeser peta. */
  function restoreLastSearch() {
    mapDrillActive = false;
    const saved = readSavedSearch();
    detailSeq += 1;
    detailFlight = null;
    loadingDetail.value = false;
    loadingProduction.value = false;
    loadingAreaStatement.value = false;
    loadingRotation.value = false;
    if (!saved) return;
    grup.value = saved.grup ?? "";
    area.value = saved.area;
    pt.value = saved.pt;
    estate.value = saved.estate;
    afdeling.value = saved.afdeling;
    ownership.value = saved.ownership;
    bulan.value = saved.bulan ?? "";
    tahun.value = saved.tahun || currentYear();
    yearToDate.value = Boolean(saved.yearToDate);
    bulanComparison.value = saved.bulanComparison ?? "";
    tahunComparison.value = saved.tahunComparison ?? "";
    blokId.value = saved.blokId;
    syncAppliedFromDraft();
    detail.value = saved.detail;
    detailKey = "";
    production.value = saved.production;
    areaStatement.value = saved.areaStatement;
    rotation.value = saved.rotation;
  }

  /** Tutup popup peta. User biasa tetap di blok terpilih; admin boleh lepas ke semua blok. */
  async function clearBlockSelection() {
    if (!allowAllScope.value) return;
    if (!blokId.value) return;
    blokId.value = "";
    applied.value = { ...applied.value, blokId: "" };
    detailSeq += 1;
    detail.value = null;
    detailKey = "";
    loadingDetail.value = false;
  }

  function clearMap() {
    filterEpoch += 1;
    filterGeneration.value = filterEpoch;
    grup.value = "";
    area.value = "";
    pt.value = "";
    estate.value = "";
    afdeling.value = "";
    blokId.value = "";
    clearAttributeFilters();
    bulan.value = "";
    tahun.value = currentYear();
    yearToDate.value = false;
    bulanComparison.value = "";
    tahunComparison.value = "";
    applied.value = emptyApplied();
    areaOptions.value = [];
    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blokOptions.value = [];
    estatesByCode.value = new Map();
    blocks.value = { type: "FeatureCollection", features: [] };
    detail.value = null;
    production.value = null;
    areaStatement.value = null;
    rotation.value = null;
    detailKey = "";
    detailFlight = null;
    errorMessage.value = "";
    clearStatus();
    blocksSeq += 1;
    detailSeq += 1;
    historySeq += 1;
    applying.value = false;
    loadingBlocks.value = false;
    loadingDetail.value = false;
    loadingProduction.value = false;
    loadingAreaStatement.value = false;
    loadingRotation.value = false;
  }

  async function reset() {
    await init();
  }

  /** Satu perusahaan, area pertama perusahaan itu, lalu seluruh estate/afdeling/blok area tersebut. */
  async function init() {
    clearMap();
    const epoch = filterEpoch;
    await Promise.all([
      loadGroups().catch(() => {
        groupOptions.value = [];
      }),
      loadCompanies().catch(() => {
        ptOptions.value = [];
      }),
      loadDefaultPeriod(),
    ]);
    if (!filterAlive(epoch)) return;
    for (const company of ptOptions.value) {
      if (!filterAlive(epoch)) return;
      pt.value = company.value;
      await loadAreas();
      if (!filterAlive(epoch)) return;
      if (!areaOptions.value.length) continue;
      area.value = firstOf(areaOptions.value);
      await refillFromArea(epoch);
      if (!filterAlive(epoch)) return;
      await applyFilters();
      return;
    }
    if (filterAlive(epoch)) clearMap();
  }

  // ------------------------------------------------------------------ turunan untuk kartu
  const scopeLabel = computed(() => {
    const current = applied.value;
    const parts = [
      groupOptions.value.find((o) => o.value === current.grup)?.label,
      areaOptions.value.find((o) => o.value === current.area)?.label,
      ptOptions.value.find((o) => o.value === current.pt)?.label,
      estateOptions.value.find((o) => o.value === current.estate)?.label,
      current.afdeling || undefined,
      selectedFeature.value?.properties?.kode_blok,
      current.ownership || undefined,
    ].filter(Boolean);
    return parts.length ? parts.join(" / ") : "Semua wilayah";
  });

  function mapHistoriRows(rows: Array<Record<string, any>>): ProductionYear[] {
    return rows
      .map((row) => ({
        periode: row.periode ?? row.tahun,
        tahun: Number(row.tahun),
        bulan: row.bulan == null || row.bulan === "" ? null : Number(row.bulan),
        ton: Number(row.ton ?? 0),
        luas: Number(row.luas ?? 0),
        ton_ha: Number(row.ton_ha ?? 0),
        bjr: Number(row.bjr ?? 0),
        jjg_ppk: Number(row.jjg_ppk ?? 0),
        kg_ppk: Number(row.kg_ppk ?? 0),
      }))
      .filter((row) => Number.isFinite(row.tahun))
      .sort((a, b) => a.tahun - b.tahun || (a.bulan ?? 0) - (b.bulan ?? 0));
  }

  function slopeFromDetail(payload: Record<string, any> | null): SlopeShare[] {
    const totals = payload?.areal_statement?.grand_total as
      | Record<string, number>
      | undefined;
    if (!totals) return [];
    const rows = SLOPE_CLASSES.map((item) => ({
      key: item.key,
      label: item.label,
      range: item.range,
      value: Number(totals[item.detailKey] ?? 0),
    })).filter((item) => item.value > 0);
    const sum = rows.reduce((acc, item) => acc + item.value, 0);
    if (!sum) return [];
    return rows.map((item) => ({ ...item, value: (item.value / sum) * 100 }));
  }

  const viewingBlock = computed(() => Boolean(selectedBlokId.value));

  function gapSummaryOf(
    source: Record<string, any> | null | undefined,
    key: string,
  ): ProductionGapSummary | null {
    const raw = source?.[key];
    if (!raw || !Array.isArray(raw.kategori)) return null;
    const row = (item: Record<string, any>): ProductionGapCategory => ({
      kategori: String(item.kategori ?? ""),
      keterangan: String(item.keterangan ?? ""),
      luas: Number(item.luas ?? 0),
      jumlah_blok: Number(item.jumlah_blok ?? 0),
      persen_blok: Number(item.persen_blok ?? 0),
    });
    const total = raw.grand_total ?? {};
    return {
      periode: {
        tahun: raw.periode?.tahun ?? null,
        bulan: raw.periode?.bulan ?? null,
      },
      pembanding: String(raw.pembanding ?? ""),
      kategori: raw.kategori.map((item: Record<string, any>) => row(item)),
      grand_total: {
        luas: Number(total.luas ?? 0),
        jumlah_blok: Number(total.jumlah_blok ?? 0),
        persen_blok: Number(total.persen_blok ?? 0),
      },
    };
  }

  /** Kartu transaksi kanan memakai histori scope Filter Kebun, termasuk setelah satu blok diklik. */
  const productionGapBudget = computed<ProductionGapSummary | null>(() =>
    gapSummaryOf(production.value, "ringkasan_gap_budget"),
  );
  const productionGapSensus = computed<ProductionGapSummary | null>(() =>
    gapSummaryOf(production.value, "ringkasan_gap_sensus"),
  );

  const productionYears = computed<ProductionYear[]>(() =>
    mapHistoriRows(
      (production.value?.data_histori ?? []) as Array<Record<string, any>>,
    ),
  );

  const areaStatementView = computed<AreaStatementHistory | null>(
    () => areaStatement.value,
  );

  const rotationView = computed<RotationHistory | null>(() => rotation.value);

  /** Porsi kelas kemiringan. Blok terpilih memakai persentase areal statement di /blok/detail. */
  const slopeShares = computed<SlopeShare[]>(() => {
    if (viewingBlock.value && mapDrillActive)
      return slopeFromDetail(detail.value);
    if (viewingBlock.value) {
      const fromDetail = slopeFromDetail(detail.value);
      if (fromDetail.length) return fromDetail;
    }
    const ha = production.value?.slope_kemiringan_lereng_ha as
      | Record<string, number>
      | undefined;
    if (!ha) return [];
    const sum = SLOPE_CLASSES.reduce(
      (acc, c) => acc + Number(ha[c.historyKey] ?? 0),
      0,
    );
    if (!sum) return [];
    return SLOPE_CLASSES.map((c) => ({
      key: c.key,
      label: c.label,
      range: c.range,
      value: (Number(ha[c.historyKey] ?? 0) / sum) * 100,
      ha: Number(ha[c.historyKey] ?? 0),
    }));
  });

  function filterLabel(value: string, options: Option[]) {
    if (!value) return "Semua";
    return options.find((option) => option.value === value)?.label || value;
  }

  /**
   * Label grup, PT, estate, afdeling, dan blok dari filter terapan (yang sedang tampil di peta).
   * Bila opsi sudah berganti karena isian belum di-Apply, label jatuh ke kode.
   */
  const filterSummary = computed(() => {
    const current = applied.value;
    const kodeBlok = selectedFeature.value?.properties?.kode_blok;
    return {
      grup: filterLabel(current.grup, groupOptions.value),
      pt: filterLabel(current.pt, ptOptions.value),
      estate: filterLabel(current.estate, estateOptions.value),
      afdeling: filterLabel(current.afdeling, afdelingOptions.value),
      blok:
        current.blokId && kodeBlok
          ? String(kodeBlok)
          : filterLabel(current.blokId, blokOptions.value),
    };
  });

  /** Filter terapan (hasil Apply terakhir), hanya untuk dibaca komponen. */
  const appliedFilter = computed<Readonly<AppliedFilter>>(() => applied.value);

  /**
   * Periode yang benar-benar ada di GeoJSON blok yang baru dimuat.
   * Tiap feature membawa `properties.bulan` dan `properties.tahun` (batas terbaru
   * pada tahun filter). Kartu info memakai periode paling baru di koleksi itu;
   * kalau satu blok dipilih, periode feature blok itu yang dipakai.
   */
  const geojsonPeriod = computed(() => {
    const selected = readFeaturePeriod(selectedFeature.value?.properties);
    if (selected) return selected;
    let latest: { bulan: number | null; tahun: number } | null = null;
    for (const feature of blockFeatures.value) {
      const period = readFeaturePeriod(feature.properties);
      if (!period) continue;
      const newer =
        !latest ||
        period.tahun > latest.tahun ||
        (period.tahun === latest.tahun &&
          (period.bulan ?? 0) > (latest.bulan ?? 0));
      if (newer) latest = period;
    }
    return latest;
  });

  /** Ringkasan untuk bar bawah & kartu info: blok terpilih atau agregat scope. */
  const summary = computed(() => {
    const years = productionYears.value;
    const latest = years.length ? years[years.length - 1] : null;
    const filter = filterSummary.value;
    const period = geojsonPeriod.value;
    if (selectedFeature.value) {
      const p = selectedFeature.value.properties ?? {};
      const info = detail.value?.informasi_blok ?? {};
      return {
        kind: "blok" as const,
        title: String(p.kode_blok ?? ""),
        subtitle: [info.hierarki?.nama_estate ?? p.nama_estate, p.kode_afd]
          .filter(Boolean)
          .join(" · "),
        status: String(info.status_tanam ?? p.status_tanam ?? ""),
        luas: Number(info.luas_tanam ?? p.areal_statement?.luas_tanam ?? 0),
        luasKerangka: Number(
          info.luas_tanah ?? p.areal_statement?.luas_tanah ?? 0,
        ),
        pokok: Number(info.pokok ?? p.areal_statement?.total_pokok ?? 0),
        produksiTon: latest?.ton ?? null,
        produksiTahun: latest?.tahun ?? null,
        blokCount: 1,
        filter,
        geojsonPeriod: period,
      };
    }
    const features = blockFeatures.value;
    return {
      kind: "scope" as const,
      title: scopeLabel.value,
      subtitle: `${features.length.toLocaleString("id-ID")} blok berbatas di peta`,
      status: "",
      luas: features.reduce(
        (acc, f) =>
          acc + Number(f.properties?.areal_statement?.luas_tanam ?? 0),
        0,
      ),
      luasKerangka: features.reduce(
        (acc, f) =>
          acc + Number(f.properties?.areal_statement?.luas_tanah ?? 0),
        0,
      ),
      pokok: features.reduce(
        (acc, f) =>
          acc + Number(f.properties?.areal_statement?.total_pokok ?? 0),
        0,
      ),
      produksiTon: latest?.ton ?? null,
      produksiTahun: latest?.tahun ?? null,
      blokCount: features.length,
      filter,
      geojsonPeriod: period,
    };
  });

  return {
    groupOptions,
    areaOptions,
    ptOptions,
    estateOptions,
    afdelingOptions,
    blokOptions,
    ownershipOptions,
    grup,
    area,
    pt,
    estate,
    afdeling,
    blokId,
    ownership,
    bulan,
    tahun,
    yearToDate,
    bulanComparison,
    tahunComparison,
    selectedBlokId,
    filterDirty,
    appliedFilter,
    visibleBlocks,
    blocks,
    blockFeatures,
    selectedFeature,
    detail,
    production,
    areaStatement,
    rotation,
    areaStatementView,
    rotationView,
    loadingOptions,
    loadingBlocks,
    loadingDetail,
    loadingProduction,
    loadingAreaStatement,
    loadingRotation,
    errorMessage,
    applying,
    statusNotice,
    scopeLevel,
    scopeLabel,
    scopeParams,
    productionYears,
    productionGapBudget,
    productionGapSensus,
    slopeShares,
    summary,
    canViewProduction,
    canViewAreaStatement,
    canViewRotation,
    canViewLanduse,
    allowAllScope,
    filterGeneration,
    init,
    reset,
    resetFilters: clearMap,
    setGrup,
    setArea,
    setPt,
    setEstate,
    setAfdeling,
    setBlok,
    setOwnership,
    setBulan,
    setTahun,
    setYearToDate,
    setBulanComparison,
    setTahunComparison,
    popupPeriod,
    applyFilters,
    selectBlock,
    loadSelectedDetail,
    loadPopupDetail,
    loadHistories,
    clearBlockSelection,
    restoreLastSearch,
    refreshScope,
  };
});
