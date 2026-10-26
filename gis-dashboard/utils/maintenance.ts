export const MAINTENANCE_PATH = "/maintenance";
export const MAINTENANCE_STATE_KEY = "maintenance-status";
export const MAINTENANCE_POLL_MS = 30_000;
export const MAINTENANCE_DEFAULT_MESSAGE =
  "Kami sedang melakukan perbaikan dan peningkatan sistem. Mohon coba beberapa saat lagi.";

export type MaintenanceStatus = { maintenance: boolean; message: string };

export function isMaintenancePath(path: string) {
  return path.replace(/\/+$/, "") === MAINTENANCE_PATH;
}

/** Ke mana harus pindah setelah status diketahui; null = tetap di halaman. */
export function maintenanceRedirect(path: string, maintenance: boolean): string | null {
  const onPage = isMaintenancePath(path);
  if (maintenance && !onPage) return MAINTENANCE_PATH;
  if (!maintenance && onPage) return "/";
  return null;
}

/** Body 503 dari backend saat maintenance aktif. */
export function isMaintenanceResponse(status: number | undefined, body: unknown) {
  return status === 503 && !!body && typeof body === "object" && (body as { maintenance?: unknown }).maintenance === true;
}

export async function fetchMaintenanceStatus(baseURL: string): Promise<MaintenanceStatus> {
  try {
    const res = await $fetch<Partial<MaintenanceStatus>>("/system/maintenance", {
      baseURL,
      timeout: 5000,
      headers: { accept: "application/json" },
    });
    return { maintenance: res?.maintenance === true, message: res?.message || MAINTENANCE_DEFAULT_MESSAGE };
  } catch {
    // Backend tidak terjangkau: jangan kunci website (fail open).
    return { maintenance: false, message: MAINTENANCE_DEFAULT_MESSAGE };
  }
}
