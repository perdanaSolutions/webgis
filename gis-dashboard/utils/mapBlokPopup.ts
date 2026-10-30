import { formatDecimalId } from "./numberFormat";
import { BUDGET_GAP_COLOR, readBudgetCategory } from "./mapLayers";

export type BlokPopupMetric = {
  aktual: string;
  budget: string;
  sensus: string;
};

export type BlokPopupData = {
  area: string;
  pt: string;
  estate: string;
  afdeling: string;
  blok: string;
  tipe: string;
  tahunTanam: string;
  bulanTanam: string;
  bibit: string;
  statusTanam: string;
  topografi: string;
  jenisTanah: string;
  luasTanam: string;
  luasTanah: string;
  pokok: string;
  sph: string;
  tbs: BlokPopupMetric;
  jjg: BlokPopupMetric;
  bjr: BlokPopupMetric;
  yieldHa: BlokPopupMetric;
  gapBudget: string;
  kategoriBudget: string;
  gapSensus: string;
  kategoriSensus: string;
  bulan: string;
  tahun: string;
  blokId: string;
  kodeBlok: string;
};

export type BlokDetailResponse = {
  blok_id?: string | null;
  nama_blok?: string | null;
  kode_blok?: string | null;
  tahun_tanam?: string | number | null;
  jenis_bibit?: string | null;
  status_tanam?: string | null;
  kode_afd?: string | null;
  nama_estate?: string | null;
  kode_est?: string | null;
  nama_pt?: string | null;
  kode_pt?: string | null;
  nama_area?: string | null;
  bulan?: number | null;
  tahun?: number | null;
  luas?: number | null;
  pokok?: number | null;
  sph?: number | null;
  act_sdbi?: number | null;
  bgt_sdbi?: number | null;
  gap_sdbi?: number | null;
  janjang_aktual?: number | null;
  bjr_sdbi?: number | null;
  kg_pkk_sdbi?: number | null;
  jjg_pkk_sdbi?: number | null;
  kategori_yield?: string | null;
  [key: string]: unknown;
};

export const BULAN_POPUP_OPTIONS = [
  { label: "Januari", value: "1" },
  { label: "Februari", value: "2" },
  { label: "Maret", value: "3" },
  { label: "April", value: "4" },
  { label: "Mei", value: "5" },
  { label: "Juni", value: "6" },
  { label: "Juli", value: "7" },
  { label: "Agustus", value: "8" },
  { label: "September", value: "9" },
  { label: "Oktober", value: "10" },
  { label: "November", value: "11" },
  { label: "Desember", value: "12" },
];

type RawProperties = Record<string, string | number | null | undefined>;

function pickString(
  properties: RawProperties,
  keys: string[],
  fallback = "-",
): string {
  for (const key of keys) {
    const value = properties[key];
    if (value !== null && value !== undefined && String(value).trim() !== "") {
      return String(value);
    }
  }
  return fallback;
}

function pickNumber(
  properties: RawProperties,
  keys: string[],
  fallback = "-",
): string {
  for (const key of keys) {
    const value = properties[key];
    if (value !== null && value !== undefined && value !== "") {
      return formatNumberId(Number(value));
    }
  }
  return fallback;
}

export function formatNumberId(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return formatDecimalId(value);
}

export function formatPercentId(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return `${formatDecimalId(value)} %`;
}

/** Kategori yang mewarnai poligon: kolom V, aktual vs budget. */
function budgetCategoryLabel(properties: RawProperties): string {
  const painted = readBudgetCategory(properties as Record<string, any>);
  if (painted) return painted;
  return pickString(properties, ["kategori_budget", "kategori_yield", "Kategori_Yield", "kategori"]);
}

function categorySwatch(value: string): string {
  const color = BUDGET_GAP_COLOR[value.trim().toUpperCase()];
  if (!color || value === "-") return value;
  return `<span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:10px;height:10px;border-radius:2px;background:${color};box-shadow:inset 0 0 0 1px rgba(0,0,0,.12);"></span>${value}</span>`;
}

function getGapColor(gapValue: string): string {
  const normalized = gapValue.replace("%", "").trim().replace(",", ".");
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return "#1f2937";
  return "#638840";
}

