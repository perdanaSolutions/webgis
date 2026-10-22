/** Pecah FeatureCollection jadi beberapa part (default 1.000 feature) untuk analyze/execute beruntun. */

export const GEOJSON_FEATURES_PER_PART = 1000;

export type GeoJsonFeature = GeoJSON.Feature<
  GeoJSON.Geometry,
  Record<string, string | number | boolean | null | undefined>
>;

export type GeoJsonCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, string | number | boolean | null | undefined>
>;

export function chunkFeatureCollection(
  collection: GeoJsonCollection,
  size = GEOJSON_FEATURES_PER_PART,
): GeoJsonCollection[] {
  const features = collection.features ?? [];
  if (!features.length) return [];
  // Bawa member `crs` (mis. urn:ogc:def:crs:EPSG::32650) ke setiap part; tanpa ini backend
  // menerima koordinat UTM tanpa keterangan CRS dan menolak part tersebut.
  const crs = (collection as { crs?: unknown }).crs;
  const parts: GeoJsonCollection[] = [];
  for (let i = 0; i < features.length; i += size) {
    parts.push({
      type: "FeatureCollection",
      ...(crs ? { crs } : {}),
      features: features.slice(i, i + size) as GeoJsonFeature[],
    } as GeoJsonCollection);
  }
  return parts;
}

