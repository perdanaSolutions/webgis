/**
 * Grafik Produksi TBS per Grup / Area / Estate (GET /spatial/produksi/grafik-grup).
 * Bar hijau = aktual (ton); garis = budget: kuning bila aktual sudah mencapai/melewati budget, merah bila belum.
 * Aktual tahun lalu hanya di tooltip.
 */
import { formatDecimalId } from "./numberFormat";

export type ProductionGroupItem = {
  kode: string | null;
  nama: string;
  nama_lengkap?: string | null;
  aktual_ton: number;
  budget_ton: number;
  aktual_tahun_lalu_ton: number;
  aktual_ton_ha: number | null;
  budget_ton_ha: number | null;
  var_budget_ton: number;
  var_budget_pct: number | null;
  var_tahun_lalu_ton: number;
  var_tahun_lalu_pct: number | null;
  luas_tanam: number;
  rut: number | null;
};

export type ProductionGroupPeriod = {
  periode_awal: string;
  periode_akhir: string;
  year_to_date: boolean;
  tahun_lalu_awal: string;
  tahun_lalu_akhir: string;
};

export type ProductionGroupChart = {
  periode: ProductionGroupPeriod | null;
  group_produksi_ton: {
    total: ProductionGroupItem | null;
    by_group: ProductionGroupItem[];
    by_area: ProductionGroupItem[];
    by_estate: ProductionGroupItem[];
  };
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** "10-2026" -> "Okt 2026". */
export function monthLabel(value: string | null | undefined): string {
  const [m, y] = String(value ?? "").split("-");
  const month = Number(m);
  return month >= 1 && month <= 12 && y ? `${MONTHS[month - 1]} ${y}` : String(value ?? "");
}

/** Judul rentang, mis. "Year to Date Jan s/d Okt 2026" atau "Okt 2026". */
export function periodTitle(periode: ProductionGroupPeriod | null | undefined): string {
  if (!periode) return "";
  const end = monthLabel(periode.periode_akhir);
  if (!periode.year_to_date) return end;
  const start = monthLabel(periode.periode_awal).split(" ")[0];
  return `Year to Date ${start} s/d ${end}`;
}

/** Nilai terbesar (aktual, budget) sebagai batas skala; minimal 1 agar tidak membagi nol. */
export function scaleMax(items: ProductionGroupItem[]): number {
  return Math.max(1, ...items.flatMap((i) => [i.aktual_ton, i.budget_ton].map((v) => (Number.isFinite(v) ? v : 0))));
}

/**
 * Status garis budget: true = aktual sudah mencapai/melewati budget (garis kuning), false = belum (garis merah),
 * null = tidak ada budget (tanpa garis). Dibandingkan dengan angka asli, bukan yang dibulatkan.
 */
export function budgetReached(item: ProductionGroupItem): boolean | null {
  if (!Number.isFinite(item.budget_ton) || item.budget_ton <= 0) return null;
  return (Number.isFinite(item.aktual_ton) ? item.aktual_ton : 0) >= item.budget_ton;
}

/** Posisi persen 0–100 pada skala. */
export function pctOf(value: number, max: number): number {
  if (!Number.isFinite(value) || value <= 0 || max <= 0) return 0;
  return Math.min(100, (value / max) * 100);
}

/** Ton dibulatkan ke satuan dengan pemisah ribuan: 1433263,4 -> "1.433.263". */
export function compactTon(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return formatDecimalId(Math.round(value));
}

export type TipRow = { label: string; value: string; tone?: "good" | "bad" };

function signed(value: number | null, suffix = ""): string {
  if (value === null || !Number.isFinite(value)) return "-";
  return `${formatDecimalId(value)}${suffix}`;
}

function tone(value: number | null): TipRow["tone"] {
  if (value === null || !Number.isFinite(value) || value === 0) return undefined;
  return value > 0 ? "good" : "bad";
}

/** Baris tooltip, urutan sama dengan referensi Tableau. */
export function tooltipRows(item: ProductionGroupItem): TipRow[] {
  return [
    { label: "Aktual (A) (ton)", value: compactTon(item.aktual_ton) },
    { label: "Budget (B) (ton)", value: compactTon(item.budget_ton) },
    { label: "Aktual (A) (ton/ha)", value: signed(item.aktual_ton_ha) },
    { label: "Budget (B) (ton/ha)", value: signed(item.budget_ton_ha) },
    { label: "Akt Thn Lalu (L) (ton)", value: compactTon(item.aktual_tahun_lalu_ton) },
    { label: "Var (%) A vs B", value: signed(item.var_budget_pct, " %"), tone: tone(item.var_budget_pct) },
    { label: "Var (ton) A vs B", value: compactTon(item.var_budget_ton) },
    { label: "Var (%) A vs L", value: signed(item.var_tahun_lalu_pct, " %"), tone: tone(item.var_tahun_lalu_pct) },
    { label: "Var (ton) A vs L", value: compactTon(item.var_tahun_lalu_ton) },
    { label: "Luas Tanam (ha)", value: compactTon(item.luas_tanam) },
    { label: "RUT (tahun)", value: signed(item.rut) },
  ];
}
