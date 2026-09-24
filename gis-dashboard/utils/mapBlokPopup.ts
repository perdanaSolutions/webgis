export type BlokPopupData = {
  area: string;
  pt: string;
  estate: string;
  afdeling: string;
  blok: string;
  tt: string;
  bibit: string;
  luas: string;
  pokok: string;
  sph: string;
  bjrSdBi: string;
  kgPkkSdBi: string;
  jjgPkkSdBi: string;
  actSdBi: string;
  bgtSdBi: string;
  gapSdBi: string;
  kategoriYield: string;
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
  return value.toLocaleString("id-ID", {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 2,
  });
}

export function formatPercentId(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return `${value.toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} %`;
}

function getGapColor(gapValue: string): string {
  const normalized = gapValue.replace("%", "").trim().replace(",", ".");
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return "#1f2937";
  return "#2B7FFF";
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
  const gapRaw = pickString(
    properties,
    ["gap_sdbi", "gap_sd_bi", "GAP_sd_Bi", "gap_sd", "gap"],
    "",
  );

  const gapNumber =
    gapRaw === "-"
      ? NaN
      : Number(String(gapRaw).replace("%", "").replace(",", "."));

  return {
    area:
      hierarchy.area ||
      pickString(properties, ["area", "kode_area", "nama_area"]),
    pt: hierarchy.pt || pickString(properties, ["pt", "nama_pt", "kode_pt"]),
    estate:
      hierarchy.estate ||
      pickString(properties, ["estate", "nama_estate", "kode_est"]),
    afdeling:
      hierarchy.afdeling ||
      pickString(properties, [
        "afdeling",
        "nama_afdeling",
        "kode_afd",
        "afd_id",
      ]),
    blok: pickString(properties, ["kode_blok", "nama_blok", "blok"]),
    tt: pickString(properties, ["tahun_tanam", "TT", "tt"]),
    bibit: pickString(properties, ["jenis_bibit", "Bibit", "bibit"]),
    luas: pickNumber(properties, ["luas", "luas_tanam", "ltanam", "LTanam"]),
    pokok: pickNumber(properties, ["pokok", "total_pokok", "Pokok"]),
    sph: pickNumber(properties, ["sph", "SPH"]),
    bjrSdBi: pickNumber(properties, [
      "bjr_sdbi",
      "bjr_sd_bi",
      "BJR_sd_Bi",
      "bjr_sensus",
      "bjr_aktual",
    ]),
    kgPkkSdBi: pickNumber(properties, [
      "kg_pkk_sdbi",
      "kg_pkk_sd_bi",
      "Kg_pkk_sd_Bi",
      "kg_pkk",
    ]),
    jjgPkkSdBi: pickNumber(properties, [
      "jjg_pkk_sdbi",
      "jjg_pkk_sd_bi",
      "Jjg_pkk_sd_Bi",
      "jjg_pkk",
    ]),
    actSdBi: pickNumber(properties, [
      "act_sdbi",
      "act_sd_bi",
      "ACT_sd_Bi",
      "tbs_aktual",
      "act_sd",
    ]),
    bgtSdBi: pickNumber(properties, [
      "bgt_sdbi",
      "bgt_sd_bi",
      "BGT_sd_Bi",
      "tbs_budget",
      "bgt_sd",
    ]),
    gapSdBi: gapRaw === "-" ? "-" : formatPercentId(gapNumber),
    kategoriYield: pickString(properties, [
      "kategori_yield",
      "Kategori_Yield",
      "kategori",
    ]),
    bulan:
      overrides?.bulan ??
      pickString(properties, ["bulan"], String(new Date().getMonth() + 1)),
    tahun:
      overrides?.tahun ??
      pickString(properties, ["tahun"], String(new Date().getFullYear())),
    blokId: pickString(properties, ["blok_id", "global_id", "GlobalID"], ""),
    kodeBlok: pickString(properties, ["kode_blok"], ""),
  };
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
    tt: toDisplayText(detail.tahun_tanam),
    bibit: toDisplayText(detail.jenis_bibit),
    luas: toDisplayNumber(detail.luas),
    pokok: toDisplayNumber(detail.pokok),
    sph: toDisplayNumber(detail.sph),
    bjrSdBi: toDisplayNumber(detail.bjr_sdbi),
    kgPkkSdBi: toDisplayNumber(detail.kg_pkk_sdbi),
    jjgPkkSdBi: toDisplayNumber(detail.jjg_pkk_sdbi),
    actSdBi: toDisplayNumber(detail.act_sdbi),
    bgtSdBi: toDisplayNumber(detail.bgt_sdbi),
    gapSdBi: resolveGapPercent(detail),
    kategoriYield: toDisplayText(detail.kategori_yield),
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

function popupRow(label: string, value: string, valueStyle = "") {
  return `
    <div style="display:grid;grid-template-columns:72px 8px minmax(0,1fr);gap:0;align-items:start;font-size:12px;line-height:1.45;">
      <span style="color:#6b7280;">${label}</span>
      <span style="color:#6b7280;">:</span>
      <span style="color:#111827;font-weight:600;word-break:break-word;${valueStyle}">${value}</span>
    </div>
  `;
}

function metricColumn(label: string, value: string) {
  return `
    <div style="min-width:0;text-align:center;">
      <div style="font-size:11px;color:#6b7280;line-height:1.3;margin-bottom:2px;">${label}</div>
      <div style="font-size:12px;font-weight:700;color:#111827;word-break:break-word;">${value}</div>
    </div>
  `;
}

function skeletonLine(width = "100%") {
  return `<div class="map-blok-skeleton-line" style="width:${width};height:12px;border-radius:4px;background:linear-gradient(90deg,#e5e7eb 25%,#f3f4f6 50%,#e5e7eb 75%);background-size:200% 100%;animation:map-blok-skeleton-shine 1.2s ease-in-out infinite;"></div>`;
}

function skeletonRow() {
  return `
    <div style="display:grid;grid-template-columns:72px 8px minmax(0,1fr);gap:0;align-items:center;">
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
        style="width:100%;height:32px;border:none;border-radius:6px;background:${loading ? "#93c5fd" : "#2B7FFF"};color:#fff;font-size:12px;font-weight:600;cursor:${loading ? "not-allowed" : "pointer"};"
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
    <div class="map-blok-popup" style="width:320px;max-width:320px;box-sizing:border-box;padding:12px 12px 10px;font-family:inherit;color:#1f2937;">
      <div style="display:grid;gap:8px;margin-bottom:12px;">
        ${Array.from({ length: 10 }, () => skeletonRow()).join("")}
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

export function buildBlokPopupHtml(
  data: BlokPopupData,
  options?: { loading?: boolean; errorMessage?: string },
) {
  const gapColor = getGapColor(data.gapSdBi);

  return `
    <div class="map-blok-popup" style="width:320px;max-width:320px;box-sizing:border-box;padding:12px 12px 10px;font-family:inherit;color:#1f2937;">
      ${
        options?.errorMessage
          ? `<p data-popup-alert style="margin:0 0 10px;padding:8px 10px;border-radius:6px;background:#fff7ed;border:1px solid #fdba74;color:#c2410c;font-size:12px;line-height:1.4;">${options.errorMessage}</p>`
          : ""
      }
      <div style="display:grid;gap:4px;margin-bottom:10px;">
        ${popupRow("Area", data.area)}
        ${popupRow("PT", data.pt)}
        ${popupRow("Estate", data.estate)}
        ${popupRow("Afdeling", data.afdeling)}
        ${popupRow("Blok", data.blok)}
        ${popupRow("TT", data.tt)}
        ${popupRow("Bibit", data.bibit)}
        ${popupRow("Luas", data.luas)}
        ${popupRow("Pokok", data.pokok)}
        ${popupRow("SPH", data.sph)}
      </div>

      <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-bottom:10px;padding-top:2px;">
        ${metricColumn("BJR(sd)Bi", data.bjrSdBi)}
        ${metricColumn("Kg/pkk (sd)Bi", data.kgPkkSdBi)}
        ${metricColumn("Jjg/pkk (sd)Bi", data.jjgPkkSdBi)}
      </div>

      <div style="display:grid;gap:4px;margin-bottom:10px;">
        ${popupRow("ACT(sd)Bi", data.actSdBi)}
        ${popupRow("BGT(sd)Bi", data.bgtSdBi)}
        ${popupRow("GAP(sd)Bi", data.gapSdBi, `color:${gapColor};`)}
        ${popupRow("Kategori Yield", data.kategoriYield)}
      </div>

      ${buildPopupFooter(data, options?.loading)}
    </div>
  `;
}
