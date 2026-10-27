/** Unduhan Excel data gagal hasil analisa/simpan upload (GET /v1/upload-jobs/{job_id}/data-gagal.xlsx). */

export function failedRowsUrl(baseUrl: string, jobId: string): string {
  return `${baseUrl}/v1/upload-jobs/${encodeURIComponent(jobId)}/data-gagal.xlsx`;
}

/** Nama file dari header Content-Disposition (filename*=UTF-8''... atau filename="..."). */
export function filenameFromDisposition(header: string | null | undefined, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*\s*=\s*(?:UTF-8'')?([^;]+)/i.exec(header);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ""));
    } catch {
      /* lanjut ke filename biasa */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(header);
  return plain?.[1]?.trim() || fallback;
}

/** Jumlah data karantina (gagal simpan) dari respons execute gabungan: jumlah semua `karantina_count`. */
export function countQuarantined(value: unknown): number {
  if (Array.isArray(value)) return value.reduce((n: number, v) => n + countQuarantined(v), 0);
  if (!value || typeof value !== "object") return 0;
  let total = 0;
  for (const [key, v] of Object.entries(value as Record<string, unknown>)) {
    if (key === "karantina_count" && typeof v === "number") total += v;
    else if (v && typeof v === "object") total += countQuarantined(v);
  }
  return total;
}

/** Pesan error dari respons blob (FastAPI mengirim JSON {detail|message}). */
export async function blobErrorMessage(error: unknown, fallback: string): Promise<string> {
  const err = error as { data?: unknown; status?: number; statusCode?: number } | null;
  let data: any = err?.data;
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    try {
      data = JSON.parse(await data.text());
    } catch {
      data = null;
    }
  }
  const message = data?.message ?? data?.detail?.message ?? (typeof data?.detail === "string" ? data.detail : null);
  if (message) return String(message);
  const status = err?.statusCode ?? err?.status;
  if (status === 404) return "Data gagal tidak ditemukan (proses upload sudah kedaluwarsa atau tidak ada data gagal).";
  if (status === 401 || status === 403) return "Anda tidak memiliki akses untuk mengunduh data ini.";
  return fallback;
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
