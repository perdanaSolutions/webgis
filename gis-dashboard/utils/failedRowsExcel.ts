/**
 * Excel "data gagal" TAHAP ANALISA, dibuat di browser langsung dari data tabel preview.
 *
 * Sumber: baris preview yang sudah ada di halaman (fitur GeoJSON `allPreviewRows` / baris Excel transaksi),
 * dicocokkan dengan hasil analisa `previewAnalysis` (gabungan `table_preview` semua part).
 * Indeks: `no_preview` = nomor data GLOBAL di file, mulai 1 (backend: feature_offset part + nomor di part),
 * sama dengan nomor baris preview -> data = previewRows[no_preview - 1]. Tidak ada batas jumlah baris;
 * satu-satunya pemotongan = teks sel > 32.767 karakter (batas Excel).
 * Satu baris Excel per data gagal; bila satu data punya >1 alasan (`gagal_lain`), kode digabung "A; B"
 * dan alasan ditulis bernomor dalam satu sel.
 */

export const CELL_LIMIT = 32767;
export const TRUNC_NOTE = " … [DIPOTONG: melebihi batas 32.767 karakter per sel Excel]";
const FORMULA_PREFIX = ["=", "+", "-", "@", "\t", "\r"];

export const KODE_LABELS: Record<string, string> = {
  ATRIBUT_BLOK_KOSONG: "atribut Estate/Afdeling/Blok tidak lengkap",
  GEOMETRI_TIDAK_VALID: "geometri tidak valid / kosong / tipenya tidak sesuai",
  NILAI_TIDAK_VALID: "nilai atribut wajib kosong / tidak valid",
  BLOK_TIDAK_DITEMUKAN: "blok tidak ditemukan di master",
  BLOK_KEMBAR_DI_MASTER: "kode blok kembar di beberapa afdeling master",
  OBJECTID_GANDA: "OBJECTID ganda di file",
  GAGAL_DISIMPAN: "gagal disimpan",
  KODE_BLOK_KOSONG: "kode blok kosong",
  DUPLIKAT_BERTENTANGAN: "baris duplikat dengan nilai bertentangan",
};

export type FailureRow = {
  no_preview: number;
  status_analisa: string;
  kode_gagal: string | null;
  alasan_gagal: string | null;
  gagal_lain?: Array<{ kode: string; alasan: string }>;
};

export type FailedExportInput = {
  /** Baris preview berurutan seperti di tabel: index 0 = data no 1. */
  rows: unknown[];
  /** previewAnalysis: key = no_preview global (mulai 1). */
  analysis: Record<number, FailureRow | undefined>;
  kategori: string;
  filename: string | null | undefined;
  periode?: string;
  /** Kolom preview (urutan tabel). Kolom lain yang hanya ada di sebagian data ditambahkan di belakang. */
  columns?: string[];
};

export function safeCell(value: unknown): string | number | boolean | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" || typeof value === "boolean") return value;
  let text = typeof value === "object" ? JSON.stringify(value) : String(value);
  // eslint-disable-next-line no-control-regex
  text = text.replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, "");
  if (FORMULA_PREFIX.some((p) => text.startsWith(p))) text = `'${text}`;
  if (text.length > CELL_LIMIT) text = text.slice(0, CELL_LIMIT - TRUNC_NOTE.length) + TRUNC_NOTE;
  return text;
}

type Pos = number[];
const fmt = (p: Pos) => p.slice(0, 3).join(" ");
const ring = (r: Pos[]) => `(${r.map(fmt).join(", ")})`;

/** GeoJSON geometry -> WKT (null bila kosong / tidak dikenal -> JSON). */
export function geometryToWkt(geometry: any): string | null {
  if (!geometry || typeof geometry !== "object") return null;
  try {
    const c = geometry.coordinates;
    switch (geometry.type) {
      case "Point": return `POINT (${fmt(c)})`;
      case "MultiPoint": return `MULTIPOINT (${c.map((p: Pos) => `(${fmt(p)})`).join(", ")})`;
      case "LineString": return `LINESTRING ${ring(c)}`;
      case "MultiLineString": return `MULTILINESTRING (${c.map(ring).join(", ")})`;
      case "Polygon": return `POLYGON (${c.map(ring).join(", ")})`;
      case "MultiPolygon": return `MULTIPOLYGON (${c.map((pg: Pos[][]) => `(${pg.map(ring).join(", ")})`).join(", ")})`;
      case "GeometryCollection":
        return `GEOMETRYCOLLECTION (${(geometry.geometries ?? []).map(geometryToWkt).join(", ")})`;
      default: return JSON.stringify(geometry);
    }
  } catch {
    return JSON.stringify(geometry);
  }
}

function split(source: any): { props: Record<string, unknown>; geometry: unknown; isGeo: boolean } {
  if (source && typeof source === "object" && (source.type === "Feature" || "geometry" in source)) {
    return { props: { ...(source.properties ?? {}) }, geometry: source.geometry, isGeo: true };
  }
  if (source && typeof source === "object") return { props: { ...source }, geometry: null, isGeo: false };
  return { props: {}, geometry: null, isGeo: false };
}

export type FailedSheets = { data: unknown[][]; summary: unknown[][]; failedCount: number; columns: string[] };