export function featureCollectionToFile(
  part: GeoJsonCollection,
  baseName: string,
  partIndex: number,
  partTotal: number,
): File {
  const blob = new Blob([JSON.stringify(part)], { type: "application/geo+json" });
  const stem = baseName.replace(/\.(geojson|json)$/i, "") || "upload";
  return new File([blob], `${stem}.part${partIndex}of${partTotal}.geojson`, {
    type: "application/geo+json",
  });
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Analisis layer bawaan/sawit ada di `data`; blok/dinamis di root. */
export function unwrapAnalysisPayload(result: Record<string, any> | null | undefined): {
  root: Record<string, any>;
  body: Record<string, any>;
  wrapped: boolean;
} {
  const root = result && isPlainObject(result) ? { ...result } : {};
  const data = root.data;
  if (
    isPlainObject(data) &&
    ("status_analisis" in data || "peringatan" in data || "kesimpulan" in data || "rincian" in data)
  ) {
    return { root, body: { ...data }, wrapped: true };
  }
  return { root, body: root, wrapped: false };
}

function mergeStatus(statuses: string[]): string {
  const set = new Set(statuses.filter(Boolean));
  if (!set.size) return "SIAP";
  if (set.size === 1) return [...set][0]!;
  if (set.has("SIAP_DENGAN_CATATAN") || (set.has("SIAP") && set.has("TIDAK_ADA_DATA_VALID"))) {
    return "SIAP_DENGAN_CATATAN";
  }
  if (set.has("TIDAK_ADA_DATA_VALID")) return "TIDAK_ADA_DATA_VALID";
  return "SIAP_DENGAN_CATATAN";
}

function addNumbers(target: Record<string, any>, source: Record<string, any>, skip: Set<string>) {
  for (const [key, value] of Object.entries(source)) {
    if (skip.has(key) || value == null) continue;
    if (typeof value === "number" && Number.isFinite(value)) {
      target[key] = (typeof target[key] === "number" ? target[key] : 0) + value;
      continue;
    }
    if (isPlainObject(value)) {
      if (!isPlainObject(target[key])) target[key] = {};
      addNumbers(target[key], value, skip);
    }
  }
}

const ANALYSIS_SKIP = new Set([
  "status_analisis",
  "kesimpulan",
  "peringatan",
  "rincian",
  "tipe_upload",
  "jenis",
  "status",
  "message",
  "data",
  "no_preview_awal",
  "no_preview_akhir",
]);

function mergePeringatan(parts: Record<string, any>[]): Array<Record<string, any>> {
  const byKode = new Map<string, Record<string, any>>();
  for (const body of parts) {
    const list = Array.isArray(body.peringatan) ? body.peringatan : [];
    for (const item of list) {
      if (!isPlainObject(item)) continue;
      const kode = String(item.kode ?? item.pesan ?? JSON.stringify(item));
      const prev = byKode.get(kode);
      if (!prev) {
        byKode.set(kode, { ...item });
        continue;
      }
      if (typeof item.jumlah === "number" || typeof prev.jumlah === "number") {
        prev.jumlah = (Number(prev.jumlah) || 0) + (Number(item.jumlah) || 0);
      }
    }
  }
  return [...byKode.values()];
}

function mergeRincian(parts: Record<string, any>[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const body of parts) {
    if (!isPlainObject(body.rincian)) continue;
    for (const [key, value] of Object.entries(body.rincian)) {
      if (key === "catatan") {
        if (typeof value === "string" && value && !out.catatan) out.catatan = value;
        continue;
      }
      if (Array.isArray(value)) {
        const prev = Array.isArray(out[key]) ? (out[key] as unknown[]) : [];
        out[key] = [...prev, ...value].slice(0, 500);
        continue;
      }
      if (isPlainObject(value) && Array.isArray(value.contoh)) {
        const prev = isPlainObject(out[key]) ? (out[key] as Record<string, unknown>) : {};
        const prevContoh = Array.isArray(prev.contoh) ? prev.contoh : [];
        const jumlah =
          (typeof prev.jumlah === "number" ? prev.jumlah : 0) +
          (typeof value.jumlah === "number" ? value.jumlah : value.contoh.length);
        out[key] = {
          ...prev,
          ...value,
          jumlah,
          contoh: [...prevContoh, ...value.contoh].slice(0, 200),
        };
        continue;
      }
      if (!(key in out)) out[key] = value;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Respons analyze per part (backend baru):
// { kategori, bulan, tahun, part, total_part,
//   data: { table_preview[], analisa_aman{}, analisa_gagal{}, ringkasan{} } }
// ---------------------------------------------------------------------------

export type PreviewAnalysisRow = {
  no_preview: number;
  status_analisa: "AMAN" | "GAGAL" | string;
  kode_gagal: string | null;
  alasan_gagal: string | null;
};

export type PartAnalyzeResponse = {
  kategori: string;
  bulan: number | string;
  tahun: number | string;
  part: number | string;
  total_part: number | string;
  data: {
    table_preview: PreviewAnalysisRow[];
    analisa_aman: Record<string, any>;
    analisa_gagal: Record<string, any>;
    ringkasan?: Record<string, any>;
  };
};

export type PartAnalyzeSummary = {
  part: number;
  total_part: number;
  no_preview_awal: number | null;
  no_preview_akhir: number | null;
  jumlah_aman: number;
  jumlah_gagal: number;
  analisa_aman: Record<string, any>;
  analisa_gagal: Record<string, any>;
};

export function isPartAnalyzeResponse(value: unknown): value is PartAnalyzeResponse {
  return (
    isPlainObject(value) &&
    "part" in value &&
    "total_part" in value &&
    isPlainObject(value.data) &&
    Array.isArray((value.data as Record<string, unknown>).table_preview)
  );
}

/** Offset feature tiap part (part 1 = 0) untuk dikirim ke backend sebagai `feature_offset`. */
export function partFeatureOffset(partIndex: number, size = GEOJSON_FEATURES_PER_PART): number {
  return Math.max(0, (partIndex - 1) * size);
}

/** Ubah respons per part ke bentuk lama (status_analisis/peringatan/rincian) untuk AnalysisResult. */
export function partToLegacyBody(response: PartAnalyzeResponse): Record<string, any> {
  const { analisa_aman: aman = {}, analisa_gagal: gagal = {}, ringkasan = {} } = response.data;
  return {
    ...ringkasan,
    peringatan: [
      ...(Array.isArray(gagal.peringatan) ? gagal.peringatan : []),
      ...(Array.isArray(aman.catatan) ? aman.catatan : []),
    ],
    rincian: {
      ...(isPlainObject(aman.rincian) ? aman.rincian : {}),
      ...(isPlainObject(gagal.rincian) ? gagal.rincian : {}),
    },
  };
}

/** Peta no_preview -> hasil analisa, untuk menambah kolom status di tabel preview. */
export function indexTablePreview(
  target: Record<number, PreviewAnalysisRow>,
  rows: PreviewAnalysisRow[] | null | undefined,
): Record<number, PreviewAnalysisRow> {
  for (const row of rows ?? []) {
    if (row && typeof row.no_preview === "number") target[row.no_preview] = row;
  }
  return target;
}

export function summarizePart(response: PartAnalyzeResponse): PartAnalyzeSummary {
  const rows = response.data.table_preview ?? [];
  const gagal = rows.filter((r) => r.status_analisa === "GAGAL").length;
  const numbers = rows.map((r) => r.no_preview);
  return {
    part: Number(response.part) || 1,
    total_part: Number(response.total_part) || 1,
    no_preview_awal: numbers.length ? Math.min(...numbers) : null,
    no_preview_akhir: numbers.length ? Math.max(...numbers) : null,
    jumlah_aman: rows.length - gagal,
    jumlah_gagal: gagal,
    analisa_aman: response.data.analisa_aman ?? {},
    analisa_gagal: response.data.analisa_gagal ?? {},
  };
}

function concatLists(target: Record<string, any>, source: Record<string, any>, limit = 1000) {
  for (const [key, value] of Object.entries(source ?? {})) {
    if (Array.isArray(value)) {
      const prev = Array.isArray(target[key]) ? target[key] : [];
      target[key] = [...prev, ...value].slice(0, limit);
    } else if (typeof value === "number") {
      target[key] = (typeof target[key] === "number" ? target[key] : 0) + value;
    } else if (isPlainObject(value)) {
      if (!isPlainObject(target[key])) target[key] = {};
      concatLists(target[key], value, limit);
    } else if (!(key in target)) {
      target[key] = value;
    }
  }
}

/** Gabung kelompok gagal per kode dari beberapa part (jumlah dijumlah, data disambung). */
function mergePerKode(parts: PartAnalyzeSummary[]): Array<Record<string, any>> {
  const byKode = new Map<string, Record<string, any>>();
  for (const part of parts) {
    for (const group of (part.analisa_gagal.per_kode ?? []) as Array<Record<string, any>>) {
      const prev = byKode.get(group.kode);
      if (!prev) {
        byKode.set(group.kode, { ...group, data: [...(group.data ?? [])] });
        continue;
      }
      prev.jumlah = (Number(prev.jumlah) || 0) + (Number(group.jumlah) || 0);
      prev.data = [...prev.data, ...(group.data ?? [])].slice(0, 5000);
    }
  }
  return [...byKode.values()].sort((a, b) => (b.jumlah ?? 0) - (a.jumlah ?? 0));
}

function mergeNotes(lists: Array<Array<Record<string, any>> | undefined>): Array<Record<string, any>> {
  return mergePeringatan(lists.map((list) => ({ peringatan: list ?? [] })));
}

/** Gabungan analisa_aman & analisa_gagal semua part (urut part). */
export function mergeAnalysisGroups(parts: PartAnalyzeSummary[]): {
  analisa_aman: Record<string, any>;
  analisa_gagal: Record<string, any>;
} {
  const sorted = [...parts].sort((a, b) => a.part - b.part);
  const amanRincian: Record<string, any> = {};
  const gagalRincian: Record<string, any> = {};
  for (const part of sorted) {
    concatLists(amanRincian, part.analisa_aman.rincian ?? {});
    concatLists(gagalRincian, part.analisa_gagal.rincian ?? {});
  }
  return {
    analisa_aman: {
      jumlah_data: sorted.reduce((n, p) => n + p.jumlah_aman, 0),
      rincian: amanRincian,
      catatan: mergeNotes(sorted.map((p) => p.analisa_aman.catatan)),
    },
    analisa_gagal: {
      jumlah_data: sorted.reduce((n, p) => n + p.jumlah_gagal, 0),
      per_kode: mergePerKode(sorted),
      rincian: gagalRincian,
      peringatan: mergeNotes(sorted.map((p) => p.analisa_gagal.peringatan)),
    },
  };
}

/** Gabungkan hasil analyze beberapa part menjadi satu payload untuk AnalysisResult. */
export function mergeAnalyzeResults(results: Array<Record<string, any> | null | undefined>): Record<string, any> {
  const present = results.filter(Boolean) as Array<Record<string, any>>;
  if (present.length && present.every(isPartAnalyzeResponse)) {
    const responses = present as PartAnalyzeResponse[];
    const legacy = mergeAnalyzeResults(responses.map(partToLegacyBody));
    const summaries = responses.map(summarizePart).sort((a, b) => a.part - b.part);
    const groups = mergeAnalysisGroups(summaries);
    const first = responses[0]!;
    return {
      ...legacy,
      kategori: first.kategori,
      bulan: first.bulan,
      tahun: first.tahun,
      total_part: Number(first.total_part) || responses.length,
      part_selesai: responses.length,
      table_preview: responses.flatMap((r) => r.data.table_preview ?? []),
      analisa_aman: groups.analisa_aman,
      analisa_gagal: groups.analisa_gagal,
      per_part: summaries,
    };
  }
  const unwrapped = present.map((r) => unwrapAnalysisPayload(r));
  if (!unwrapped.length) return {};

  const bodies = unwrapped.map((u) => u.body);
  const mergedBody: Record<string, any> = {};
  for (const body of bodies) addNumbers(mergedBody, body, ANALYSIS_SKIP);

  mergedBody.status_analisis = mergeStatus(bodies.map((b) => String(b.status_analisis ?? "")));
  mergedBody.peringatan = mergePeringatan(bodies);
  mergedBody.rincian = mergeRincian(bodies);

  const totalFeatures = bodies.reduce((sum, b) => {
    const n = b.total_data ?? b.jumlah_data_total_di_file ?? b.jumlah_data_dianalisis;
    return sum + (typeof n === "number" ? n : 0);
  }, 0);
  mergedBody.kesimpulan =
    bodies.length === 1
      ? bodies[0]!.kesimpulan
      : `Hasil digabung dari ${bodies.length} part` +
        (totalFeatures ? ` (total ${totalFeatures.toLocaleString("id-ID")} data).` : ".");

  const first = unwrapped[0]!;
  if (!first.wrapped) return mergedBody;

  return {
    ...first.root,
    data: mergedBody,
    message:
      typeof first.root.message === "string"
        ? `${first.root.message} (digabung ${bodies.length} part)`
        : first.root.message,
  };
}

/** Gabungkan hasil execute beberapa part (jumlah sukses/gagal dll.). */
export function mergeExecuteResults(results: Array<Record<string, any> | null | undefined>): Record<string, any> {
  const list = results.filter((r): r is Record<string, any> => isPlainObject(r));
  if (!list.length) return {};
  if (list.length === 1) return list[0]!;

  const merged: Record<string, any> = { ...list[0], parts: list.length };
  const skip = new Set(["status", "message", "batch_id", "versi_penyimpanan", "parts"]);

  for (let i = 1; i < list.length; i++) {
    // addNumbers sudah rekursif ke detail/data/detail_status — jangan dijumlah dua kali.
    addNumbers(merged, list[i]!, skip);
  }

  const statuses = list.map((r) =>
    String(r.status_proses ?? r.detail?.status_proses ?? r.data?.status_proses ?? r.status ?? ""),
  );
  if (statuses.some((s) => s === "PARTIAL_SUCCESS" || s === "FAILED") && statuses.some((s) => s === "SUCCESS")) {
    if (merged.detail && isPlainObject(merged.detail)) merged.detail.status_proses = "PARTIAL_SUCCESS";
    if (merged.data && isPlainObject(merged.data)) merged.data.status_proses = "PARTIAL_SUCCESS";
    merged.status_proses = "PARTIAL_SUCCESS";
  }

  if (typeof merged.message === "string") {
    merged.message = `${merged.message} (digabung ${list.length} part)`;
  }
  return merged;
}
