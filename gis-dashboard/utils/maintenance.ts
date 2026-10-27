export const MAINTENANCE_PATH = "/maintenance";
export const MAINTENANCE_STATE_KEY = "maintenance-status";
/** Endpoint status (relatif ke apiBaseUrlPython yang sudah berakhiran /api). */
export const MAINTENANCE_STATUS_ENDPOINT = "/v1/system/maintenance";
/** Polling latar berkala di semua halaman (client): 15 menit. */
export const MAINTENANCE_POLL_MS = 15 * 60 * 1000;
/** Cek pemulihan di halaman /maintenance (ubah di sini bila perlu). */
export const MAINTENANCE_PAGE_RECOVERY_POLL_MS = 60 * 1000;
/** Setelah maintenance/server pulih user wajib login ulang (sesi sudah dihapus). */
export const MAINTENANCE_RECOVERY_PATH = "/login";

/**
 * URL absolut status maintenance: selalu <origin>/api/v1/system/maintenance.
 * Base boleh "https://x/api", "https://x/api/", "https://x/api/v1", atau "https://x".
 */
export function maintenanceStatusUrl(baseURL: string): string {
  let base = String(baseURL || "").trim().replace(/\/+$/, "");
  base = base.replace(/\/v1$/, "");
  if (!/\/api$/.test(base)) base = `${base}/api`;
  return `${base}${MAINTENANCE_STATUS_ENDPOINT}`;
}
export const MAINTENANCE_DEFAULT_MESSAGE =
  "Kami sedang melakukan perbaikan dan peningkatan sistem. Mohon coba beberapa saat lagi.";

export type MaintenanceStatus = { maintenance: boolean; message: string };

export function isMaintenancePath(path: string) {
  return path.replace(/\/+$/, "") === MAINTENANCE_PATH;
}

export function isLoginPath(path: string) {
  return path.replace(/\/+$/, "") === "/login";
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

/**
 * Body bertanda maintenance: `maintenance: true` ATAU errors[].type === "maintenance".
 * Contoh 503 dari middleware backend:
 * { maintenance: true, message: "...", errors: [{ type: "maintenance", field: "global", msg: "..." }] }
 */
export function parseMaintenanceBody(body: unknown): MaintenanceStatus | null {
  if (!body || typeof body !== "object") return null;
  const b = body as { maintenance?: unknown; message?: unknown; errors?: unknown };
  const errors = Array.isArray(b.errors) ? b.errors : [];
  const err = errors.find(
    (e) => !!e && typeof e === "object" && (e as { type?: unknown }).type === "maintenance",
  ) as { msg?: unknown } | undefined;
  if (b.maintenance !== true && !err) return null;
  const message =
    (typeof b.message === "string" && b.message)
    || (typeof err?.msg === "string" && err.msg)
    || MAINTENANCE_DEFAULT_MESSAGE;
  return { maintenance: true, message };
}

/** Middleware: cek status di setiap navigasi kecuali di /maintenance (halaman itu polling sendiri). */
export function shouldFetchMaintenanceOnRoute(path: string, _isAuthenticated?: boolean) {
  return !isMaintenancePath(path);
}

/** Target /maintenance (mode maintenance) dengan path asal agar bisa kembali. */
export function maintenanceTarget(_fromFullPath?: string) {
  // Tidak membawa `from`: setelah maintenance user harus login ulang.
  return MAINTENANCE_PATH;
}

/**
 * Ke mana harus pindah setelah status diketahui; null = tetap di halaman.
 * - maintenance aktif & bukan di /maintenance -> /maintenance
 * - maintenance mati & di /maintenance (bukan reason=server-error) -> /login (sesi sudah dihapus)
 */
export function maintenanceRedirect(
  path: string,
  maintenance: boolean,
  reason?: unknown,
  options?: { fullPath?: string; from?: unknown },
): string | null {
  const onPage = isMaintenancePath(path);
  if (maintenance && !onPage) return maintenanceTarget(options?.fullPath ?? path);
  // reason=server-error: halaman /maintenance sendiri yang mengurus pemulihan.
  const serverError = (Array.isArray(reason) ? reason[0] : reason) === "server-error";
  if (!maintenance && onPage && !serverError) return MAINTENANCE_RECOVERY_PATH;
  return null;
}

/** Respons API lain (200 atau 503) yang bodinya menandakan maintenance. */
export function isMaintenanceResponse(status: number | undefined, body: unknown) {
  return (status === 503 || status === 200) && parseMaintenanceBody(body) !== null;
}

/**
 * GET /v1/system/maintenance. 200 -> baca flag; 503 + body maintenance -> maintenance aktif.
 * Selain itu (404, 5xx lain, jaringan) fail open: website tidak dikunci.
 */
export async function fetchMaintenanceStatus(baseURL: string): Promise<MaintenanceStatus> {
  try {
    const res = await $fetch.raw<Partial<MaintenanceStatus>>(maintenanceStatusUrl(baseURL), {
      timeout: 5000,
      headers: { accept: "application/json" },
    });
    const parsed = parseMaintenanceBody(res._data);
    if (parsed) return parsed;
    const data = res._data;
    return {
      maintenance: false,
      message: (typeof data?.message === "string" && data.message) || MAINTENANCE_DEFAULT_MESSAGE,
    };
  } catch (error) {
    // 503 dari middleware maintenance: body tetap dibaca (dulu tertelan di sini).
    const body = (error as { response?: { _data?: unknown }; data?: unknown })?.response?._data
      ?? (error as { data?: unknown })?.data;
    const parsed = parseMaintenanceBody(body);
    if (parsed) return parsed;
    return { maintenance: false, message: MAINTENANCE_DEFAULT_MESSAGE };
  }
}
