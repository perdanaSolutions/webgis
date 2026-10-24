import { isAccessTokenExpired } from "~/utils/authSession";
import { isShellPath, MENU_ROUTE_CHECKING_KEY, MENU_ROUTE_UNLOCKED_KEY } from "~/utils/menuRouteAccess";

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();
  const unlocked = useState(MENU_ROUTE_UNLOCKED_KEY, () => false);
  const checking = useState(MENU_ROUTE_CHECKING_KEY, () => false);

  if (to.path === "/login") {
    if (auth.token && isAccessTokenExpired(auth.token)) auth.clearAuthData();
    checking.value = false;
    return;
  }

  if (!auth.token || isAccessTokenExpired(auth.token)) {
    auth.clearAuthData();
    unlocked.value = false;
    checking.value = false;
    return navigateTo("/login", { replace: true });
  }

  if (isShellPath(to.path)) {
    checking.value = false;
    return;
  }

  if (import.meta.server) {
    unlocked.value = false;
    checking.value = false;
    return;
  }

  const nuxtApp = useNuxtApp();
  const redirectTo = (path: string) =>
    nuxtApp.runWithContext(() => navigateTo(path, { replace: true }));

  const { enforce } = useMenuRouteGuard();
  const redirectPath = await enforce(to.path);
  if (redirectPath) return redirectTo(redirectPath);
});
