/** Nama bulan lengkap (Indonesia) untuk label periode data Block Profile. */
export const MONTHS_FULL_ID = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember",
] as const;

export type BlokDataPeriod = { bulan: number | null; tahun: number } | null | undefined;

/**
 * Label periode data di kartu/popup Informasi Blok dan PDF Unduh Peta.
 * - specific=false (bulan filter kosong -> data terbaru): "Data terbaru: Oktober 2026"
 * - specific=true (bulan periode dipilih):                "Data Periode: September 2026"
 * Bulan tidak ada -> hanya tahun ("Data terbaru: 2026"). Periode/tahun tidak ada -> "" (baris disembunyikan).
 */
export function blokDataPeriodLabel(period: BlokDataPeriod, specific: boolean): string {
  if (!period || !Number.isFinite(period.tahun) || !period.tahun) return "";
  const month = period.bulan && period.bulan >= 1 && period.bulan <= 12 ? MONTHS_FULL_ID[period.bulan - 1] : "";
  const when = [month, String(period.tahun)].filter(Boolean).join(" ");
  return `${specific ? "Data Periode" : "Data terbaru"}: ${when}`;
}
