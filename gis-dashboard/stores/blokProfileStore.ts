import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { useAuthStore } from "~/stores/authStore";

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
  const isSuperAdmin = computed(() => (authStore.user?.roles ?? []).some((r) => r === "superadmin"));
  const aksesData = computed(() => (authStore.user?.akses_data ?? []) as AksesData[]);

  function scopeRows(): AksesData[] {
    return Array.isArray(aksesData.value) ? aksesData.value : [];
  }

  function allowedAreas(): Set<string> | null {
    if (isSuperAdmin.value) return null;
    return new Set(scopeRows().map((row) => norm(row.kode_area)).filter(Boolean));
  }

  /** Grant induk (area/PT/estate tanpa anak) mencakup level di bawahnya. Baris ganda diabaikan. */
  function isEstateAllowed(item: EstateItem): boolean {
    if (isSuperAdmin.value) return true;
    return scopeRows().some((row) => {
      if (norm(row.kode_area) !== norm(area.value)) return false;
      if (norm(row.kode_est)) return norm(row.kode_est) === norm(item.kode_est);
      if (norm(row.kode_pt)) return norm(row.kode_pt) === norm(item.kode_pt);
      return Boolean(norm(row.kode_area));
    });
  }

  function isAfdelingAllowed(kodeAfd: string): boolean {
    if (isSuperAdmin.value) return true;
    const estatePt = estatesByCode.value.get(estate.value)?.kode_pt;
    return scopeRows().some((row) => {
      if (norm(row.kode_area) !== norm(area.value)) return false;
      if (norm(row.kode_est) && norm(row.kode_est) !== norm(estate.value)) return false;
      if (!norm(row.kode_est) && norm(row.kode_pt) && norm(row.kode_pt) !== norm(estatePt)) return false;
      if (norm(row.kode_afd)) return norm(row.kode_afd) === norm(kodeAfd);
      return true;
    });
  }

  // ------------------------------------------------------------------ opsi filter
  async function loadAreas() {
    loadingOptions.value = true;
    try {
      const res = await get<{ data: Array<{ area_id: string; nama: string }> }>("/spatial/area", { limit: 100 });
      const allowed = allowedAreas();
      areaOptions.value = (res?.data ?? [])
        .filter((item) => !allowed || allowed.has(norm(item.area_id)))
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
    const seq = ++blocksSeq;
    loadingBlocks.value = true;
    errorMessage.value = "";
    try {
      const res = await get<BlockCollection>("/spatial/geojson", scopeParams.value);
      if (seq !== blocksSeq) return;
      blocks.value = res && Array.isArray(res.features) ? res : { type: "FeatureCollection", features: [] };
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
      if (seq === detailSeq) detail.value = res;
    } catch {
      if (seq === detailSeq) detail.value = null;
    } finally {
      if (seq === detailSeq) loadingDetail.value = false;
    }
  }

  async function loadProduction() {
    const seq = ++productionSeq;
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

  async function init() {
    await loadAreas();
    if (!area.value) await setArea(areaOptions.value[0]?.value ?? "");
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
    init, reset, setArea, setEstate, setAfdeling, selectBlock, refreshScope,
  };
});
