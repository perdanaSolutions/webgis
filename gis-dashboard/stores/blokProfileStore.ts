import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { useAuthStore } from "~/stores/authStore";
import { expandTransactionGrants, grantCovers } from "~/utils/accessGrants";

/**
 * State halaman Blok Profile (peta layar penuh).
 *
 * Hierarki filter: Area -> Estate -> Afdeling -> Blok.
 * - Area/Estate/Afdeling menentukan SCOPE: blok-blok yang dimuat ke peta.
 * - Blok hanya MEMILIH satu blok di dalam scope (peta tidak difilter ulang),
 *   sehingga blok tetangga tetap terlihat dan kartu kanan menampilkan data blok itu.
 * Pilihan dibatasi `akses_data` user (superadmin bebas).
 */

export type Option = { label: string; value: string };
export type ScopeLevel = "semua" | "area" | "estate" | "afdeling" | "blok";

type EstateItem = { id: number; kode_est: string; nama_estate: string; kode_pt: string };
type AksesData = { kode_area?: string | null; kode_pt?: string | null; kode_est?: string | null; kode_afd?: string | null };

export type BlockFeature = GeoJSON.Feature<GeoJSON.Geometry, Record<string, any>>;
export type BlockCollection = GeoJSON.FeatureCollection<GeoJSON.Geometry, Record<string, any>>;

export type ProductionYear = { tahun: number; ton: number; luas: number; ton_ha: number; bjr: number };
export type SlopeShare = { key: string; label: string; range: string; value: number };

const SLOPE_CLASSES: Array<{ key: string; label: string; range: string; historyKey: string; detailKey: string }> = [
  { key: "datar", label: "Datar", range: "0–3%", historyKey: "0-3%", detailKey: "pct_tanah_datar" },
  { key: "gelombang", label: "Bergelombang", range: "3–8%", historyKey: "3-8%", detailKey: "pct_gelombang" },
  { key: "berbukit", label: "Berbukit", range: "8–15%", historyKey: "8-15%", detailKey: "pct_berbukit" },
  { key: "curam", label: "Curam", range: "15–25%", historyKey: "15-25%", detailKey: "pct_curam" },
];

function norm(value: unknown) {
  return String(value ?? "").trim().toUpperCase();
}

