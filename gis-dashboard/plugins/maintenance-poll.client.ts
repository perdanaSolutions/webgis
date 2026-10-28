import {
  fetchMaintenanceStatus,
  isMaintenancePath,
  isOnMaintenancePage,
  maintenanceRedirect,
  MAINTENANCE_POLL_MS,
  MAINTENANCE_STATE_KEY,
  type MaintenanceStatus,
} from "~/utils/maintenance";

// Cek berkala setiap 30 detik di halaman selain /maintenance (halaman itu polling sendiri).
export default defineNuxtPlugin((nuxtApp) => {
  const config = useRuntimeConfig();
  const router = useRouter();
  const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null);

  async function check() {
    const route = router.currentRoute.value;
    if (isMaintenancePath(route.path) || isOnMaintenancePage(window.location.pathname, config.app.baseURL)) return;
    const status = await fetchMaintenanceStatus(String(config.public.apiBaseUrlPython || ""));
    state.value = status;
    const target = maintenanceRedirect(route.path, status.maintenance, route.query.reason, {
      fullPath: route.fullPath,
    });
    if (target) await nuxtApp.runWithContext(() => navigateTo(target, { replace: true }));
  }

  window.setInterval(check, MAINTENANCE_POLL_MS);
});