/** Susun isi sheet (array of arrays). Semua data GAGAL dari `analysis`, diurutkan menurut nomor data. */
export function buildFailedSheets(input: FailedExportInput, now: Date = new Date()): FailedSheets {
  const failed = Object.values(input.analysis)
    .filter((r): r is FailureRow => Boolean(r) && r!.status_analisa === "GAGAL")
    .sort((a, b) => a.no_preview - b.no_preview);

  const prepared = failed.map((r) => ({ r, ...split(input.rows[r.no_preview - 1]) }));
  const columns = [...(input.columns ?? [])];
  const seen = new Set(columns);
  for (const p of prepared) for (const k of Object.keys(p.props)) if (!seen.has(k)) { seen.add(k); columns.push(k); }
  const hasGeo = prepared.some((p) => p.isGeo);

  const header = ["No", "No Data di File", "Kode Gagal", "Keterangan Kode", "Alasan Gagal", ...columns];
  if (hasGeo) header.push("Geometri (WKT)");
  const data: unknown[][] = [header.map(safeCell)];
  const counts = new Map<string, number>();
  prepared.forEach((p, i) => {
    const all = [{ kode: p.r.kode_gagal ?? "-", alasan: p.r.alasan_gagal ?? "" }, ...(p.r.gagal_lain ?? [])];
    all.forEach((x) => counts.set(x.kode, (counts.get(x.kode) ?? 0) + 1));
    const kode = all.map((x) => x.kode).join("; ");
    const ket = all.map((x) => KODE_LABELS[x.kode] ?? x.kode).join("; ");
    const alasan = all.length === 1 ? all[0]!.alasan : all.map((x, n) => `${n + 1}. [${x.kode}] ${x.alasan}`).join("\n");
    const line: unknown[] = [i + 1, p.r.no_preview, kode, ket, alasan, ...columns.map((c) => p.props[c])];
    if (hasGeo) line.push(geometryToWkt(p.geometry));
    data.push(line.map(safeCell));
  });

  const summary: unknown[][] = [
    ["Nama File", input.filename || "-"],
    ["Kategori", input.kategori || "-"],
    ["Periode", input.periode || "-"],
    ["Tahap", "Analisis (Tahap 1)"],
    ["Diunduh", formatWib(now)],
    ["Total Data di File", input.rows.length],
    ["Total Data Gagal", failed.length],
    [],
    ["Kode Gagal", "Jumlah", "Keterangan"],
    ...[...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([k, n]) => [k, n, KODE_LABELS[k] ?? k]),
  ].map((r) => r.map(safeCell));
  if ([...counts.values()].reduce((a, b) => a + b, 0) > failed.length) {
    summary.push([], ["Catatan", "Satu data bisa punya lebih dari satu kode gagal; jumlah per kode bisa melebihi total data gagal."]);
  }
  return { data, summary, failedCount: failed.length, columns };
}

function wibParts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Jakarta", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return { y: get("year"), m: get("month"), d: get("day"), h: get("hour").replace("24", "00"), i: get("minute") };
}

export function formatWib(date: Date): string {
  const p = wibParts(date);
  return `${p.d}-${p.m}-${p.y} ${p.h}:${p.i} WIB`;
}

export function failedExportFilename(kategori: string, filename: string | null | undefined, now: Date = new Date()): string {
  const clean = (s: string) => s.replace(/[^A-Za-z0-9_-]+/g, "_").replace(/^_+|_+$/g, "");
  const stem = clean((filename ?? "").replace(/(_part\d+of\d+)?\.(geo)?json$|\.(xlsx|xls|csv)$/i, "")).slice(0, 60) || "file";
  const p = wibParts(now);
  return `data_gagal_${clean(kategori || "data") || "data"}_${stem}_${p.y}${p.m}${p.d}-${p.h}${p.i}.xlsx`;
}

/** Bangun & unduh file .xlsx (SheetJS dimuat saat dibutuhkan saja). Mengembalikan jumlah data gagal. */
export async function downloadFailedRowsExcel(input: FailedExportInput): Promise<number> {
  const now = new Date();
  const sheets = buildFailedSheets(input, now);
  if (!sheets.failedCount) throw new Error("Tidak ada data gagal untuk diunduh.");
  const XLSX = await import("xlsx");
  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(sheets.data);
  const width = (h: unknown) => (h === "Alasan Gagal" ? 80 : h === "Geometri (WKT)" ? 50 : h === "No" ? 6 : 18);
  ws["!cols"] = (sheets.data[0] as unknown[]).map((h) => ({ wch: width(h) }));
  ws["!autofilter"] = { ref: ws["!ref"] as string };
  XLSX.utils.book_append_sheet(wb, ws, "Data Gagal");
  const ss = XLSX.utils.aoa_to_sheet(sheets.summary);
  ss["!cols"] = [{ wch: 28 }, { wch: 40 }, { wch: 60 }];
  XLSX.utils.book_append_sheet(wb, ss, "Ringkasan");
  XLSX.writeFile(wb, failedExportFilename(input.kategori, input.filename, now), { compression: true });
  return sheets.failedCount;
}

/** Jumlah data GAGAL di previewAnalysis (gabungan table_preview semua part yang sudah selesai). */
export function countFailedPreview(analysis: Record<number, { status_analisa?: string } | undefined>): number {
  let n = 0;
  for (const row of Object.values(analysis)) if (row?.status_analisa === "GAGAL") n++;
  return n;
}
