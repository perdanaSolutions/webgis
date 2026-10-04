import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { useAuthStore } from "~/stores/authStore";
import { expandTransactionGrants, grantCovers } from "~/utils/accessGrants";
import { getCurrentPopupPeriod } from "~/utils/mapBlokPopup";
import { readBudgetCategory } from "~/utils/mapLayers";

/**
 * State halaman Blok Profile (peta layar penuh).
 *
 * Hierarki filter: Area -> Perusahaan (PT) -> Estate -> Afdeling -> Blok
 * -> Ownership -> Tahun tanam.
 * - Area s.d. Afdeling menentukan SCOPE wilayah: blok-blok yang dimuat ke peta.
 * - Blok hanya MEMILIH satu blok di dalam scope (peta tidak difilter ulang),
 *   sehingga blok tetangga tetap terlihat dan kartu kanan menampilkan data blok itu.
 * - Kartu produksi, areal statement, dan rotasi saat satu blok dipilih
 *   hanya diisi dari GET /spatial/blok/detail. /spatial/history dipakai
 *   untuk agregat scope (belum ada blok yang dipilih).
 * - Ownership menyaring blok yang sudah termuat, tanpa fetch GeoJSON.
 * - Tahun tanam memuat ulang semua GeoJSON (batas blok dan layer peta). Nilainya
 *   dikirim sebagai query `tahun`, bukan `tahun_tanam`.
 * - Opsi dropdown tahun tanam dari GET /spatial/history/tahun-tanam (bukan dari GeoJSON).
 * Keduanya mulai dari string kosong (= semua).
 * Pilihan dibatasi `akses_data` user (superadmin bebas).
 * User biasa tidak punya opsi "semua" pada Area s.d. Blok: tiap level
 * otomatis memilih satu-satunya data, atau data pertama bila lebih dari satu.
 * Opsi semua data hanya untuk superadmin@plantation.com.
 */

export type Option = { label: string; value: string };
export type ScopeLevel = "semua" | "area" | "pt" | "estate" | "afdeling" | "blok";

type CompanyItem = { id: number; kode_pt: string; nama_pt: string };
type EstateItem = { id: number; kode_est: string; nama_estate: string; kode_pt: string };
type AksesData = { kode_area?: string | null; kode_pt?: string | null; kode_est?: string | null; kode_afd?: string | null };

export type BlockFeature = GeoJSON.Feature<GeoJSON.Geometry, Record<string, any>>;
export type BlockCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, Record<string, any>>;

