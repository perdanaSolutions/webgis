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
  return Array.from({ length: 11 }, (_, index) => {
    const year = String(currentYear - index);
    const selected = year === selectedYear ? "selected" : "";
    return `<option value="${year}" ${selected}>${year}</option>`;
  }).join("");
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
  const gapRaw = pickString(properties, [
    "gap_sd_bi",
    "GAP_sd_Bi",
    "gap_sd",
    "gap",
  ], "");

  const gapNumber = gapRaw === "-"
    ? NaN
    : Number(String(gapRaw).replace("%", "").replace(",", "."));

  return {
    area: hierarchy.area || pickString(properties, ["area", "kode_area", "nama_area"]),
    pt: hierarchy.pt || pickString(properties, ["pt", "nama_pt", "kode_pt"]),
    estate: hierarchy.estate || pickString(properties, ["estate", "nama_estate", "kode_est"]),
    afdeling: hierarchy.afdeling || pickString(properties, ["afdeling", "nama_afdeling", "kode_afd", "afd_id"]),
    blok: pickString(properties, ["kode_blok", "nama_blok", "blok"]),
    tt: pickString(properties, ["tahun_tanam", "TT", "tt"]),
    bibit: pickString(properties, ["jenis_bibit", "Bibit", "bibit"]),
    luas: pickNumber(properties, ["luas", "luas_tanam", "ltanam", "LTanam"]),
    pokok: pickNumber(properties, ["pokok", "total_pokok", "Pokok"]),
    sph: pickNumber(properties, ["sph", "SPH"]),
    bjrSdBi: pickNumber(properties, ["bjr_sd_bi", "BJR_sd_Bi", "bjr_sensus", "bjr_aktual"]),
    kgPkkSdBi: pickNumber(properties, ["kg_pkk_sd_bi", "Kg_pkk_sd_Bi", "kg_pkk"]),
    jjgPkkSdBi: pickNumber(properties, ["jjg_pkk_sd_bi", "Jjg_pkk_sd_Bi", "jjg_pkk"]),
    actSdBi: pickNumber(properties, ["act_sd_bi", "ACT_sd_Bi", "tbs_aktual", "act_sd"]),
    bgtSdBi: pickNumber(properties, ["bgt_sd_bi", "BGT_sd_Bi", "tbs_budget", "bgt_sd"]),
    gapSdBi: gapRaw === "-" ? "-" : formatPercentId(gapNumber),
    kategoriYield: pickString(properties, ["kategori_yield", "Kategori_Yield", "kategori"]),
    bulan: overrides?.bulan
      ?? pickString(properties, ["bulan"], String(new Date().getMonth() + 1)),
    tahun: overrides?.tahun
      ?? pickString(properties, ["tahun"], String(new Date().getFullYear())),
    blokId: pickString(properties, ["blok_id", "global_id", "GlobalID"], ""),
    kodeBlok: pickString(properties, ["kode_blok"], ""),
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

export function buildBlokPopupHtml(
  data: BlokPopupData,
  options?: { loading?: boolean },
) {
  const gapColor = getGapColor(data.gapSdBi);
  const bulanOptions = buildSelectOptions(BULAN_POPUP_OPTIONS, data.bulan);
  const tahunOptions = buildYearOptions(data.tahun);

  return `
    <div class="map-blok-popup" style="width:320px;max-width:320px;box-sizing:border-box;padding:12px 12px 10px;font-family:inherit;color:#1f2937;">
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

      <div style="border-top:1px solid #e5e7eb;padding-top:10px;display:grid;gap:8px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
          <label style="display:grid;gap:4px;font-size:11px;color:#6b7280;">
            <span>Bulan</span>
            <select data-popup-bulan style="width:100%;height:30px;border:1px solid #d1d5db;border-radius:6px;padding:0 8px;font-size:12px;color:#111827;background:#fff;">
              ${bulanOptions}
            </select>
          </label>
          <label style="display:grid;gap:4px;font-size:11px;color:#6b7280;">
            <span>Tahun</span>
            <select data-popup-tahun style="width:100%;height:30px;border:1px solid #d1d5db;border-radius:6px;padding:0 8px;font-size:12px;color:#111827;background:#fff;">
              ${tahunOptions}
            </select>
          </label>
        </div>
        <button
          type="button"
          data-popup-apply
          data-blok-id="${data.blokId}"
          data-kode-blok="${data.kodeBlok}"
          style="width:100%;height:32px;border:none;border-radius:6px;background:#2B7FFF;color:#fff;font-size:12px;font-weight:600;cursor:pointer;"
          ${options?.loading ? "disabled" : ""}
        >
          ${options?.loading ? "Memuat..." : "Apply"}
        </button>
      </div>
    </div>
  `;
}
