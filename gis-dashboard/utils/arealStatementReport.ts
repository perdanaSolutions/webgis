import type { ArealSummary } from "~/stores/blokProfileStore";

/**
 * Baris card "Informasi Areal Statement", urutannya mengikuti tabel laporan peta areal statement:
 * tanaman per tahun tanam, populasi per kelas kerapatan pokok, lalu areal non-tanam dari layer landuse.
 * `luas` null = data tidak tersedia (tidak ada sumbernya, belum ada data, atau tanpa hak akses).
 */
export type ArealReportRow = {
  no?: string;
  label: string;
  luas: number | null;
  persen?: number | null;
  /** Kotak warna (tahun tanam). */
  swatch?: string | null;
  /** Titik warna (kelas populasi). */
  dot?: string;
  kind: "total" | "item" | "section" | "sub" | "grand";
};

const POPULATION_DOT: Record<string, string> = {
  ATAS_136: "#22a33a",
  ANTARA_130_135: "#f5d90a",
  BAWAH_130: "#e02424",
};
const POPULATION_LABEL: Record<string, string> = {
  ATAS_136: "Diatas 136 Pokok/Ha",
  ANTARA_130_135: "130 - 135 Pokok/Ha",
  BAWAH_130: "Dibawah 130 Pokok/Ha",
};

export function buildArealReport(summary: ArealSummary | null | undefined): ArealReportRow[] {
  const tanam = summary?.areal_tanam ?? null;
  const nonTanam = summary?.areal_non_tanam ?? null;
  const landuse = (kode: string) => {
    if (!nonTanam) return null;
    return nonTanam.per_baris.find((row) => row.kode === kode)?.luas ?? 0;
  };
  const lc = landuse("LC");
  const tb = tanam ? tanam.per_status.find((row) => row.status === "TB")?.luas_tanam ?? 0 : null;
  const lainnya = landuse("LAINNYA");

  const rows: ArealReportRow[] = [
    { label: "Tanaman (TM+TBM+TB)", luas: tanam?.total_luas_tanam ?? null, kind: "total" },
    ...(tanam?.per_tahun_tanam ?? []).map((row): ArealReportRow => ({
      label: `Tahun Tanam ${row.tahun_tanam || "-"}`, luas: row.luas_tanam, swatch: row.warna, kind: "item",
    })),
    { no: "6", label: "Tanaman Baru (TB)", luas: tb, kind: "item" },
    { label: "Populasi Tanaman (PKK/HA)", luas: null, kind: "section" },
    ...(summary?.populasi?.kelas ?? []).map((row): ArealReportRow => ({
      label: POPULATION_LABEL[row.kode] ?? row.label, luas: row.luas_tanam, persen: row.persen,
      dot: POPULATION_DOT[row.kode], kind: "sub",
    })),
    { label: "Pembukaan Lahan / LC", luas: lc, kind: "item" },
    { no: "7", label: "a. LC (Perun) Dikerjakan", luas: null, kind: "sub" },
    { no: "8", label: "b. LC (Perun) Belum Dikerjakan", luas: null, kind: "sub" },
    { label: "Total Ditanam + LC (Perun)", luas: tanam ? tanam.total_luas_tanam + (lc ?? 0) : null, kind: "item" },
    { no: "9", label: "Bibitan", luas: landuse("BIBITAN"), kind: "item" },
    { no: "10", label: "Emplasemen/Pondok", luas: landuse("EMPLASEMEN"), kind: "item" },
    { no: "11", label: "Pabrik", luas: landuse("PABRIK"), kind: "item" },
    { label: "Jalan/Jembatan/Prasarana Lain", luas: landuse("JALAN_PRASARANA"), kind: "item" },
    { no: "12", label: "Cadangan", luas: landuse("CADANGAN"), kind: "item" },
    { no: "13", label: "Okupasi", luas: landuse("OKUPASI"), kind: "item" },
    { no: "14", label: "Tanah Desa", luas: null, kind: "item" },
    { no: "15", label: "Bukit, Sungai, Rawa, Tandus dll", luas: landuse("BUKIT_SUNGAI_RAWA"), kind: "item" },
  ];
  // Kategori landuse yang belum dipetakan ke baris laporan tetap ditampilkan agar grand total cocok.
  if (lainnya) rows.push({ label: "Lainnya", luas: lainnya, kind: "item" });
  rows.push({ label: "Grand Total Areal", luas: summary?.total?.grand_total_areal ?? null, kind: "grand" });
  return rows;
}
