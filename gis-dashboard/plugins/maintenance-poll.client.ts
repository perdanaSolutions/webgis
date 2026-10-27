import { fetchMaintenanceStatus, maintenanceRedirect, MAINTENANCE_POLL_MS, MAINTENANCE_STATE_KEY, type MaintenanceStatus } from "~/utils/maintenance";

// Cek berkala agar user yang sedang membuka halaman ikut dialihkan saat maintenance
// dinyalakan, dan kembali ke beranda saat dimatikan.
export default defineNuxtPlugin((nuxtApp) => {
  const config = useRuntimeConfig();
  const router = useRouter();
  const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null);

  async function check() {
    const status = await fetchMaintenanceStatus(String(config.public.apiBaseUrlPython || ""));
    state.value = status;
    const target = maintenanceRedirect(router.currentRoute.value.path, status.maintenance);
    if (target) await nuxtApp.runWithContext(() => navigateTo(target, { replace: true }));
  }

  window.setInterval(check, MAINTENANCE_POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") check();
  });
});
