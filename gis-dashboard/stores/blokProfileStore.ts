import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { useAuthStore } from "~/stores/authStore";
import { expandTransactionGrants, grantCovers } from "~/utils/accessGrants";
import { getCurrentPopupPeriod } from "~/utils/mapBlokPopup";

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
 * Keduanya mulai dari string kosong (= semua).
 * Pilihan dibatasi `akses_data` user (superadmin bebas).
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
  let detailKey = "";
  let detailFlight: { key: string; promise: Promise<Record<string, any>> } | null = null;

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
    if (!canViewAreaStatement.value) delete next.areal_statement;
    if (!canViewProduction.value) delete next.produksi_tbs;
    if (!canViewRotation.value) delete next.rotasi_terakhir;
    return next;
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
  async function loadAreas() {
    loadingOptions.value = true;
    try {
      const res = await get<{ data: Array<{ area_id: string; nama: string }> }>("/spatial/area", { limit: 100 });
      const allowed = areaAllowance();
      areaOptions.value = (res?.data ?? [])
        .filter((item) => allowed === "all" || (allowed instanceof Set && allowed.has(norm(item.area_id))))
        .map((item) => ({ label: item.nama, value: item.area_id }));
    } finally {
      loadingOptions.value = false;
    }
  }

  async function loadCompanies() {
    ptOptions.value = [];
    if (!area.value) return;
    const res = await get<{ data: CompanyItem[] }>("/spatial/pt", { area_id: area.value, limit: 100 });
    ptOptions.value = (res?.data ?? [])
      .filter(isCompanyAllowed)
      .map((item) => ({ label: item.nama_pt || item.kode_pt, value: item.kode_pt }));
  }

  async function loadEstates() {
    estateOptions.value = [];
    estatesByCode.value = new Map();
    if (!area.value) return;
    const res = await get<{ data: EstateItem[] }>("/spatial/estate", {
      area_id: area.value, kode_pt: pt.value || undefined, limit: 100,
    });
    const items = (res?.data ?? []).filter(isEstateAllowed);
    estatesByCode.value = new Map(items.map((item) => [item.kode_est, item]));
    estateOptions.value = items.map((item) => ({ label: item.nama_estate, value: item.kode_est }));
  }

  async function loadAfdelings() {
    afdelingOptions.value = [];
    if (!estate.value) return;
    const res = await get<{ data: Array<{ kode_afd: string }> }>("/spatial/afdeling", {
      kode_est: estate.value, kode_pt: pt.value || undefined, limit: 100,
    });
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

  /** Diisi dari GeoJSON wilayah (tanpa `tahun`), supaya pilihan tidak hilang setelah filter tahun. */
  const tahunTanamCatalog = ref<Option[]>([]);

  function tahunOptionsFrom(features: BlockFeature[]): Option[] {
    const values = new Set<string>();
    for (const feature of features) {
      const raw = feature.properties?.tahun_tanam;
      if (raw === null || raw === undefined || String(raw).trim() === "") continue;
      values.add(String(raw));
    }
    return [...values]
      .sort((a, b) => Number(b) - Number(a))
      .map((value) => ({ label: value, value }));
  }

  const tahunTanamOptions = computed(() => tahunTanamCatalog.value);

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
      if (!tahunTanam.value) tahunTanamCatalog.value = tahunOptionsFrom(features);
    } catch {
      if (seq !== blocksSeq) return;
      blocks.value = { type: "FeatureCollection", features: [] };
      if (!tahunTanam.value) tahunTanamCatalog.value = [];
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
          .then((res) => { if (seq === historySeq) target.value = res; })
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
  async function setArea(value: string) {
    area.value = value || "";
    pt.value = "";
    estate.value = "";
    afdeling.value = "";
    afdelingOptions.value = [];
    clearAttributeFilters();
    await loadCompanies();
    await loadEstates();
    await refreshScope();
  }

  async function setPt(value: string) {
    pt.value = value || "";
    estate.value = "";
    afdeling.value = "";
    afdelingOptions.value = [];
    clearAttributeFilters();
    await loadEstates();
    await refreshScope();
  }

  async function setEstate(value: string) {
    estate.value = value || "";
    afdeling.value = "";
    clearAttributeFilters();
    await loadAfdelings();
    await refreshScope();
  }

  async function setAfdeling(value: string) {
    afdeling.value = value || "";
    clearAttributeFilters();
    await refreshScope();
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

  async function setOwnership(value: string) {
    ownership.value = value || "";
    detailKey = "";
    dropHiddenBlock();
    await reloadSelectedOrScope();
  }

  async function setTahunTanam(value: string) {
    tahunTanam.value = value || "";
    detailKey = "";
    await loadBlocks();
    dropHiddenBlock();
    await reloadSelectedOrScope();
  }

  async function selectBlock(value: string) {
    if (!value) {
      await clearBlockSelection();
      return;
    }
    blokId.value = value;
    const period = getCurrentPopupPeriod();
    try {
      await loadSelectedDetail(value, period.bulan, period.tahun);
    } catch {
      detail.value = null;
    }
  }

  /** Tutup popup peta: hanya field blok yang lepas. Filter wilayah di atasnya tetap. */
  async function clearBlockSelection() {
    if (!blokId.value) return;
    blokId.value = "";
    detailSeq += 1;
    detail.value = null;
    detailKey = "";
    loadingDetail.value = false;
    production.value = null;
    areaStatement.value = null;
    rotation.value = null;
    await loadHistories();
  }

  async function reset() {
    await setArea(areaOptions.value[0]?.value ?? "");
  }

  function clearMap() {
    area.value = "";
    pt.value = "";
    estate.value = "";
    afdeling.value = "";
    blokId.value = "";
    clearAttributeFilters();
    ptOptions.value = [];
    estateOptions.value = [];
    afdelingOptions.value = [];
    blocks.value = { type: "FeatureCollection", features: [] };
    tahunTanamCatalog.value = [];
    detail.value = null;
    production.value = null;
    areaStatement.value = null;
    rotation.value = null;
  }

  async function init() {
    await loadAreas();
    if (area.value || !areaOptions.value.length) {
      if (!areaOptions.value.length) clearMap();
      return;
    }
    const explicitArea = scopeRows().some((row) => norm(row.kode_area));
    if (isSuperAdmin.value || explicitArea) {
      await setArea(areaOptions.value[0]?.value ?? "");
      return;
    }
    for (const option of areaOptions.value) {
      area.value = option.value;
      pt.value = "";
      estate.value = "";
      afdeling.value = "";
      clearAttributeFilters();
      await loadCompanies();
      await loadEstates();
      if (estateOptions.value.length) {
        await refreshScope();
        return;
      }
    }
    clearMap();
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
    scopeLevel, scopeLabel, scopeParams, productionYears, slopeShares, summary,
    canViewProduction, canViewAreaStatement, canViewRotation,
    init, reset, setArea, setPt, setEstate, setAfdeling, setOwnership, setTahunTanam, selectBlock, loadSelectedDetail, clearBlockSelection, refreshScope,
  };
});
