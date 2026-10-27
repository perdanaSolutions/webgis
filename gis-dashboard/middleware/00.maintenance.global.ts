import {
  fetchMaintenanceStatus,
  maintenanceRedirect,
  shouldFetchMaintenanceOnRoute,
  MAINTENANCE_STATE_KEY,
  type MaintenanceStatus,
} from "~/utils/maintenance";

// Berjalan sebelum auth.global.
// Hit API hanya: masuk/reload login, atau ganti menu saat sudah login.
export default defineNuxtRouteMiddleware(async (to) => {
  const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null);

  let isAuthenticated = false;
  try {
    isAuthenticated = Boolean(useAuthStore().token);
  } catch {
    isAuthenticated = false;
  }

  if (!shouldFetchMaintenanceOnRoute(to.path, isAuthenticated)) {
    if (state.value != null) {
      const target = maintenanceRedirect(to.path, state.value.maintenance);
      if (target) return navigateTo(target, { replace: true });
    }
    return;
  }

  const config = useRuntimeConfig();
  const baseURL = String(
    (import.meta.server ? config.apiBaseUrlPythonServer : "") || config.public.apiBaseUrlPython || "",
  );
  const status = await fetchMaintenanceStatus(baseURL);
  state.value = status;
  const target = maintenanceRedirect(to.path, status.maintenance);
  if (target) return navigateTo(target, { replace: true });
});
