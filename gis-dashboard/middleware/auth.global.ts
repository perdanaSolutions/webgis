import { isAccessTokenExpired } from "~/utils/authSession";

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();

  if (to.path === "/login") {
    if (auth.token && isAccessTokenExpired(auth.token)) auth.clearAuthData();
    return;
  }

  if (!auth.token || isAccessTokenExpired(auth.token)) {
    auth.clearAuthData();
    return navigateTo("/login", { replace: true });
  }

  if (import.meta.server || useNuxtApp().isHydrating) return;

  auth.hydrateUser();
  if (auth.user?.id) return;

  const nuxtApp = useNuxtApp();
  const me = await auth.validateToken({ redirect: false });
  if (!me) {
    return nuxtApp.runWithContext(() => navigateTo("/login", { replace: true }));
  }
});
