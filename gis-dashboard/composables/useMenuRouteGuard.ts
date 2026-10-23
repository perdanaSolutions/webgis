import { dashboardStore } from "~/stores/dashboardStore";
import {
  isShellPath,
  MENU_ROUTE_CHECKING_KEY,
  MENU_ROUTE_UNLOCKED_KEY,
  resolveMenuRouteAccess,
} from "~/utils/menuRouteAccess";

let enforceGeneration = 0;

export function useMenuRouteGuard() {
  const unlocked = useState(MENU_ROUTE_UNLOCKED_KEY, () => false);
  const checking = useState(MENU_ROUTE_CHECKING_KEY, () => false);

  async function enforce(path: string) {
    const ticket = ++enforceGeneration;
    const stale = () => ticket !== enforceGeneration;
    const auth = useAuthStore();

    if (isShellPath(path) || auth.isSuperAdmin) {
      if (!stale()) {
        checking.value = false;
        if (auth.isSuperAdmin) unlocked.value = true;
      }
      return null;
    }

    unlocked.value = false;
    checking.value = true;

    try {
      const dashboard = dashboardStore();
      let catalogReady = dashboard.menuCatalogReady;
      if (!catalogReady) {
        try {
          await dashboard.ensureMenuCatalog();
          catalogReady = true;
        } catch {
          catalogReady = false;
        }
      }

      if (stale()) return null;

      const decision = resolveMenuRouteAccess({
        path,
        menus: dashboard.menuCatalog,
        allowedMenuIds: auth.user?.akses_menu ?? [],
        isSuperAdmin: auth.isSuperAdmin,
        catalogReady,
      });

      unlocked.value = decision.allowed;
      if (!decision.allowed && decision.redirectTo && decision.redirectTo !== path) {
        return decision.redirectTo;
      }
      return null;
    } finally {
      if (!stale()) checking.value = false;
    }
  }

  return { unlocked, checking, enforce };
}
