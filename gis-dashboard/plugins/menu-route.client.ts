import { isShellPath } from "~/utils/menuRouteAccess";

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.hook("app:mounted", async () => {
    const auth = useAuthStore();
    auth.hydrateUser();

    const path = window.location.pathname;
    if (isShellPath(path)) return;

    const { unlocked, enforce } = useMenuRouteGuard();
    if (unlocked.value) return;

    const redirectPath = await enforce(path);
    if (!redirectPath || isShellPath(window.location.pathname)) return;

    await nuxtApp.runWithContext(() => navigateTo(redirectPath, { replace: true }));
    if (window.location.pathname !== redirectPath) {
      window.location.replace(redirectPath);
    }
  });
});
