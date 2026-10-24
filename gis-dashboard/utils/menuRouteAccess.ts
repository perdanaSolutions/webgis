export type MenuRouteNode = {
  id: string;
  to?: string | null;
  children?: MenuRouteNode[];
};

/** Halaman aplikasi yang tidak boleh dibuka tanpa hak menu, termasuk lewat URL langsung. */
export const PROTECTED_PAGE_PATHS = [
  "/roles",
  "/users",
  "/menus",
  "/permissions",
  "/map",
  "/transaksi",
  "/document",
  "/riwayat",
  "/pengumuman",
] as const;

export const MENU_ROUTE_UNLOCKED_KEY = "menu-route-unlocked";
export const MENU_ROUTE_CHECKING_KEY = "menu-route-checking";
export const MENU_ACCESS_DENIED_KEY = "menu-access-denied";

export type MenuRouteDecision = {
  allowed: boolean;
  redirectTo: string | null;
  /** true bila user memang tidak punya hak menu ini, bukan karena katalog gagal dimuat. */
  denied: boolean;
};

const ALLOWED: MenuRouteDecision = Object.freeze({
  allowed: true,
  redirectTo: null,
  denied: false,
});

export function markMenuAccessDenied() {
  const denied = useState(MENU_ACCESS_DENIED_KEY, () => false);
  denied.value = true;
  if (import.meta.client) sessionStorage.setItem(MENU_ACCESS_DENIED_KEY, "1");
}

export function menuAccessDeniedPending() {
  const denied = useState(MENU_ACCESS_DENIED_KEY, () => false);
  if (denied.value) return true;
  return import.meta.client && sessionStorage.getItem(MENU_ACCESS_DENIED_KEY) === "1";
}

export function clearMenuAccessDenied() {
  const denied = useState(MENU_ACCESS_DENIED_KEY, () => false);
  denied.value = false;
  if (import.meta.client) sessionStorage.removeItem(MENU_ACCESS_DENIED_KEY);
}

const PATH_ALIASES: Record<string, string> = {
  "/transaski": "/transaksi",
};

const SHELL_PATHS = new Set(["/", "/login", "/dashboard"]);

export function normalizeMenuId(value: unknown) {
  return String(value ?? "").trim().toLowerCase();
}

export function normalizeMenuRoute(value: unknown) {
  const raw = String(value ?? "").trim();
  if (!raw || /^[a-z][a-z0-9+.-]*:/i.test(raw)) return "";
  const path = raw.split(/[?#]/)[0]?.replace(/\/+$/, "") ?? "";
  if (!path || path === "/") return path === "/" ? "/" : "";
  const withSlash = path.startsWith("/") ? path : `/${path}`;
  return withSlash.toLowerCase();
}

export function isShellPath(path: string) {
  const normalized = normalizeMenuRoute(path);
  return !normalized || SHELL_PATHS.has(normalized);
}

export function canonicalMenuRoute(path: string) {
  const normalized = normalizeMenuRoute(path);
  return PATH_ALIASES[normalized] ?? normalized;
}

function collectMenus(items: MenuRouteNode[] | null | undefined) {
  const result: MenuRouteNode[] = [];
  const walk = (nodes: MenuRouteNode[]) => {
    for (const node of nodes) {
      result.push(node);
      if (node.children?.length) walk(node.children);
    }
  };
  walk(items ?? []);
  return result;
}

export function menuRouteMatchesPath(menuPath: string, currentPath: string) {
  if (!menuPath || menuPath === "/") return menuPath === currentPath;
  return currentPath === menuPath || currentPath.startsWith(`${menuPath}/`);
}

export function findControllingMenus(items: MenuRouteNode[], path: string) {
  const current = normalizeMenuRoute(path);
  if (!current || current === "/") return [];
  const matches = collectMenus(items).filter((item) =>
    menuRouteMatchesPath(normalizeMenuRoute(item.to), current),
  );
  if (!matches.length) return [];
  const longest = Math.max(
    ...matches.map((item) => normalizeMenuRoute(item.to).length),
  );
  return matches.filter((item) => normalizeMenuRoute(item.to).length === longest);
}

function isProtectedPage(path: string) {
  return PROTECTED_PAGE_PATHS.some(
    (page) => path === page || path.startsWith(`${page}/`),
  );
}

export function resolveMenuRouteAccess(options: {
  path: string;
  menus: MenuRouteNode[];
  allowedMenuIds: Iterable<string>;
  isSuperAdmin?: boolean;
  catalogReady: boolean;
}): MenuRouteDecision {
  const path = canonicalMenuRoute(options.path);
  if (!path || SHELL_PATHS.has(path) || options.isSuperAdmin) return ALLOWED;
  if (!options.catalogReady) {
    return { allowed: false, redirectTo: "/dashboard", denied: false };
  }

  const allowed = new Set(
    [...options.allowedMenuIds].map((id) => normalizeMenuId(id)).filter(Boolean),
  );
  const raw = normalizeMenuRoute(options.path);
  const controlling = findControllingMenus(options.menus, path);
  if (raw && raw !== path) controlling.push(...findControllingMenus(options.menus, raw));
  if (controlling.length) {
    const permitted = controlling.some((item) =>
      allowed.has(normalizeMenuId(item.id)),
    );
    return permitted ? ALLOWED : { allowed: false, redirectTo: "/dashboard", denied: true };
  }

  if (isProtectedPage(path)) {
    return { allowed: false, redirectTo: "/dashboard", denied: true };
  }

  return ALLOWED;
}
