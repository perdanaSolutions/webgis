import { pendingServerErrorRedirect } from "~/utils/serverErrorRedirect";
import { dashboardStore } from "~/stores/dashboardStore";
import {
  canonicalMenuRoute,
  isShellPath,
  markMenuAccessDenied,
  MENU_ROUTE_CHECKING_KEY,
  MENU_ROUTE_UNLOCKED_KEY,
  resolveMenuRouteAccess,
  type MenuRouteDecision,
  type MenuRouteNode,
} from "~/utils/menuRouteAccess";

const CATALOG_CACHE_KEY = "menu-route-catalog-v1";
const CATALOG_WAIT_MS = 8000;

let enforceGeneration = 0;
let inflight: Promise<string | null> | null = null;
let inflightPath = "";

function readCatalogCache(): MenuRouteNode[] | null {
  if (!import.meta.client) return null;
  try {
    const raw = sessionStorage.getItem(CATALOG_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as MenuRouteNode[]) : null;
  } catch {
    return null;
  }
}

function writeCatalogCache(menus: MenuRouteNode[]) {
  if (!import.meta.client) return;
  try {
    sessionStorage.setItem(CATALOG_CACHE_KEY, JSON.stringify(menus));
  } catch {
    // Kuota sessionStorage penuh tidak boleh menahan redirect.
  }
}

function denyRedirect(path: string, decision: MenuRouteDecision) {
  if (decision.allowed || !decision.redirectTo || decision.redirectTo === path) return null;
  if (decision.denied) markMenuAccessDenied();
  return decision.redirectTo;
}

async function catalogBecomesReady(dashboard: ReturnType<typeof dashboardStore>) {
  if (dashboard.menuCatalogReady) return true;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const pending = dashboard.ensureMenuCatalog().then((menus) => {
    writeCatalogCache(menus);
    return true;
  }).catch(() => dashboard.menuCatalogReady);
  try {
    return await Promise.race([
      pending,
      new Promise<boolean>((resolve) => {
        timer = setTimeout(() => resolve(dashboard.menuCatalogReady), CATALOG_WAIT_MS);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export function useMenuRouteGuard() {
  const unlocked = useState(MENU_ROUTE_UNLOCKED_KEY, () => false);
  const checking = useState(MENU_ROUTE_CHECKING_KEY, () => false);

  async function execute(path: string) {
    const ticket = ++enforceGeneration;
    const stale = () => ticket !== enforceGeneration;
    const auth = useAuthStore();
    const target = canonicalMenuRoute(path);

    auth.hydrateUser();
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
      if (!auth.user?.id || !auth.hasStoredFullProfile()) {
        const me = await auth.validateToken({ redirect: false });
        if (!me) return pendingServerErrorRedirect() ?? "/login";
      }
      if (stale()) return null;
      if (auth.isSuperAdmin) {
        unlocked.value = true;
        return null;
      }

      const allowedMenuIds = auth.user?.akses_menu ?? [];
      if (!allowedMenuIds.length) {
        const decision = resolveMenuRouteAccess({
          path,
          menus: [],
          allowedMenuIds,
          catalogReady: true,
        });
        unlocked.value = decision.allowed;
        return denyRedirect(target, decision);
      }

      const dashboard = dashboardStore();
      const cached = dashboard.menuCatalogReady ? null : readCatalogCache();
      if (cached?.length) {
        const decision = resolveMenuRouteAccess({
          path,
          menus: cached,
          allowedMenuIds,
          catalogReady: true,
        });
        unlocked.value = decision.allowed;
        const redirectTo = denyRedirect(target, decision);
        if (redirectTo || decision.allowed) {
          void dashboard.ensureMenuCatalog().then((menus) => writeCatalogCache(menus)).catch(() => undefined);
          return redirectTo;
        }
      }

      const ready = await catalogBecomesReady(dashboard);
      if (stale()) return null;
      if (ready) writeCatalogCache(dashboard.menuCatalog);

      const decision = resolveMenuRouteAccess({
        path,
        menus: dashboard.menuCatalog,
        allowedMenuIds,
        catalogReady: ready,
        isSuperAdmin: auth.isSuperAdmin,
      });
      unlocked.value = decision.allowed;
      return denyRedirect(target, decision);
    } finally {
      if (!stale()) checking.value = false;
    }
  }

  function enforce(path: string) {
    const key = canonicalMenuRoute(path) || path;
    if (inflight && inflightPath === key) return inflight;
    inflightPath = key;
    const run = execute(path).finally(() => {
      if (inflight === run) inflight = null;
    });
    inflight = run;
    return run;
  }

  return { unlocked, checking, enforce };
}
