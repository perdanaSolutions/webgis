import {
  fetchMaintenanceStatus,
  isMaintenancePath,
  maintenanceRedirect,
  MAINTENANCE_POLL_MS,
  MAINTENANCE_STATE_KEY,
  type MaintenanceStatus,
} from "~/utils/maintenance";

// Cadangan: cek berkala setiap 30 menit (login enter + ganti menu tetap jadi pemicu utama).
export default defineNuxtPlugin((nuxtApp) => {
  const config = useRuntimeConfig();
  const router = useRouter();
  const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null);

  async function check() {
    const route = router.currentRoute.value;
    // Di /maintenance?reason=server-error pemulihan ditangani halaman itu sendiri.
    if (isMaintenancePath(route.path) && route.query.reason === "server-error") return;
    const status = await fetchMaintenanceStatus(String(config.public.apiBaseUrlPython || ""));
    state.value = status;
    const target = maintenanceRedirect(route.path, status.maintenance, route.query.reason);
    if (target) await nuxtApp.runWithContext(() => navigateTo(target, { replace: true }));
  }

  window.setInterval(check, MAINTENANCE_POLL_MS);
});