export type ProductionYear = {
  tahun: number; ton: number; luas: number; ton_ha: number; bjr: number; jjg_ppk: number; kg_ppk: number;
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
export type SlopeShare = { key: string; label: string; range: string; value: number; ha?: number };

export type AreaStatementGroup = {
  group_keys: {
    status_tanam?: string | null;
    bulan_tanam?: string | null;
    tahun_tanam?: number | null;
    jenis_bibit?: string | null;
    jenis_topografi?: string | null;
    jenis_tanah?: string | null;
  };
  totals: {
    count_records?: number;
    luas_tanam?: number;
    luas_tanah?: number;
    total_pokok?: number;
    sph?: number;
    pct_tanah_datar?: number;
    pct_berbukit?: number;
    pct_gelombang?: number;
    pct_curam?: number;
  };
};
export type AreaStatementHistory = {
  meta?: { label?: string; mode_akumulasi?: string; filter_applied?: { tahun_tanam?: string | null }; total_records?: number };
  grand_total?: Record<string, number>;
  data?: Array<{ tahun: number; groups?: AreaStatementGroup[] }>;
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

const SLOPE_CLASSES: Array<{ key: string; label: string; range: string; historyKey: string; detailKey: string }> = [
  { key: "datar", label: "Datar", range: "0–3%", historyKey: "0-3%", detailKey: "pct_tanah_datar" },
  { key: "gelombang", label: "Bergelombang", range: "3–8%", historyKey: "3-8%", detailKey: "pct_gelombang" },
  { key: "berbukit", label: "Berbukit", range: "8–15%", historyKey: "8-15%", detailKey: "pct_berbukit" },
  { key: "curam", label: "Curam", range: "15–25%", historyKey: "15-25%", detailKey: "pct_curam" },
  { key: "sangat", label: "Sangat curam", range: ">25%", historyKey: ">25%", detailKey: "" },
];

function norm(value: unknown) {
  return String(value ?? "").trim().toUpperCase();
}

export const useBlokProfileStore = defineStore("blokProfile", () => {
  const authStore = useAuthStore();

  const areaOptions = ref<Option[]>([]);
  const ptOptions = ref<Option[]>([]);
  const estateOptions = ref<Option[]>([]);
  const afdelingOptions = ref<Option[]>([]);
  const estatesByCode = ref(new Map<string, EstateItem>());

  const area = ref("");
  const pt = ref("");
  const estate = ref("");
  const afdeling = ref("");
  const blokId = ref("");
  const ownership = ref("");
  const tahunTanam = ref("");

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

  let blocksSeq = 0;
  let detailSeq = 0;
  let historySeq = 0;
  let filterEpoch = 0;
  const filterGeneration = ref(0);
  let detailKey = "";
  let detailFlight: { key: string; promise: Promise<Record<string, any>> } | null = null;
  /** True saat kartu kanan sedang menampilkan blok yang diklik di peta, bukan hasil Filter Kebun. */
  let mapDrillActive = false;

  const LAST_SEARCH_KEY = "blok-profile-last-search";
  type SavedSearch = {
    area: string;
    pt: string;
    estate: string;
    afdeling: string;
    blokId: string;
    ownership: string;
    tahunTanam: string;
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
    } catch { /* penyimpanan penuh atau mode privat */ }
  }

  /** Hasil Filter Kebun terakhir: isian filter + data kartu kanan. */
  function captureSearch() {
    persistSearch({
      area: area.value,
      pt: pt.value,
      estate: estate.value,
      afdeling: afdeling.value,
      blokId: blokId.value,
      ownership: ownership.value,
      tahunTanam: tahunTanam.value,
      detail: cloneData(detail.value),
      production: cloneData(production.value),
      areaStatement: cloneData(areaStatement.value),
      rotation: cloneData(rotation.value),
    });
  }

  /** Histori scope yang selesai setelah klik peta tetap masuk ke pencarian tersimpan, bukan ke tampilan blok. */
  function patchSavedHistories() {
    if (!mapDrillActive || !memorySearch) return;
    memorySearch.production = cloneData(production.value);
    memorySearch.areaStatement = cloneData(areaStatement.value);
    memorySearch.rotation = cloneData(rotation.value);
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

  async function get<T>(path: string, params: Record<string, string | number | undefined> = {}) {
    const { $api } = useNuxtApp();
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    const qs = query.toString();
    return $api<T>(`${baseUrl()}/v1${path}${qs ? `?${qs}` : ""}`);
  }

  // ------------------------------------------------------------------ hak akses
  const isSuperAdmin = computed(() => authStore.isSuperAdmin);
  /** Hanya akun ini yang boleh memilih "semua" di filter kebun (Area s.d. Blok). */
  const allowAllScope = computed(
    () => (authStore.user?.email ?? "").trim().toLowerCase() === "superadmin@plantation.com",
  );
  const aksesData = computed(() => (authStore.user?.akses_data ?? []) as AksesData[]);
  const transactionGrants = computed(() =>
    isSuperAdmin.value ? null : expandTransactionGrants(authStore.user?.akses_transaksi),
  );
  const canViewProduction = computed(() => grantCovers(transactionGrants.value, "trx.block_productions", "trx_produksi_tbs"));
  const canViewAreaStatement = computed(() => grantCovers(transactionGrants.value, "trx.area_statements", "trx_areal_statement"));
  const canViewRotation = computed(() => grantCovers(transactionGrants.value, "trx.harvest_rotations", "trx_rotasi_pusingan"));

  function scopeRows(): AksesData[] {
    return Array.isArray(aksesData.value) ? aksesData.value : [];
  }

  /** `"all"` = superadmin atau grant tanpa kode area. `"none"` = tidak ada wilayah. */
  function areaAllowance(): "all" | "none" | Set<string> {
    if (isSuperAdmin.value) return "all";
    const codes = scopeRows().map((row) => norm(row.kode_area)).filter(Boolean);
    if (codes.length) return new Set(codes);
    if (scopeRows().some((row) => norm(row.kode_pt) || norm(row.kode_est) || norm(row.kode_afd))) return "all";
    return "none";
  }

  function grantTouches(row: AksesData, place: { area?: string; pt?: string; est?: string; afd?: string }) {
    const rowArea = norm(row.kode_area);
    const rowPt = norm(row.kode_pt);
    const rowEst = norm(row.kode_est);
    const rowAfd = norm(row.kode_afd);
    if (!(rowArea || rowPt || rowEst || rowAfd)) return false;
    if (rowArea && rowArea !== norm(place.area)) return false;
    if (rowPt && place.pt !== undefined && rowPt !== norm(place.pt)) return false;
    if (rowEst && place.est !== undefined && rowEst !== norm(place.est)) return false;
    if (rowAfd && place.afd !== undefined && rowAfd !== norm(place.afd)) return false;
    return true;
  }

  function isCompanyAllowed(item: CompanyItem): boolean {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) => {
      if (norm(row.kode_area) && norm(row.kode_area) !== norm(area.value)) return false;
      if (norm(row.kode_pt)) return norm(row.kode_pt) === norm(item.kode_pt);
      if (norm(row.kode_est) || norm(row.kode_afd)) return true;
      return Boolean(norm(row.kode_area));
    });
  }

  /** Grant induk (area/PT/estate tanpa anak) mencakup level di bawahnya. Baris ganda diabaikan. */
  function isEstateAllowed(item: EstateItem): boolean {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) => {
      if (norm(row.kode_area) && norm(row.kode_area) !== norm(area.value)) return false;
      if (norm(row.kode_est)) return norm(row.kode_est) === norm(item.kode_est);
      if (norm(row.kode_pt)) return norm(row.kode_pt) === norm(item.kode_pt);
      if (norm(row.kode_afd)) return false;
      return Boolean(norm(row.kode_area));
    });
  }

  function isAfdelingAllowed(kodeAfd: string): boolean {
    if (isSuperAdmin.value) return true;
    const estatePt = estatesByCode.value.get(estate.value)?.kode_pt;
    return scopeRows().some((row) => {
      if (norm(row.kode_area) && norm(row.kode_area) !== norm(area.value)) return false;
      if (norm(row.kode_est) && norm(row.kode_est) !== norm(estate.value)) return false;
      if (!norm(row.kode_est) && norm(row.kode_pt) && norm(row.kode_pt) !== norm(estatePt)) return false;
      if (norm(row.kode_afd)) return norm(row.kode_afd) === norm(kodeAfd);
      return Boolean(norm(row.kode_area) || norm(row.kode_pt) || norm(row.kode_est));
    });
  }

  function featureAllowed(props: Record<string, any>) {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) => grantTouches(row, {
      area: props.kode_area, pt: props.kode_pt, est: props.kode_est, afd: props.kode_afd,
    }));
  }

  function redactProperties(props: Record<string, any>) {
    const next = { ...props };
    const produksi = asPlain(next.produksi_tbs);
    if (produksi) next.produksi_tbs = produksi;
    const category = readBudgetCategory(next);
    // Warna peta hanya butuh kategori, tetap disimpan meski rincian produksi disembunyikan.
    if (category) next.kategori_budget = category;
    if (!canViewAreaStatement.value) delete next.areal_statement;
    if (!canViewProduction.value) delete next.produksi_tbs;
    if (!canViewRotation.value) delete next.rotasi_terakhir;
    return next;
  }

  function asPlain(value: unknown): Record<string, any> | null {
    if (!value) return null;
    if (typeof value === "string") {
      try {
        const parsed = JSON.parse(value) as unknown;
        return parsed && typeof parsed === "object" ? parsed as Record<string, any> : null;
      } catch {
        return null;
      }
    }
    return typeof value === "object" ? value as Record<string, any> : null;
  }

  function redactDetail(payload: Record<string, any> | null) {
    if (!payload) return payload;
    const next = { ...payload };
    if (!canViewAreaStatement.value) next.areal_statement = null;
    if (!canViewProduction.value) next.produksi_tbs = null;
    if (!canViewRotation.value) next.rotasi_pusingan = null;
    return next;
  }

  // ------------------------------------------------------------------ opsi filter
  function filterAlive(epoch: number) {
    return epoch === filterEpoch;
  }

  async function loadAreas() {
    const epoch = filterEpoch;
    loadingOptions.value = true;
    try {
      const res = await get<{ data: Array<{ area_id: string; nama: string }> }>("/spatial/area", { limit: 100 });
      if (!filterAlive(epoch)) return;
      const allowed = areaAllowance();
      areaOptions.value = (res?.data ?? [])
        .filter((item) => allowed === "all" || (allowed instanceof Set && allowed.has(norm(item.area_id))))
        .map((item) => ({ label: item.nama, value: item.area_id }));
    } finally {
      if (filterAlive(epoch)) loadingOptions.value = false;
    }
  }

  async function loadCompanies() {
    const epoch = filterEpoch;
    ptOptions.value = [];
    if (!area.value) return;
    const res = await get<{ data: CompanyItem[] }>("/spatial/pt", { area_id: area.value, limit: 100 });
    if (!filterAlive(epoch)) return;
    ptOptions.value = (res?.data ?? [])
      .filter(isCompanyAllowed)
      .map((item) => ({ label: item.nama_pt || item.kode_pt, value: item.kode_pt }));
  }

  async function loadEstates() {
    const epoch = filterEpoch;
    estateOptions.value = [];
    estatesByCode.value = new Map();
    if (!area.value) return;
    const res = await get<{ data: EstateItem[] }>("/spatial/estate", {
      area_id: area.value, kode_pt: pt.value || undefined, limit: 100,
    });
    if (!filterAlive(epoch)) return;
    const items = (res?.data ?? []).filter(isEstateAllowed);
    estatesByCode.value = new Map(items.map((item) => [item.kode_est, item]));
    estateOptions.value = items.map((item) => ({ label: item.nama_estate, value: item.kode_est }));
  }

  async function loadAfdelings() {
    const epoch = filterEpoch;
    afdelingOptions.value = [];
    if (!estate.value) return;
    const res = await get<{ data: Array<{ kode_afd: string }> }>("/spatial/afdeling", {
      kode_est: estate.value, kode_pt: pt.value || undefined, limit: 100,
    });
    if (!filterAlive(epoch)) return;
    afdelingOptions.value = (res?.data ?? [])
      .filter((item) => isAfdelingAllowed(item.kode_afd))
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

  /** Wilayah saja. Ownership tidak ikut, supaya opsi tahun tanam tetap dari poligon scope. */
  const mapParams = computed(() => ({
    area_id: area.value || undefined,
    kode_pt: pt.value || undefined,
    kode_est: estate.value || undefined,
    kode_afd: afdeling.value || undefined,
  }));

  /** Query semua endpoint GeoJSON. Tahun tanam masuk sebagai `tahun`; ownership tidak dikirim. */
  const scopeParams = computed(() => ({
    ...mapParams.value,
    tahun: tahunTanam.value || undefined,
  }));

  function matchesOwnership(props: Record<string, any>) {
    return !ownership.value || norm(props.tipe_blok) === norm(ownership.value);
  }

  const scopedFeatures = computed<BlockFeature[]>(() => blocks.value?.features ?? []);

  const blockFeatures = computed<BlockFeature[]>(() =>
    scopedFeatures.value.filter((feature) => matchesOwnership((feature.properties ?? {}) as Record<string, any>)),
  );

  const visibleBlocks = computed<BlockCollection>(() => ({
    type: "FeatureCollection",
    features: blockFeatures.value,
  }));

  const ownershipOptions: Option[] = [
    { label: "inti", value: "inti" },
    { label: "plasma", value: "plasma" },
  ];

  /** Diisi dari GET /spatial/history/tahun-tanam sesuai scope wilayah aktif. */
  const tahunTanamCatalog = ref<Option[]>([]);

  const tahunTanamOptions = computed(() => tahunTanamCatalog.value);

  async function loadTahunTanamOptions() {
    const epoch = filterEpoch;
    try {
      const kodeBlok = String(selectedFeature.value?.properties?.kode_blok ?? "").trim();
      const res = await get<{ data?: Array<number | string> }>("/spatial/history/tahun-tanam", {
        area_id: area.value || undefined,
        kode_pt: pt.value || undefined,
        kode_est: estate.value || undefined,
        kode_afd: afdeling.value || undefined,
        blok_id: blokId.value || undefined,
        kode_blok: kodeBlok || undefined,
        ownership: ownership.value || undefined,
      });
      if (!filterAlive(epoch)) return;
      const years = Array.isArray(res?.data) ? res.data : [];
      tahunTanamCatalog.value = years
        .map((year) => String(year).trim())
        .filter(Boolean)
        .map((value) => ({ label: value, value }));
    } catch {
      if (!filterAlive(epoch)) return;
      tahunTanamCatalog.value = [];
    }
  }

  const blokOptions = computed<Option[]>(() =>
    [...blockFeatures.value]
      .map((f) => ({ label: String(f.properties?.kode_blok ?? ""), value: String(f.properties?.blok_id ?? "") }))
      .filter((o) => o.value)
      .sort((a, b) => a.label.localeCompare(b.label)),
  );

  const selectedFeature = computed<BlockFeature | null>(() =>
    blockFeatures.value.find((f) => String(f.properties?.blok_id) === blokId.value) ?? null,
  );

  async function loadBlocks() {
    if (!isSuperAdmin.value && !area.value && !pt.value && !estate.value && !afdeling.value) {
      blocks.value = { type: "FeatureCollection", features: [] };
      loadingBlocks.value = false;
      return;
    }
    const seq = ++blocksSeq;
    loadingBlocks.value = true;
    errorMessage.value = "";
    try {
      const res = await get<BlockCollection>("/spatial/geojson", scopeParams.value);
      if (seq !== blocksSeq) return;
      const features = (Array.isArray(res?.features) ? res.features : [])
        .filter((feature) => featureAllowed((feature.properties ?? {}) as Record<string, any>))
        .map((feature) => ({ ...feature, properties: redactProperties((feature.properties ?? {}) as Record<string, any>) }));
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
   * Klik peta dan tombol Apply berbagi request yang sama (bulan+tahun sama tidak diulang).
   */
  async function loadSelectedDetail(id: string, bulan: string, tahun: string) {
    const key = [id, bulan, tahun, ownership.value, tahunTanam.value].join("|");
    if (detailFlight?.key === key) return detailFlight.promise;
    if (detailKey === key && detail.value && blokId.value === id) return detail.value;

    const seq = ++detailSeq;
    loadingDetail.value = true;
    detail.value = null;
    const promise = (async () => {
      try {
        const res = await get<Record<string, any>>("/spatial/blok/detail", {
          blok_id: id,
          bulan,
          tahun,
          ownership: ownership.value || undefined,
          tahun_tanam: tahunTanam.value || undefined,
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
        if (detailFlight?.promise === promise) detailFlight = null;
      }
    })();
    detailFlight = { key, promise };
    return promise;
  }

  /** Parameter GET /spatial/history. Nilai kosong tidak dikirim; `tahun` kalender tidak ada di filter kebun. */
  function historyParams() {
    const kodeBlok = String(selectedFeature.value?.properties?.kode_blok ?? "").trim();
    return {
      tahun_tanam: tahunTanam.value || undefined,
      area_id: area.value || undefined,
      kode_pt: pt.value || undefined,
      kode_est: estate.value || undefined,
      kode_afd: afdeling.value || undefined,
      blok_id: blokId.value || undefined,
      kode_blok: kodeBlok || undefined,
      ownership: ownership.value || undefined,
    };
  }

  async function loadHistories() {
    const seq = ++historySeq;
    const params = historyParams();
    const jobs: Array<Promise<void>> = [];

    function track<T>(
      allowed: boolean,
      table: string,
      loading: { value: boolean },
      target: { value: T | null },
    ) {
      if (!allowed) {
        target.value = null;
        loading.value = false;
        return;
      }
      loading.value = true;
      jobs.push(
        get<T>("/spatial/history", { table, ...params })
          .then((res) => {
            if (seq !== historySeq) return;
            target.value = res;
            patchSavedHistories();
          })
          .catch(() => { if (seq === historySeq) target.value = null; })
          .finally(() => { if (seq === historySeq) loading.value = false; }),
      );
    }

    track(canViewProduction.value, "trx_produksi_tbs", loadingProduction, production);
    track(canViewAreaStatement.value, "trx_areal_statement", loadingAreaStatement, areaStatement);
    track(canViewRotation.value, "trx_rotasi_pusingan", loadingRotation, rotation);
    await Promise.all(jobs);
  }

  async function refreshScope() {
    blokId.value = "";
    detailSeq += 1;
    detail.value = null;
    detailKey = "";
    await Promise.all([loadBlocks(), loadHistories()]);
  }

  function clearAttributeFilters() {
    ownership.value = "";
    tahunTanam.value = "";
  }

  function dropHiddenBlock() {
    if (!blokId.value) return;
    const stillVisible = blockFeatures.value.some((feature) => String(feature.properties?.blok_id) === blokId.value);
    if (!stillVisible) {
      blokId.value = "";
      detail.value = null;
    }
  }

  // ------------------------------------------------------------------ aksi filter
  function firstOf(options: Option[]) {
    return options[0]?.value ?? "";
  }

  /** User biasa tidak boleh kosong: tetap di pilihan sekarang, atau data pertama. */
  function resolveChoice(current: string, incoming: string, options: Option[]) {
    if (allowAllScope.value) return incoming || "";
    return incoming || current || firstOf(options);
  }

  /**
   * Muat blok scope. User biasa yang sudah sampai afdeling langsung membuka blok pertama
   * (atau satu-satunya blok). Akun admin boleh tetap tanpa blok (= semua blok di scope).
   */
  async function focusLoadedScope() {
    const epoch = filterEpoch;
    mapDrillActive = false;
    blokId.value = "";
    detailSeq += 1;
    detail.value = null;
    detailKey = "";
    await Promise.all([loadBlocks(), loadTahunTanamOptions()]);
    if (!filterAlive(epoch)) return;
    const first = !allowAllScope.value && afdeling.value ? firstOf(blokOptions.value) : "";
    if (first) {
      await selectBlock(first);
      return;
    }
    await loadHistories();
    if (!filterAlive(epoch)) return;
    captureSearch();
  }

  async function activateArea(value: string) {
    const epoch = filterEpoch;
    area.value = value;
    pt.value = "";
    estate.value = "";
    afdeling.value = "";
    afdelingOptions.value = [];
    clearAttributeFilters();
    await loadCompanies();
    if (!filterAlive(epoch)) return;
    await loadEstates();
    if (!filterAlive(epoch)) return;
    if (!allowAllScope.value) {
      const ptsWithEstate = new Set([...estatesByCode.value.values()].map((item) => norm(item.kode_pt)));
      pt.value = ptOptions.value.find((option) => ptsWithEstate.has(norm(option.value)))?.value
        ?? firstOf(ptOptions.value);
      if (pt.value) await loadEstates();
      if (!filterAlive(epoch)) return;
      estate.value = firstOf(estateOptions.value);
      if (estate.value) await loadAfdelings();
      else afdelingOptions.value = [];
      if (!filterAlive(epoch)) return;
      afdeling.value = firstOf(afdelingOptions.value);
    }
    if (!filterAlive(epoch)) return;
    await focusLoadedScope();
  }

  async function setArea(value: string) {
    const next = resolveChoice(area.value, value || "", areaOptions.value);
    if (next === area.value) return;
    await activateArea(next);
  }

  async function setPt(value: string) {
    const epoch = filterEpoch;
    const next = resolveChoice(pt.value, value || "", ptOptions.value);
    if (next === pt.value) return;
    pt.value = next;
    estate.value = "";
    afdeling.value = "";
    afdelingOptions.value = [];
    clearAttributeFilters();
    await loadEstates();
    if (!filterAlive(epoch)) return;
    if (!allowAllScope.value) estate.value = firstOf(estateOptions.value);
    if (estate.value) await loadAfdelings();
    else afdelingOptions.value = [];
    if (!filterAlive(epoch)) return;
    if (!allowAllScope.value) afdeling.value = firstOf(afdelingOptions.value);
    await focusLoadedScope();
  }

  async function setEstate(value: string) {
    const epoch = filterEpoch;
    const next = resolveChoice(estate.value, value || "", estateOptions.value);
    if (next === estate.value) return;
    estate.value = next;
    afdeling.value = "";
    clearAttributeFilters();
    if (estate.value) await loadAfdelings();
    else afdelingOptions.value = [];
    if (!filterAlive(epoch)) return;
    if (!allowAllScope.value) afdeling.value = firstOf(afdelingOptions.value);
    await focusLoadedScope();
  }

  async function setAfdeling(value: string) {
    const next = resolveChoice(afdeling.value, value || "", afdelingOptions.value);
    if (next === afdeling.value) return;
    afdeling.value = next;
    clearAttributeFilters();
    await focusLoadedScope();
  }

  async function reloadSelectedOrScope() {
    if (!blokId.value) {
      await loadHistories();
      return;
    }
    const period = getCurrentPopupPeriod();
    try {
      await loadSelectedDetail(blokId.value, period.bulan, period.tahun);
    } catch {
      detail.value = null;
    }
  }

  async function ensureBlockForRegularUser() {
    if (allowAllScope.value || blokId.value) return false;
    const first = firstOf(blokOptions.value);
    if (!first) return false;
    await selectBlock(first);
    return true;
  }

  async function setOwnership(value: string) {
    const epoch = filterEpoch;
    mapDrillActive = false;
    ownership.value = value || "";
    detailKey = "";
    dropHiddenBlock();
    if (!filterAlive(epoch)) return;
    await loadTahunTanamOptions();
    if (!filterAlive(epoch)) return;
    if (await ensureBlockForRegularUser()) return;
    if (!filterAlive(epoch)) return;
    await reloadSelectedOrScope();
    if (!filterAlive(epoch)) return;
    captureSearch();
  }

  async function setTahunTanam(value: string) {
    const epoch = filterEpoch;
    mapDrillActive = false;
    tahunTanam.value = value || "";
    detailKey = "";
    await loadBlocks();
    if (!filterAlive(epoch)) return;
    dropHiddenBlock();
    if (await ensureBlockForRegularUser()) return;
    if (!filterAlive(epoch)) return;
    await reloadSelectedOrScope();
    if (!filterAlive(epoch)) return;
    captureSearch();
  }

  async function selectBlock(value: string, source: "filter" | "map" = "filter") {
    if (source === "map") {
      if (!mapDrillActive) captureSearch();
      mapDrillActive = true;
    } else {
      mapDrillActive = false;
    }
    if (!value) {
      if (!allowAllScope.value) {
        if (blokId.value) return;
        value = firstOf(blokOptions.value);
        if (!value) return;
      } else {
        await clearBlockSelection();
        captureSearch();
        return;
      }
    }
    blokId.value = value;
    const period = getCurrentPopupPeriod();
    try {
      await Promise.all([
        loadSelectedDetail(value, period.bulan, period.tahun),
        loadTahunTanamOptions(),
      ]);
    } catch {
      detail.value = null;
    }
    if (source !== "map") captureSearch();
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
    area.value = saved.area;
    pt.value = saved.pt;
    estate.value = saved.estate;
    afdeling.value = saved.afdeling;
    ownership.value = saved.ownership;
    tahunTanam.value = saved.tahunTanam;
    blokId.value = saved.blokId;
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
    detailSeq += 1;
    detail.value = null;
    detailKey = "";
    loadingDetail.value = false;
    production.value = null;
    areaStatement.value = null;
    rotation.value = null;
    await Promise.all([loadHistories(), loadTahunTanamOptions()]);
  }

  function clearMap() {
    filterEpoch += 1;
    filterGeneration.value = filterEpoch;
    area.value = "";
    pt.value = "";
    estate.value = "";
    afdeling.value = "";
    blokId.value = "";
    clearAttributeFilters();
    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    estatesByCode.value = new Map();
    blocks.value = { type: "FeatureCollection", features: [] };
    tahunTanamCatalog.value = [];
    detail.value = null;
    production.value = null;
    areaStatement.value = null;
    rotation.value = null;
    detailKey = "";
    detailFlight = null;
    errorMessage.value = "";
    blocksSeq += 1;
    detailSeq += 1;
    historySeq += 1;
    loadingBlocks.value = false;
    loadingDetail.value = false;
    loadingProduction.value = false;
    loadingAreaStatement.value = false;
    loadingRotation.value = false;
  }

  async function reset() {
    await init();
  }

  /** Setiap masuk halaman mulai dari field kosong, lalu isi level sesuai hak akses. */
  async function init() {
    clearMap();
    const epoch = filterEpoch;
    await Promise.all([loadAreas(), loadTahunTanamOptions()]);
    if (!filterAlive(epoch) || !areaOptions.value.length) return;
    const explicitArea = scopeRows().some((row) => norm(row.kode_area));
    if (allowAllScope.value || explicitArea) {
      await setArea(firstOf(areaOptions.value));
      return;
    }
    for (const option of areaOptions.value) {
      if (!filterAlive(epoch)) return;
      area.value = option.value;
      await loadCompanies();
      if (!filterAlive(epoch)) return;
      await loadEstates();
      if (!filterAlive(epoch)) return;
      if (ptOptions.value.length || estateOptions.value.length) {
        area.value = "";
        await setArea(option.value);
        return;
      }
    }
    if (filterAlive(epoch)) clearMap();
  }

  // ------------------------------------------------------------------ turunan untuk kartu
  const scopeLabel = computed(() => {
    const parts = [
      areaOptions.value.find((o) => o.value === area.value)?.label,
      ptOptions.value.find((o) => o.value === pt.value)?.label,
      estateOptions.value.find((o) => o.value === estate.value)?.label,
      afdeling.value || undefined,
      selectedFeature.value?.properties?.kode_blok,
      ownership.value || undefined,
      tahunTanam.value ? `TT ${tahunTanam.value}` : undefined,
    ].filter(Boolean);
    return parts.length ? parts.join(" / ") : "Semua wilayah";
  });

  function productionYearsFromDetail(payload: Record<string, any> | null): ProductionYear[] {
    const produksi = payload?.produksi_tbs;
    const tahun = Number(payload?.periode?.tahun ?? payload?.areal_statement?.tahun);
    if (!produksi || !Number.isFinite(tahun)) return [];
    const kg = Number(produksi.tbs?.aktual ?? 0);
    const luas = Number(payload?.areal_statement?.grand_total?.luas_tanam ?? 0);
    const ton = Number.isFinite(kg) ? kg / 1000 : 0;
    return [{
      tahun,
      ton,
      luas,
      ton_ha: luas > 0 ? ton / luas : 0,
      bjr: Number(produksi.bjr?.aktual ?? 0),
      jjg_ppk: Number(produksi.kpi_per_pokok?.jjg_pkk ?? 0),
      kg_ppk: Number(produksi.kpi_per_pokok?.kg_pkk ?? 0),
    }];
  }

  function areaStatementFromDetail(payload: Record<string, any> | null): AreaStatementHistory | null {
    const statement = payload?.areal_statement;
    if (!statement?.grand_total) return null;
    const tahun = Number(statement.tahun);
    return {
      meta: { label: payload?.periode?.label_periode, filter_applied: { tahun_tanam: payload?.periode?.label_periode ?? null } },
      grand_total: statement.grand_total,
      data: Number.isFinite(tahun) ? [{ tahun, groups: statement.groups ?? [] }] : [],
    };
  }

  function rotationFromDetail(payload: Record<string, any> | null): RotationHistory | null {
    if (!payload) return null;
    const kegiatan = ((payload.rotasi_pusingan?.daftar_rotasi ?? []) as Array<Record<string, any>>)
      .map((row) => ({
        tanggal: String(row.tanggal ?? ""),
        rotasi: String(row.rotasi_ke ?? "-"),
        hari: Number(row.pusingan_hari ?? 0),
        status: String(row.status_pusingan ?? ""),
        luas: Number(row.luas ?? 0),
        pokok: Number(row.pokok ?? 0),
      }));
    return { label: payload.periode?.label_periode, kegiatan, total_periode: kegiatan.length, data: [] };
  }

  function slopeFromDetail(payload: Record<string, any> | null): SlopeShare[] {
    const totals = payload?.areal_statement?.grand_total as Record<string, number> | undefined;
    if (!totals) return [];
    const rows = SLOPE_CLASSES
      .map((item) => ({ key: item.key, label: item.label, range: item.range, value: Number(totals[item.detailKey] ?? 0) }))
      .filter((item) => item.value > 0);
    const sum = rows.reduce((acc, item) => acc + item.value, 0);
    if (!sum) return [];
    return rows.map((item) => ({ ...item, value: (item.value / sum) * 100 }));
  }

  const viewingBlock = computed(() => Boolean(blokId.value));

  function gapSummaryOf(source: Record<string, any> | null | undefined, key: string): ProductionGapSummary | null {
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
      periode: { tahun: raw.periode?.tahun ?? null, bulan: raw.periode?.bulan ?? null },
      pembanding: String(raw.pembanding ?? ""),
      kategori: raw.kategori.map((item: Record<string, any>) => row(item)),
      grand_total: {
        luas: Number(total.luas ?? 0),
        jumlah_blok: Number(total.jumlah_blok ?? 0),
        persen_blok: Number(total.persen_blok ?? 0),
      },
    };
  }

  /** Rekap gap produksi. Blok terpilih mengambil salinan yang sama di /blok/detail. */
  const productionGapBudget = computed<ProductionGapSummary | null>(() =>
    viewingBlock.value
      ? gapSummaryOf(detail.value?.produksi_tbs, "ringkasan_gap_budget")
      : gapSummaryOf(production.value, "ringkasan_gap_budget"),
  );
  const productionGapSensus = computed<ProductionGapSummary | null>(() =>
    viewingBlock.value
      ? gapSummaryOf(detail.value?.produksi_tbs, "ringkasan_gap_sensus")
      : gapSummaryOf(production.value, "ringkasan_gap_sensus"),
  );

  const productionYears = computed<ProductionYear[]>(() => {
    if (viewingBlock.value) return productionYearsFromDetail(detail.value);
    return ((production.value?.data_histori ?? []) as Array<Record<string, any>>)
      .map((row) => ({
        tahun: Number(row.tahun),
        ton: Number(row.ton ?? 0),
        luas: Number(row.luas ?? 0),
        ton_ha: Number(row.ton_ha ?? 0),
        bjr: Number(row.bjr ?? 0),
        jjg_ppk: Number(row.jjg_ppk ?? 0),
        kg_ppk: Number(row.kg_ppk ?? 0),
      }))
      .filter((row) => Number.isFinite(row.tahun));
  });

  const areaStatementView = computed<AreaStatementHistory | null>(() =>
    viewingBlock.value ? areaStatementFromDetail(detail.value) : areaStatement.value,
  );

  const rotationView = computed<RotationHistory | null>(() =>
    viewingBlock.value ? rotationFromDetail(detail.value) : rotation.value,
  );

  /** Porsi kelas kemiringan. Blok terpilih memakai persentase areal statement di /blok/detail. */
  const slopeShares = computed<SlopeShare[]>(() => {
    if (viewingBlock.value) return slopeFromDetail(detail.value);
    const ha = production.value?.slope_kemiringan_lereng_ha as Record<string, number> | undefined;
    if (!ha) return [];
    const sum = SLOPE_CLASSES.reduce((acc, c) => acc + Number(ha[c.historyKey] ?? 0), 0);
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

  /** Label PT, estate, afdeling, dan blok persis mengikuti pilihan Filter Kebun. */
  const filterSummary = computed(() => ({
    pt: filterLabel(pt.value, ptOptions.value),
    estate: filterLabel(estate.value, estateOptions.value),
    afdeling: filterLabel(afdeling.value, afdelingOptions.value),
    blok: filterLabel(blokId.value, blokOptions.value),
  }));

  /** Ringkasan untuk bar bawah & kartu info: blok terpilih atau agregat scope. */
  const summary = computed(() => {
    const years = productionYears.value;
    const latest = years.length ? years[years.length - 1] : null;
    const filter = filterSummary.value;
    if (selectedFeature.value) {
      const p = selectedFeature.value.properties ?? {};
      const info = detail.value?.informasi_blok ?? {};
      const gt = detail.value?.areal_statement?.grand_total ?? {};
      return {
        kind: "blok" as const,
        title: String(p.kode_blok ?? ""),
        subtitle: [info.hierarki?.nama_estate ?? p.nama_estate, p.kode_afd].filter(Boolean).join(" · "),
        status: String(info.status_tanam ?? p.status_tanam ?? ""),
        luas: Number(gt.luas_tanam ?? p.areal_statement?.luas_tanam ?? 0),
        luasKerangka: Number(gt.luas_tanah ?? p.areal_statement?.luas_tanah ?? 0),
        pokok: Number(gt.total_pokok ?? p.areal_statement?.total_pokok ?? 0),
        produksiTon: latest?.ton ?? null,
        produksiTahun: latest?.tahun ?? null,
        blokCount: 1,
        filter,
      };
    }
    const features = blockFeatures.value;
    return {
      kind: "scope" as const,
      title: scopeLabel.value,
      subtitle: `${features.length.toLocaleString("id-ID")} blok berbatas di peta`,
      status: "",
      luas: features.reduce((acc, f) => acc + Number(f.properties?.areal_statement?.luas_tanam ?? 0), 0),
      luasKerangka: features.reduce((acc, f) => acc + Number(f.properties?.areal_statement?.luas_tanah ?? 0), 0),
      pokok: features.reduce((acc, f) => acc + Number(f.properties?.areal_statement?.total_pokok ?? 0), 0),
      produksiTon: latest?.ton ?? null,
      produksiTahun: latest?.tahun ?? null,
      blokCount: features.length,
      filter,
    };
  });

  return {
    areaOptions, ptOptions, estateOptions, afdelingOptions, blokOptions,
    ownershipOptions, tahunTanamOptions,
    area, pt, estate, afdeling, blokId, ownership, tahunTanam,
    visibleBlocks,
    blocks, blockFeatures, selectedFeature, detail, production, areaStatement, rotation,
    areaStatementView, rotationView,
    loadingOptions, loadingBlocks, loadingDetail, loadingProduction, loadingAreaStatement, loadingRotation, errorMessage,
    scopeLevel, scopeLabel, scopeParams, productionYears, productionGapBudget, productionGapSensus, slopeShares, summary,
    canViewProduction, canViewAreaStatement, canViewRotation, allowAllScope,
    filterGeneration,
    init, reset, resetFilters: clearMap, setArea, setPt, setEstate, setAfdeling, setOwnership, setTahunTanam, selectBlock, loadSelectedDetail, clearBlockSelection, restoreLastSearch, refreshScope,
  };
});