function buildSelectOptions(
  options: Array<{ label: string; value: string }>,
  selectedValue: string,
): string {
  return options
    .map((option) => {
      const selected = option.value === selectedValue ? "selected" : "";
      return `<option value="${option.value}" ${selected}>${option.label}</option>`;
    })
    .join("");
}

function buildYearOptions(selectedYear: string): string {
  const currentYear = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, index) => {
    const year = String(currentYear - index);
    const selected = year === selectedYear ? "selected" : "";
    return `<option value="${year}" ${selected}>${year}</option>`;
  }).join("");
}

function toDisplayText(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined || String(value).trim() === "") {
    return fallback;
  }
  return String(value);
}

function toDisplayNumber(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined || value === "") return fallback;
  return formatNumberId(Number(value));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function metricOf(aktual: unknown, budget: unknown, sensus: unknown): BlokPopupMetric {
  return {
    aktual: toDisplayNumber(aktual),
    budget: toDisplayNumber(budget),
    sensus: toDisplayNumber(sensus),
  };
}

function metricFromTriplet(source: Record<string, unknown> | null | undefined): BlokPopupMetric {
  return metricOf(source?.aktual, source?.budget, source?.sensus);
}

const EMPTY_METRIC: BlokPopupMetric = { aktual: "-", budget: "-", sensus: "-" };

