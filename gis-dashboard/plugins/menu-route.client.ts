import { watch } from "vue";
import { isShellPath } from "~/utils/menuRouteAccess";

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.hook("app:mounted", async () => {
    const { unlocked, checking, enforce } = useMenuRouteGuard();

    if (checking.value) {
      await new Promise<void>((resolve) => {
        const stop = watch(checking, (value) => {
          if (!value) {
            stop();
            resolve();
          }
        });
      });
    }

    const path = window.location.pathname;
    if (isShellPath(path) || unlocked.value) return;

    const redirectPath = await enforce(path);
    if (!redirectPath || isShellPath(window.location.pathname) || unlocked.value) return;

    await nuxtApp.runWithContext(() => navigateTo(redirectPath, { replace: true }));
    if (window.location.pathname !== redirectPath) {
      window.location.replace(redirectPath);
    }
  });
});
