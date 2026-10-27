import { fetchMaintenanceStatus, maintenanceRedirect, MAINTENANCE_STATE_KEY, type MaintenanceStatus } from "~/utils/maintenance";

// Berjalan sebelum auth.global agar saat maintenance semua halaman (termasuk login) dialihkan.
export default defineNuxtRouteMiddleware(async (to) => {
  const config = useRuntimeConfig();
  const baseURL = String(
    (import.meta.server ? config.apiBaseUrlPythonServer : "") || config.public.apiBaseUrlPython || "",
  );
  const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null);
  const status = await fetchMaintenanceStatus(baseURL);
  state.value = status;
  const target = maintenanceRedirect(to.path, status.maintenance);
  if (target) return navigateTo(target, { replace: true });
});
