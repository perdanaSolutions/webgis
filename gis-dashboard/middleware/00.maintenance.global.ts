import {
  fetchMaintenanceStatus,
  maintenanceRedirect,
  shouldFetchMaintenanceOnRoute,
  MAINTENANCE_STATE_KEY,
  type MaintenanceStatus,
} from "~/utils/maintenance";

// Berjalan sebelum auth.global, di setiap navigasi (termasuk load pertama / SSR).
export default defineNuxtRouteMiddleware(async (to) => {
  const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null);
  const opts = { fullPath: to.fullPath, from: to.query.from };

  if (!shouldFetchMaintenanceOnRoute(to.path)) {
    // Di /maintenance: halaman sendiri yang polling & mengembalikan user.
    return;
  }

  const config = useRuntimeConfig();
  const baseURL = String(
    (import.meta.server ? config.apiBaseUrlPythonServer : "") || config.public.apiBaseUrlPython || "",
  );
  const status = await fetchMaintenanceStatus(baseURL);
  state.value = status;
  const target = maintenanceRedirect(to.path, status.maintenance, to.query.reason, opts);
  if (target) return navigateTo(target, { replace: true });
});
