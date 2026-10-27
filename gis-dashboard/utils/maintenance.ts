export const MAINTENANCE_PATH = "/maintenance";
export const MAINTENANCE_STATE_KEY = "maintenance-status";
/** Polling latar: cukup jarang; cek utama lewat login enter/reload dan ganti menu. */
export const MAINTENANCE_POLL_MS = 30 * 60 * 1000;
export const MAINTENANCE_DEFAULT_MESSAGE =
  "Kami sedang melakukan perbaikan dan peningkatan sistem. Mohon coba beberapa saat lagi.";

export type MaintenanceStatus = { maintenance: boolean; message: string };

export function isMaintenancePath(path: string) {
  return path.replace(/\/+$/, "") === MAINTENANCE_PATH;
}

export function isLoginPath(path: string) {
  return path.replace(/\/+$/, "") === "/login";
}

/**
 * Kapan middleware boleh hit API status:
 * - halaman login (reload / baru masuk)
 * - navigasi menu saat user sudah login
 */
export function shouldFetchMaintenanceOnRoute(path: string, isAuthenticated: boolean) {
  if (isMaintenancePath(path)) return false;
  if (isLoginPath(path)) return true;
  return isAuthenticated;
}

/** Ke mana harus pindah setelah status diketahui; null = tetap di halaman. */
export function maintenanceRedirect(path: string, maintenance: boolean, reason?: unknown): string | null {
  const onPage = isMaintenancePath(path);
  if (maintenance && !onPage) return MAINTENANCE_PATH;
  // reason=server-error: halaman /maintenance sendiri yang mengurus pemulihan (cek health + kembali ke `from`).
  const serverError = (Array.isArray(reason) ? reason[0] : reason) === "server-error";
  if (!maintenance && onPage && !serverError) return "/";
  return null;
}

/** Body 503 dari API lain saat middleware backend memblokir request. */
export function isMaintenanceResponse(status: number | undefined, body: unknown) {
  return status === 503 && !!body && typeof body === "object" && (body as { maintenance?: unknown }).maintenance === true;
}

/**
 * GET /system/maintenance harus HTTP 200 + { maintenance: boolean }.
 * Selain 200 (termasuk 404) dianggap bukan sinyal maintenance (fail open).
 */
export async function fetchMaintenanceStatus(baseURL: string): Promise<MaintenanceStatus> {
  try {
    const res = await $fetch.raw<Partial<MaintenanceStatus>>("/system/maintenance", {
      baseURL,
      timeout: 5000,
      headers: { accept: "application/json" },
    });
    if (res.status !== 200) {
      return { maintenance: false, message: MAINTENANCE_DEFAULT_MESSAGE };
    }
    const data = res._data;
    return {
      maintenance: data?.maintenance === true,
      message: (typeof data?.message === "string" && data.message) || MAINTENANCE_DEFAULT_MESSAGE,
    };
  } catch {
    // Backend tidak terjangkau / non-200: jangan kunci website (fail open).
    return { maintenance: false, message: MAINTENANCE_DEFAULT_MESSAGE };
  }
}
