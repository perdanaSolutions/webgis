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
  const parts: GeoJsonCollection[] = [];
  for (let i = 0; i < features.length; i += size) {
    parts.push({
      type: "FeatureCollection",
      features: features.slice(i, i + size) as GeoJsonFeature[],
    });
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

/** Gabungkan hasil analyze beberapa part menjadi satu payload untuk AnalysisResult. */
export function mergeAnalyzeResults(results: Array<Record<string, any> | null | undefined>): Record<string, any> {
  const unwrapped = results.filter(Boolean).map((r) => unwrapAnalysisPayload(r!));
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
