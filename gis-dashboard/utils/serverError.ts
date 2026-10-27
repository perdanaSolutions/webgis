import { isMaintenancePath, isMaintenanceResponse, MAINTENANCE_PATH } from "./maintenance";

/** Nilai query `reason` di /maintenance saat backend error (bukan mode maintenance dari DB). */
export const SERVER_ERROR_REASON = "server-error";
/** Status HTTP yang dianggap "server bermasalah" dan memicu redirect ke /maintenance. */
export const SERVER_ERROR_STATUSES: readonly number[] = [500, 502, 503, 504];
/** Interval cek pemulihan di halaman /maintenance?reason=server-error. */
export const SERVER_RECOVERY_POLL_MS = 20 * 1000;
/** Jendela debounce: banyak 5xx bersamaan hanya menghasilkan satu navigasi. */
export const SERVER_REDIRECT_DEBOUNCE_MS = 5 * 1000;

/** Opsi per-request untuk mematikan redirect (error ditangani inline oleh pemanggil). */
export type ServerErrorRedirectOptions = { skipServerErrorRedirect?: boolean };

export function isServerErrorStatus(status: number | undefined | null): boolean {
  return typeof status === "number" && SERVER_ERROR_STATUSES.includes(status);
}

type FetchLikeError = {
  name?: string;
  status?: number;
  statusCode?: number;
  response?: { status?: number; _data?: unknown } | null;
  data?: unknown;
  cause?: unknown;
};

/**
 * Klasifikasi error $fetch/ofetch:
 * - "server": 500/502/503/504 (kecuali 503 maintenance) atau tidak ada respons (network/timeout)
 * - "maintenance": 503 + { maintenance: true } (sudah ditangani fitur maintenance)
 * - "abort": request dibatalkan sengaja (AbortController) -> diabaikan
 * - "client": status lain (4xx dll) -> tidak redirect
 */
export function classifyFetchError(error: unknown): "server" | "maintenance" | "abort" | "client" {
  const err = (error ?? {}) as FetchLikeError;
  const causeName = (err.cause as { name?: string } | undefined)?.name;
  if (err.name === "AbortError" || causeName === "AbortError") return "abort";
  const status = err.response?.status ?? err.status ?? err.statusCode;
  const body = err.response?._data ?? err.data;
  if (isMaintenanceResponse(status, body)) return "maintenance";
  if (isServerErrorStatus(status)) return "server";
  if (!status) return "server"; // tidak ada respons: backend tidak terjangkau / timeout
  return "client";
}

export function isServerProblemError(error: unknown): boolean {
  return classifyFetchError(error) === "server";
}

/** Hanya path internal; tolak open redirect (//evil, http:, /\\evil) dan /maintenance itu sendiri. */
export function sanitizeReturnPath(raw: unknown, fallback = "/"): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (typeof value !== "string" || !value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f\\]/.test(value)) return fallback;
  try {
    const url = new URL(value, "http://internal.invalid");
    if (url.origin !== "http://internal.invalid") return fallback;
    if (isMaintenancePath(url.pathname)) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}

/** Target redirect untuk error server; null bila sudah di /maintenance (cegah loop). */
export function serverErrorRedirectTarget(currentPath: string, currentFullPath?: string): string | null {
  if (isMaintenancePath(currentPath)) return null;
  const from = sanitizeReturnPath(currentFullPath ?? currentPath);
  const query = new URLSearchParams({ reason: SERVER_ERROR_REASON, from });
  return `${MAINTENANCE_PATH}?${query.toString()}`;
}

export function isServerErrorReason(reason: unknown): boolean {
  const value = Array.isArray(reason) ? reason[0] : reason;
  return value === SERVER_ERROR_REASON;
}

/** Debounce sederhana: true hanya untuk panggilan pertama dalam jendela waktu. */
export function createRedirectDebouncer(windowMs = SERVER_REDIRECT_DEBOUNCE_MS, now: () => number = Date.now) {
  let last = Number.NEGATIVE_INFINITY;
  let target: string | null = null;
  return {
    tryAcquire(nextTarget: string): boolean {
      const t = now();
      if (t - last < windowMs) return false;
      last = t;
      target = nextTarget;
      return true;
    },
    /** Target redirect yang sedang berjalan (dalam jendela debounce), atau null. */
    pending(): string | null {
      return now() - last < windowMs ? target : null;
    },
    reset() {
      last = Number.NEGATIVE_INFINITY;
      target = null;
    },
  };
}

export type BackendHealth = { ok: boolean; maintenance: boolean; message: string | null };

/** Cek pemulihan: ok hanya jika GET /system/maintenance HTTP 200. */
export async function checkBackendHealth(baseURL: string): Promise<BackendHealth> {
  try {
    const res = await $fetch.raw<{ maintenance?: boolean; message?: string }>("/system/maintenance", {
      baseURL,
      timeout: 5000,
      headers: { accept: "application/json" },
    });
    if (res.status !== 200) return { ok: false, maintenance: false, message: null };
    const data = res._data;
    return {
      ok: true,
      maintenance: data?.maintenance === true,
      message: typeof data?.message === "string" && data.message ? data.message : null,
    };
  } catch (error) {
    const status = (error as FetchLikeError)?.response?.status;
    const body = (error as FetchLikeError)?.response?._data;
    if (isMaintenanceResponse(status, body)) {
      const message = (body as { message?: unknown }).message;
      return { ok: true, maintenance: true, message: typeof message === "string" ? message : null };
    }
    return { ok: false, maintenance: false, message: null };
  }
}