function displayGap(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${formatNumberId(number)} %`;
}

function resolveGapPercent(detail: BlokDetailResponse): string {
  const act = Number(detail.act_sdbi);
  const bgt = Number(detail.bgt_sdbi);

  if (Number.isFinite(act) && Number.isFinite(bgt) && bgt !== 0) {
    return formatPercentId(((act - bgt) / bgt) * 100);
  }

  const gap = Number(detail.gap_sdbi);
  if (Number.isFinite(gap)) {
    return formatPercentId(gap);
  }

  return "-";
}

function plainRecord(value: unknown): Record<string, any> | null {
  if (!value) return null;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown;
      return parsed && typeof parsed === "object" ? (parsed as Record<string, any>) : null;
    } catch {
      return null;
    }
  }
  return typeof value === "object" ? (value as Record<string, any>) : null;
}

/** "10-2026" -> { bulan: "10", tahun: "2026" }. */
function parsePeriodLabel(value: unknown): { bulan: string; tahun: string } | null {
  const match = /^(\d{1,2})-(\d{4})$/.exec(String(value ?? "").trim());
  return match ? { bulan: String(Number(match[1])), tahun: match[2]! } : null;
}

/**
 * Periode awal popup blok = bulan produksi yang dipakai mewarnai blok itu di peta
 * (`produksi_tbs.periode` dari GeoJSON), supaya warna dan isi popup sama. Bila blok
 * tidak punya data produksi, pakai `fallback` (periode filter).
 */
export function popupPeriodFromProperties(
  properties: Record<string, any> | undefined,
  fallback: { bulan: string; tahun: string },
) {
  return parsePeriodLabel(plainRecord(properties?.produksi_tbs)?.periode) ?? fallback;
}

export type PopupComparison = Pick<
  BlokPopupData,
  "tbs" | "jjg" | "bjr" | "yieldHa" | "gapBudget" | "kategoriBudget" | "gapSensus" | "kategoriSensus"
> & { periode: string };

/** Produksi dan gap periode pembanding (`produksi_tbs_comparison` dari GeoJSON), bila filter pembanding dipakai. */
export function comparisonFromProperties(properties: Record<string, any> | undefined): PopupComparison | null {
  const comparison = plainRecord(properties?.produksi_tbs_comparison);
  if (!comparison) return null;
  const start = String(comparison.periode_awal ?? "");
  const end = String(comparison.periode_akhir ?? comparison.periode ?? "");
  return {
    periode: start && start !== end ? `${start} s/d ${end}` : end,
    tbs: metricOf(comparison.tbs_aktual, comparison.tbs_budget, comparison.tbs_sensus),
    jjg: metricOf(comparison.janjang_aktual, comparison.janjang_budget, comparison.janjang_sensus),
    bjr: metricOf(comparison.bjr_aktual, comparison.bjr_budget, comparison.bjr_sensus),
    yieldHa: metricOf(comparison.y_aktual, comparison.y_budget, comparison.y_sensus),
    gapBudget: displayGap(comparison.gap_budget_pct),
    kategoriBudget: toDisplayText(comparison.kategori_budget),
    gapSensus: displayGap(comparison.gap_sensus_pct),
    kategoriSensus: toDisplayText(comparison.kategori_sensus),
  };
}

export function getCurrentPopupPeriod() {
  const now = new Date();
  return {
    bulan: String(now.getMonth() + 1),
    tahun: String(now.getFullYear()),
  };
}

export function normalizeBlokPopupData(
  properties: RawProperties,
  hierarchy: {
    area: string;
    pt: string;
    estate: string;
    afdeling: string;
  },
  overrides?: Partial<Pick<BlokPopupData, "bulan" | "tahun">>,
): BlokPopupData {
  const source = properties as Record<string, any>;
  const statement = (source.areal_statement ?? {}) as Record<string, any>;
  const prod = (source.produksi_tbs ?? {}) as Record<string, any>;
  const gapBudget = prod.gap_budget_pct ?? source.gap_sdbi ?? source.gap_sd_bi ?? source.gap;

  return {
    area: hierarchy.area || pickString(properties, ["area", "nama_area", "kode_area"]),
    pt: hierarchy.pt || pickString(properties, ["pt", "nama_pt", "kode_pt"]),
    estate: hierarchy.estate || pickString(properties, ["estate", "nama_estate", "kode_est"]),
    afdeling: hierarchy.afdeling || pickString(properties, ["afdeling", "nama_afdeling", "kode_afd", "afd_id"]),
    blok: pickString(properties, ["kode_blok", "nama_blok", "blok"]),
    tipe: pickString(properties, ["tipe_blok"]),
    tahunTanam: pickString(properties, ["tahun_tanam", "TT", "tt"]),
    bulanTanam: pickString(properties, ["bulan_tanam"]),
    bibit: pickString(properties, ["jenis_bibit", "Bibit", "bibit"]),
    statusTanam: pickString(properties, ["status_tanam"]),
    topografi: pickString(properties, ["jenis_topografi"]),
    jenisTanah: pickString(properties, ["jenis_tanah"]),
    luasTanam: pickNumber({ ...statement, ...properties }, ["luas_tanam", "luas", "ltanam", "LTanam"]),
    luasTanah: pickNumber({ ...statement, ...properties }, ["luas_tanah"]),
    pokok: pickNumber({ ...statement, ...properties }, ["pokok", "total_pokok", "Pokok"]),
    sph: pickNumber({ ...statement, ...properties }, ["sph", "SPH"]),
    tbs: metricOf(prod.tbs_aktual ?? source.tbs_aktual, prod.tbs_budget ?? source.tbs_budget, prod.tbs_sensus ?? source.tbs_sensus),
    jjg: metricOf(prod.janjang_aktual ?? source.janjang_aktual, prod.janjang_budget ?? source.jjg_budget, prod.janjang_sensus ?? source.jjg_sensus),
    bjr: metricOf(prod.bjr_aktual ?? source.bjr_aktual, prod.bjr_budget ?? source.bjr_budget, prod.bjr_sensus ?? source.bjr_sensus),
    yieldHa: metricOf(prod.y_aktual ?? source.act_sdbi, prod.y_budget ?? source.bgt_sdbi, prod.y_sensus),
    gapBudget: displayGap(gapBudget),
    kategoriBudget: toDisplayText(prod.kategori_budget, budgetCategoryLabel(properties)),
    gapSensus: displayGap(prod.gap_sensus_pct),
    kategoriSensus: toDisplayText(prod.kategori_sensus),
    bulan: overrides?.bulan ?? pickString(properties, ["bulan"], String(new Date().getMonth() + 1)),
    tahun: overrides?.tahun ?? pickString(properties, ["tahun"], String(new Date().getFullYear())),
    blokId: pickString(properties, ["blok_id", "global_id", "GlobalID"], ""),
    kodeBlok: pickString(properties, ["kode_blok"], ""),
  };
}

/**
 * Payload GET /spatial/blok/detail (`informasi_blok`) -> baris popup peta.
 * Payload datar lama tetap lewat normalizeBlokDetailResponse.
 */
export function blokPopupFromDetail(
  detail: Record<string, any> | null | undefined,
  overrides?: Partial<Pick<BlokPopupData, "bulan" | "tahun">>,
  fallbackHierarchy?: { area?: string; pt?: string; estate?: string; afdeling?: string },
): BlokPopupData {
  if (detail && !detail.informasi_blok) {
    return normalizeBlokDetailResponse(detail as BlokDetailResponse, fallbackHierarchy, overrides);
  }

  const info = detail?.informasi_blok ?? {};
  const hierarchy = info.hierarki ?? {};
  const period = detail?.periode ?? {};
  const gapBudget = info.gap_act_bgt ?? {};
  const gapSensus = info.gap_act_sns ?? {};

  return {
    area: toDisplayText(hierarchy.nama_area || hierarchy.kode_area, fallbackHierarchy?.area || "-"),
    pt: toDisplayText(hierarchy.nama_pt || hierarchy.kode_pt, fallbackHierarchy?.pt || "-"),
    estate: toDisplayText(hierarchy.nama_estate || hierarchy.kode_est, fallbackHierarchy?.estate || "-"),
    afdeling: toDisplayText(hierarchy.kode_afd || hierarchy.nama_afd, fallbackHierarchy?.afdeling || "-"),
    blok: toDisplayText(info.kode_blok || info.nama_blok),
    tipe: toDisplayText(info.tipe_blok),
    tahunTanam: toDisplayText(info.tahun_tanam),
    bulanTanam: toDisplayText(info.bulan_tanam),
    bibit: toDisplayText(info.jenis_bibit),
    statusTanam: toDisplayText(info.status_tanam),
    topografi: toDisplayText(info.jenis_topografi),
    jenisTanah: toDisplayText(info.jenis_tanah),
    luasTanam: toDisplayNumber(info.luas_tanam),
    luasTanah: toDisplayNumber(info.luas_tanah),
    pokok: toDisplayNumber(info.pokok),
    sph: toDisplayNumber(info.sph),
    tbs: metricFromTriplet(info.tbs),
    jjg: metricFromTriplet(info.jjg),
    bjr: metricFromTriplet(info.bjr),
    yieldHa: metricFromTriplet(info.yield),
    gapBudget: displayGap(gapBudget.value),
    kategoriBudget: toDisplayText(gapBudget.kategori),
    gapSensus: displayGap(gapSensus.value),
    kategoriSensus: toDisplayText(gapSensus.kategori),
    bulan: overrides?.bulan ?? toDisplayText(period.bulan, String(new Date().getMonth() + 1)),
    tahun: overrides?.tahun ?? toDisplayText(period.tahun, String(new Date().getFullYear())),
    blokId: toDisplayText(info.blok_id, ""),
    kodeBlok: toDisplayText(info.kode_blok, ""),
  };
}

/** Isi awal dari properti GeoJSON batas blok, sebelum detail periode selesai dimuat. */
export function blokPopupFromFeature(
  properties: Record<string, any>,
  overrides?: Partial<Pick<BlokPopupData, "bulan" | "tahun">>,
): BlokPopupData {
  return normalizeBlokPopupData(
    {
      ...properties,
      nama_area: properties.nama_area ?? properties.kode_area,
    },
    { area: "", pt: "", estate: "", afdeling: "" },
    overrides,
  );
}

export function normalizeBlokDetailResponse(
  detail: BlokDetailResponse,
  hierarchy?: {
    area?: string;
    pt?: string;
    estate?: string;
    afdeling?: string;
  },
  overrides?: Partial<Pick<BlokPopupData, "bulan" | "tahun">>,
): BlokPopupData {
  return {
    area: toDisplayText(detail.nama_area, hierarchy?.area || "-"),
    pt: toDisplayText(detail.nama_pt, hierarchy?.pt || "-"),
    estate: toDisplayText(detail.nama_estate, hierarchy?.estate || "-"),
    afdeling: toDisplayText(detail.kode_afd, hierarchy?.afdeling || "-"),
    blok: toDisplayText(detail.kode_blok || detail.nama_blok),
    tipe: "-",
    tahunTanam: toDisplayText(detail.tahun_tanam),
    bulanTanam: "-",
    bibit: toDisplayText(detail.jenis_bibit),
    statusTanam: toDisplayText(detail.status_tanam),
    topografi: "-",
    jenisTanah: "-",
    luasTanam: toDisplayNumber(detail.luas),
    luasTanah: "-",
    pokok: toDisplayNumber(detail.pokok),
    sph: toDisplayNumber(detail.sph),
    tbs: { ...EMPTY_METRIC },
    jjg: metricOf(detail.janjang_aktual, undefined, undefined),
    bjr: metricOf(detail.bjr_sdbi, undefined, undefined),
    yieldHa: metricOf(detail.act_sdbi, detail.bgt_sdbi, undefined),
    gapBudget: resolveGapPercent(detail),
    kategoriBudget: toDisplayText(detail.kategori_budget ?? detail.kategori_yield),
    gapSensus: "-",
    kategoriSensus: "-",
    bulan:
      overrides?.bulan ??
      toDisplayText(detail.bulan, String(new Date().getMonth() + 1)),
    tahun:
      overrides?.tahun ??
      toDisplayText(detail.tahun, String(new Date().getFullYear())),
    blokId: toDisplayText(detail.blok_id, ""),
    kodeBlok: toDisplayText(detail.kode_blok, ""),
  };
}

function popupRow(label: string, value: string, valueStyle = "", html = false) {
  const shown = html ? value : escapeHtml(value);
  return `
    <div style="display:grid;grid-template-columns:96px 8px minmax(0,1fr);gap:0;align-items:start;font-size:12px;line-height:1.45;">
      <span style="color:#6b7280;">${label}</span>
      <span style="color:#6b7280;">:</span>
      <span style="color:#111827;font-weight:600;word-break:break-word;${valueStyle}">${shown}</span>
    </div>
  `;
}

function metricTable(rows: Array<{ label: string; metric: BlokPopupMetric }>) {
  const head = `
    <div style="display:grid;grid-template-columns:52px repeat(3,minmax(0,1fr));gap:4px;font-size:10px;color:#6b7280;text-align:right;">
      <span></span><span>Aktual</span><span>Budget</span><span>Sensus</span>
    </div>
  `;
  const body = rows.map((row) => `
    <div style="display:grid;grid-template-columns:52px repeat(3,minmax(0,1fr));gap:4px;font-size:12px;line-height:1.4;">
      <span style="color:#6b7280;">${row.label}</span>
      <span style="text-align:right;font-weight:700;color:#111827;">${escapeHtml(row.metric.aktual)}</span>
      <span style="text-align:right;font-weight:700;color:#111827;">${escapeHtml(row.metric.budget)}</span>
      <span style="text-align:right;font-weight:700;color:#111827;">${escapeHtml(row.metric.sensus)}</span>
    </div>
  `).join("");
  return `<div style="display:grid;gap:4px;margin-bottom:10px;padding-top:8px;border-top:1px solid #e5e7eb;">${head}${body}</div>`;
}

function gapLine(label: string, value: string, kategori: string) {
  const swatch = categorySwatch(escapeHtml(kategori));
  return popupRow(label, `${escapeHtml(value)} · ${swatch}`, `color:${getGapColor(value)};`, true);
}

function skeletonLine(width = "100%") {
  return `<div class="map-blok-skeleton-line" style="width:${width};height:12px;border-radius:4px;background:linear-gradient(90deg,#e5e7eb 25%,#f3f4f6 50%,#e5e7eb 75%);background-size:200% 100%;animation:map-blok-skeleton-shine 1.2s ease-in-out infinite;"></div>`;
}

function skeletonRow() {
  return `
    <div style="display:grid;grid-template-columns:96px 8px minmax(0,1fr);gap:0;align-items:center;">
      ${skeletonLine("70%")}
      <span></span>
      ${skeletonLine("85%")}
    </div>
  `;
}

function buildPopupFooter(data: Pick<BlokPopupData, "bulan" | "tahun" | "blokId" | "kodeBlok">, loading = false) {
  const bulanOptions = buildSelectOptions(BULAN_POPUP_OPTIONS, data.bulan);
  const tahunOptions = buildYearOptions(data.tahun);

  return `
    <div style="border-top:1px solid #e5e7eb;padding-top:10px;display:grid;gap:8px;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <label style="display:grid;gap:4px;font-size:11px;color:#6b7280;">
          <span>Bulan</span>
          <select data-popup-bulan ${loading ? "disabled" : ""} style="width:100%;height:30px;border:1px solid #d1d5db;border-radius:6px;padding:0 8px;font-size:12px;color:#111827;background:#fff;">
            ${bulanOptions}
          </select>
        </label>
        <label style="display:grid;gap:4px;font-size:11px;color:#6b7280;">
          <span>Tahun</span>
          <select data-popup-tahun ${loading ? "disabled" : ""} style="width:100%;height:30px;border:1px solid #d1d5db;border-radius:6px;padding:0 8px;font-size:12px;color:#111827;background:#fff;">
            ${tahunOptions}
          </select>
        </label>
      </div>
      <button
        type="button"
        data-popup-apply
        data-blok-id="${data.blokId}"
        data-kode-blok="${data.kodeBlok}"
        style="width:100%;height:32px;border:none;border-radius:6px;background:${loading ? "#b4c9a0" : "#638840"};color:#fff;font-size:12px;font-weight:600;cursor:${loading ? "not-allowed" : "pointer"};"
        ${loading ? "disabled" : ""}
      >
        ${loading ? "Memuat..." : "Apply"}
      </button>
    </div>
  `;
}

export function buildBlokPopupSkeletonHtml(options: {
  bulan: string;
  tahun: string;
  blokId: string;
  kodeBlok?: string;
}) {
  return `
    <div class="map-blok-popup" style="width:100%;max-width:100%;box-sizing:border-box;padding:12px 12px 10px;font-family:inherit;color:#1f2937;">
      <div style="display:grid;gap:8px;margin-bottom:12px;">
        ${Array.from({ length: 14 }, () => skeletonRow()).join("")}
      </div>

      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:12px;">
        <div style="display:grid;gap:6px;justify-items:center;">
          ${skeletonLine("70%")}
          ${skeletonLine("50%")}
        </div>
        <div style="display:grid;gap:6px;justify-items:center;">
          ${skeletonLine("70%")}
          ${skeletonLine("50%")}
        </div>
        <div style="display:grid;gap:6px;justify-items:center;">
          ${skeletonLine("70%")}
          ${skeletonLine("50%")}
        </div>
      </div>

      <div style="display:grid;gap:8px;margin-bottom:12px;">
        ${Array.from({ length: 4 }, () => skeletonRow()).join("")}
      </div>

      ${buildPopupFooter(
        {
          bulan: options.bulan,
          tahun: options.tahun,
          blokId: options.blokId,
          kodeBlok: options.kodeBlok || "",
        },
        true,
      )}
    </div>
  `;
}

export function getBulanPopupLabel(bulan: string): string {
  return (
    BULAN_POPUP_OPTIONS.find((item) => item.value === String(Number(bulan)))
      ?.label || `Bulan ${bulan}`
  );
}

/**
 * mode LATEST_TAHUN_TANAM = bulan+tahun yang diminta tidak punya transaksi,
 * data di popup adalah transaksi paling akhir. SPESIFIK_TAHUN_TANAM = periode itu ada.
 * TIDAK_ADA_DATA = periode lebih awal dari transaksi pertama blok, tidak ada data yang bisa ditampilkan.
 */
export function periodAvailabilityNotice(
  detail: Record<string, any> | null | undefined,
  requested: { bulan: string; tahun: string },
): string | undefined {
  const mode = String(detail?.mode ?? "");
  const asked = `${getBulanPopupLabel(requested.bulan)} ${requested.tahun}`;
  if (mode === "TIDAK_ADA_DATA") return `Tidak ada data pada periode ${asked}.`;
  if (mode !== "LATEST_TAHUN_TANAM") return undefined;
  const actualMonth = detail?.periode?.bulan;
  const actualYear = detail?.periode?.tahun;
  const actual = actualMonth && actualYear
    ? `${getBulanPopupLabel(String(actualMonth))} ${actualYear}`
    : "";
  if (actual && actual !== asked) {
    return `Periode ${asked} tidak tersedia. Data yang tampil adalah transaksi terakhir (${actual}).`;
  }
  return `Periode ${asked} tidak tersedia. Data yang tampil adalah transaksi terakhir.`;
}

export function buildBlokPopupHtml(
  data: BlokPopupData,
  options?: { loading?: boolean; errorMessage?: string; notice?: string; comparison?: PopupComparison | null },
) {
  const compared = options?.comparison;
  const comparison = compared
    ? `
      <div data-popup-comparison style="margin:-4px 0 10px;padding-top:6px;border-top:1px dashed #e5e7eb;">
        <div style="margin-bottom:6px;">${popupRow("Pembanding", compared.periode)}</div>
        ${metricTable([
          { label: "TBS", metric: compared.tbs },
          { label: "JJG", metric: compared.jjg },
          { label: "BJR", metric: compared.bjr },
          { label: "Yield", metric: compared.yieldHa },
        ])}
        <div style="display:grid;gap:4px;">
          ${gapLine("Gap Budget", compared.gapBudget, compared.kategoriBudget)}
          ${gapLine("Gap Sensus", compared.gapSensus, compared.kategoriSensus)}
        </div>
      </div>`
    : "";
  const banner = options?.errorMessage
    ? `<p data-popup-alert style="margin:0 0 10px;padding:8px 10px;border-radius:6px;background:#fff7ed;border:1px solid #fdba74;color:#c2410c;font-size:12px;line-height:1.4;">${escapeHtml(options.errorMessage)}</p>`
    : options?.notice
      ? `<p data-popup-notice style="margin:0 0 10px;padding:8px 10px;border-radius:6px;background:#fffbeb;border:1px solid #fcd34d;color:#92400e;font-size:12px;line-height:1.4;">${escapeHtml(options.notice)}</p>`
      : "";

  return `
    <div class="map-blok-popup" style="width:100%;max-width:100%;box-sizing:border-box;padding:12px 12px 10px;font-family:inherit;color:#1f2937;">
      ${banner}
      <div style="display:grid;gap:4px;margin-bottom:10px;">
        ${popupRow("Area", data.area)}
        ${popupRow("PT", data.pt)}
        ${popupRow("Estate", data.estate)}
        ${popupRow("Afdeling", data.afdeling)}
        ${popupRow("Blok", data.blok)}
        ${popupRow("Tipe Blok", data.tipe)}
        ${popupRow("Tahun Tanam", data.tahunTanam)}
        ${popupRow("Bulan Tanam", data.bulanTanam)}
        ${popupRow("Jenis Bibit", data.bibit)}
        ${popupRow("Status Tanam", data.statusTanam)}
        ${popupRow("Topografi", data.topografi)}
        ${popupRow("Jenis Tanah", data.jenisTanah)}
        ${popupRow("Luas Tanam", data.luasTanam)}
        ${popupRow("Luas Tanah", data.luasTanah)}
        ${popupRow("Pokok", data.pokok)}
        ${popupRow("SPH", data.sph)}
      </div>

      ${metricTable([
        { label: "TBS", metric: data.tbs },
        { label: "JJG", metric: data.jjg },
        { label: "BJR", metric: data.bjr },
        { label: "Yield", metric: data.yieldHa },
      ])}

      <div style="display:grid;gap:4px;margin-bottom:10px;">
        ${gapLine("Gap Budget", data.gapBudget, data.kategoriBudget)}
        ${gapLine("Gap Sensus", data.gapSensus, data.kategoriSensus)}
      </div>
      ${comparison}

      ${buildPopupFooter(data, options?.loading)}
    </div>
  `;
}