export const useBlokProfileStore = defineStore("blokProfile", () => {
  const authStore = useAuthStore();

  const areaOptions = ref<Option[]>([]);
  const estateOptions = ref<Option[]>([]);
  const afdelingOptions = ref<Option[]>([]);
  const estatesByCode = ref(new Map<string, EstateItem>());

  const area = ref("");
  const estate = ref("");
  const afdeling = ref("");
  const blokId = ref("");

  const blocks = ref<BlockCollection | null>(null);
  const detail = ref<Record<string, any> | null>(null);
  const production = ref<Record<string, any> | null>(null);

  const loadingOptions = ref(false);
  const loadingBlocks = ref(false);
  const loadingDetail = ref(false);
  const loadingProduction = ref(false);
  const errorMessage = ref("");

  let blocksSeq = 0;
  let detailSeq = 0;
  let productionSeq = 0;

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

  async function loadEstates() {
    estateOptions.value = [];
    estatesByCode.value = new Map();
    if (!area.value) return;
    const res = await get<{ data: EstateItem[] }>("/spatial/estate", { area_id: area.value, limit: 100 });
    const items = (res?.data ?? []).filter(isEstateAllowed);
    estatesByCode.value = new Map(items.map((item) => [item.kode_est, item]));
    estateOptions.value = items.map((item) => ({ label: item.nama_estate, value: item.kode_est }));
  }

  async function loadAfdelings() {
    afdelingOptions.value = [];
    if (!estate.value) return;
    const res = await get<{ data: Array<{ kode_afd: string }> }>("/spatial/afdeling", { kode_est: estate.value, limit: 100 });
    afdelingOptions.value = (res?.data ?? [])
      .filter((item) => isAfdelingAllowed(item.kode_afd))
      .map((item) => ({ label: item.kode_afd, value: item.kode_afd }));
  }

  // ------------------------------------------------------------------ scope & data
  const scopeLevel = computed<ScopeLevel>(() => {
    if (blokId.value) return "blok";
    if (afdeling.value) return "afdeling";
    if (estate.value) return "estate";
    if (area.value) return "area";
    return "semua";
  });

  const scopeParams = computed(() => ({
    area_id: area.value || undefined,
    kode_est: estate.value || undefined,
    kode_afd: afdeling.value || undefined,
  }));

  const blockFeatures = computed<BlockFeature[]>(() => blocks.value?.features ?? []);

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
    if (!isSuperAdmin.value && !area.value && !estate.value && !afdeling.value) {
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

  async function loadDetail() {
    const seq = ++detailSeq;
    detail.value = null;
    if (!blokId.value) return;
    loadingDetail.value = true;
    try {
      const res = await get<Record<string, any>>("/spatial/blok/detail", { blok_id: blokId.value });
      if (seq === detailSeq) detail.value = redactDetail(res);
    } catch {
      if (seq === detailSeq) detail.value = null;
    } finally {
      if (seq === detailSeq) loadingDetail.value = false;
    }
  }

  async function loadProduction() {
    const seq = ++productionSeq;
    if (!canViewProduction.value) {
      production.value = null;
      loadingProduction.value = false;
      return;
    }
    loadingProduction.value = true;
    try {
      const res = await get<Record<string, any>>("/spatial/history", {
        table: "trx_produksi_tbs",
        ...scopeParams.value,
        blok_id: blokId.value || undefined,
      });
      if (seq === productionSeq) production.value = res;
    } catch {
      if (seq === productionSeq) production.value = null;
    } finally {
      if (seq === productionSeq) loadingProduction.value = false;
    }
  }

  async function refreshScope() {
    blokId.value = "";
    detail.value = null;
    await Promise.all([loadBlocks(), loadProduction()]);
  }

  // ------------------------------------------------------------------ aksi filter
  async function setArea(value: string) {
    area.value = value || "";
    estate.value = "";
    afdeling.value = "";
    afdelingOptions.value = [];
    await loadEstates();
    await refreshScope();
  }

  async function setEstate(value: string) {
    estate.value = value || "";
    afdeling.value = "";
    await loadAfdelings();
    await refreshScope();
  }

  async function setAfdeling(value: string) {
    afdeling.value = value || "";
    await refreshScope();
  }

  async function selectBlock(value: string) {
    blokId.value = value || "";
    await Promise.all([loadDetail(), loadProduction()]);
  }

  async function reset() {
    await setArea(areaOptions.value[0]?.value ?? "");
  }

  function clearMap() {
    area.value = "";
    estate.value = "";
    afdeling.value = "";
    blokId.value = "";
    estateOptions.value = [];
    afdelingOptions.value = [];
    blocks.value = { type: "FeatureCollection", features: [] };
    detail.value = null;
    production.value = null;
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
      estate.value = "";
      afdeling.value = "";
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
      estateOptions.value.find((o) => o.value === estate.value)?.label,
      afdeling.value || undefined,
      selectedFeature.value?.properties?.kode_blok,
    ].filter(Boolean);
    return parts.length ? parts.join(" / ") : "Semua wilayah";
  });

  const productionYears = computed<ProductionYear[]>(() =>
    ((production.value?.data_histori ?? []) as Array<Record<string, any>>)
      .map((row) => ({
        tahun: Number(row.tahun),
        ton: Number(row.ton ?? 0),
        luas: Number(row.luas ?? 0),
        ton_ha: Number(row.ton_ha ?? 0),
        bjr: Number(row.bjr ?? 0),
      }))
      .filter((row) => Number.isFinite(row.tahun)),
  );

  /** Porsi kelas kemiringan (%): blok -> area statement blok; scope -> luas slope agregat. */
  const slopeShares = computed<SlopeShare[]>(() => {
    const totals = detail.value?.areal_statement?.grand_total;
    if (blokId.value && totals) {
      return SLOPE_CLASSES.map((c) => ({ key: c.key, label: c.label, range: c.range, value: Number(totals[c.detailKey] ?? 0) }));
    }
    const ha = production.value?.slope_kemiringan_lereng_ha as Record<string, number> | undefined;
    if (!ha) return [];
    const sum = SLOPE_CLASSES.reduce((acc, c) => acc + Number(ha[c.historyKey] ?? 0), 0);
    if (!sum) return [];
    return SLOPE_CLASSES.map((c) => ({
      key: c.key, label: c.label, range: c.range, value: (Number(ha[c.historyKey] ?? 0) / sum) * 100,
    }));
  });

  /** Ringkasan untuk bar bawah & kartu info: blok terpilih atau agregat scope. */
  const summary = computed(() => {
    const years = productionYears.value;
    const latest = years.length ? years[years.length - 1] : null;
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
        pokok: Number(gt.total_pokok ?? p.areal_statement?.total_pokok ?? 0),
        produksiTon: latest?.ton ?? null,
        produksiTahun: latest?.tahun ?? null,
        blokCount: 1,
      };
    }
    const features = blockFeatures.value;
    return {
      kind: "scope" as const,
      title: scopeLabel.value,
      subtitle: `${features.length.toLocaleString("id-ID")} blok berbatas di peta`,
      status: "",
      luas: features.reduce((acc, f) => acc + Number(f.properties?.areal_statement?.luas_tanam ?? 0), 0),
      pokok: features.reduce((acc, f) => acc + Number(f.properties?.areal_statement?.total_pokok ?? 0), 0),
      produksiTon: latest?.ton ?? null,
      produksiTahun: latest?.tahun ?? null,
      blokCount: features.length,
    };
  });

  return {
    areaOptions, estateOptions, afdelingOptions, blokOptions,
    area, estate, afdeling, blokId,
    blocks, blockFeatures, selectedFeature, detail, production,
    loadingOptions, loadingBlocks, loadingDetail, loadingProduction, errorMessage,
    scopeLevel, scopeLabel, scopeParams, productionYears, slopeShares, summary,
    canViewProduction, canViewAreaStatement,
    init, reset, setArea, setEstate, setAfdeling, selectBlock, refreshScope,
  };
});
