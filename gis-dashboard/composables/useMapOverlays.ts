import { computed, ref, watch, type Ref } from "vue";

import { useAuthStore } from "~/stores/authStore";
import { expandTransactionGrants } from "~/utils/accessGrants";
import { getOverlayLegend, getOverlayStyle, type LegendItem, type OverlayStyle } from "~/utils/mapLayers";

/**
 * Layer data tambahan di atas peta (TPH, sawit, landuse, slope, jalan, ...).
 * Daftar diambil dari katalog backend, ditambah layer turunan "Pokok Kuning"
 * (subset sawit berkategori Kuning). Data dimuat hanya untuk layer yang aktif
 * dan dimuat ulang saat scope wilayah berubah.
 */

export type OverlayLayer = {
  code: string;
  name: string;
  geometryType: string;
  style: OverlayStyle;
  legend: LegendItem[];
  endpoint: string;
  /** layer turunan: ambil data dari endpoint layer lain lalu saring */
  filter?: (properties: Record<string, any>) => boolean;
  enabled: boolean;
  loading: boolean;
  count: number | null;
  period: string;
  error: string;
  data: GeoJSON.FeatureCollection | null;
};

type CatalogItem = {
  kode: string;
  nama: string;
  table_name?: string;
  geometry_type: string;
  endpoints: Record<string, string> | null;
};

const ORDER = ["tph", "sawit", "kuning", "landuse", "slope", "jalan", "jembatan"];
const LABELS: Record<string, string> = {
  tph: "TPH", sawit: "Pokok Sawit", kuning: "Pokok Kuning", landuse: "Landuse", slope: "Slope",
  jalan: "Jalan", jembatan: "Jembatan",
};
const DEFAULT_ON = new Set(["tph", "sawit", "landuse"]);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

function rank(code: string) {
  const i = ORDER.indexOf(code);
  return i < 0 ? ORDER.length : i;
}

export function useMapOverlays(scopeParams: Ref<Record<string, string | undefined>>) {
  const authStore = useAuthStore();
  const layers = ref<OverlayLayer[]>([]);
  const sequence = new Map<string, number>();

  function transactionAllowed(item: CatalogItem) {
    if (authStore.isSuperAdmin) return true;
    const allowed = expandTransactionGrants(authStore.user?.akses_transaksi);
    if (!allowed.size) return false;
    return [item.kode, item.table_name, item.nama]
      .map((value) => String(value ?? "").trim().toLowerCase())
      .some((value) => value && allowed.has(value));
  }

  function baseUrl() {
    return useRuntimeConfig().public.apiBaseUrlPython as string;
  }

  async function loadCatalog() {
    const { $api } = useNuxtApp();
    const catalog = await $api<CatalogItem[]>(`${baseUrl()}/v1/spatial/geo/catalog`).catch(() => []);
    const seen = new Set<string>();
    const items: OverlayLayer[] = (Array.isArray(catalog) ? catalog : [])
      .filter((item) => {
        const key = String(item.kode ?? "").trim().toLowerCase();
        if (!key || key === "blok" || !item.endpoints?.geojson || seen.has(key)) return false;
        if (!transactionAllowed(item)) return false;
        seen.add(key);
        return true;
      })
      .map((item, index) => {
        const style = getOverlayStyle(item.kode, index);
        return {
          code: item.kode, name: LABELS[item.kode] ?? item.nama, geometryType: item.geometry_type, style,
          legend: getOverlayLegend(style), endpoint: item.endpoints!.geojson!, enabled: DEFAULT_ON.has(item.kode),
          loading: false, count: null, period: "", error: "", data: null,
        };
      });

    const sawit = items.find((item) => item.code === "sawit");
    if (sawit) {
      const style: OverlayStyle = { ...getOverlayStyle("sawit"), colors: undefined, colorBy: undefined, defaultColor: "#eab308", radius: 4 };
      items.push({
        ...sawit, code: "kuning", name: LABELS.kuning!, style, legend: [], enabled: false, data: null,
        filter: (p) => String(p.kategori ?? "").toLowerCase() === "kuning",
      });
    }
    layers.value = items.sort((a, b) => rank(a.code) - rank(b.code));
    await Promise.all(layers.value.filter((l) => l.enabled).map(load));
  }

  async function load(layer: OverlayLayer) {
    const seq = (sequence.get(layer.code) ?? 0) + 1;
    sequence.set(layer.code, seq);
    layer.loading = true;
    layer.error = "";
    try {
      const { $api } = useNuxtApp();
      const query = new URLSearchParams();
      const params = scopeParams.value;
      Object.entries(params).forEach(([k, v]) => v && query.set(k, v));
      const qs = query.toString();
      const res = await $api<GeoJSON.FeatureCollection>(`${baseUrl()}/v1/spatial${layer.endpoint}${qs ? `?${qs}` : ""}`);
      if (sequence.get(layer.code) !== seq || !layer.enabled) return;
      let features = Array.isArray(res?.features) ? res.features : [];
      if (layer.filter) features = features.filter((f) => layer.filter!((f.properties ?? {}) as Record<string, any>));
      layer.data = { type: "FeatureCollection", features };
      layer.count = features.length;
      const first = features[0]?.properties as Record<string, any> | undefined;
      layer.period = first?.bulan && first?.tahun ? `${MONTHS[Number(first.bulan) - 1] ?? first.bulan} ${first.tahun}` : "";
    } catch {
      if (sequence.get(layer.code) !== seq) return;
      layer.data = null;
      layer.count = null;
      layer.error = "Gagal memuat";
    } finally {
      if (sequence.get(layer.code) === seq) layer.loading = false;
    }
  }

  function toggle(code: string) {
    const layer = layers.value.find((l) => l.code === code);
    if (!layer) return;
    layer.enabled = !layer.enabled;
    if (layer.enabled) {
      void load(layer);
    } else {
      sequence.set(code, (sequence.get(code) ?? 0) + 1); // batalkan request berjalan
      layer.loading = false;
      layer.data = null;
    }
  }

  function reloadEnabled() {
    layers.value.filter((l) => l.enabled).forEach((l) => void load(l));
  }

  watch(scopeParams, reloadEnabled, { deep: true });

  const activeCount = computed(() => layers.value.filter((l) => l.enabled).length);

  return { layers, activeCount, loadCatalog, toggle, reloadEnabled };
}
