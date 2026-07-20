import { computed } from "vue";
import { useAuthStore } from "~/stores/authStore";

export type AccessScope = {
  menuAccess: string[];
  ptAccess: string[];
  estateAccess: string[];
  transactionAccess: string[];
};

function normalize(value: string) {
  return value.trim().toLowerCase();
}

function parseToken(value: string) {
  const v = normalize(value);
  const parts = v.split(":").filter(Boolean);
  return {
    raw: v,
    head: parts[0] ?? "",
    second: parts[1] ?? "",
    third: parts[2] ?? "",
    tokens: v.split(/[:_\-\s]+/).filter(Boolean),
  };
}

function unique(values: string[]) {
  return Array.from(new Set(values));
}

export function useAccessControl() {
  const authStore = useAuthStore();

  const permissions = computed(() => authStore.user?.permissions ?? []);

  const scope = computed<AccessScope>(() => {
    const menuAccess: string[] = [];
    const ptAccess: string[] = [];
    const estateAccess: string[] = [];
    const transactionAccess: string[] = [];

    permissions.value.forEach((permission) => {
      const parsed = parseToken(permission);

      if (
        parsed.head === "menu" ||
        parsed.tokens.includes("menu") ||
        parsed.tokens.includes("modul")
      ) {
        menuAccess.push(parsed.raw);
      }

      if (parsed.head === "pt" || parsed.tokens.includes("pt")) {
        ptAccess.push(parsed.raw);
      }

      if (parsed.head === "estate" || parsed.tokens.includes("estate")) {
        estateAccess.push(parsed.raw);
      }

      const txHints = [
        "transaksi",
        "transaction",
        "panen",
        "produksi",
        "pupuk",
        "infrastruktur",
      ];
      if (
        parsed.head === "transaksi" ||
        parsed.head === "transaction" ||
        txHints.some((hint) => parsed.tokens.includes(hint))
      ) {
        transactionAccess.push(parsed.raw);
      }
    });

    return {
      menuAccess: unique(menuAccess),
      ptAccess: unique(ptAccess),
      estateAccess: unique(estateAccess),
      transactionAccess: unique(transactionAccess),
    };
  });

  const isSuperAdmin = computed(
    () => normalize(authStore.user?.role ?? "") === "superadmin",
  );

  function hasPermission(code: string) {
    const normalized = normalize(code);
    if (!normalized) return false;
    if (isSuperAdmin.value) return true;
    return permissions.value.some((perm) => normalize(perm) === normalized);
  }

  function canAccessMenuPath(path: string) {
    const normalizedPath = normalize(path);
    if (!normalizedPath) return false;
    if (isSuperAdmin.value) return true;

    if (!scope.value.menuAccess.length) return true;

    return scope.value.menuAccess.some((permission) => {
      return permission.includes(normalizedPath.replace(/\//g, ""));
    });
  }

  function extractAllowedCodes(
    source: string[],
    prefix: "pt" | "estate" | "transaksi" | "transaction",
  ) {
    const results: string[] = [];

    source.forEach((permission) => {
      const parsed = parseToken(permission);
      if (
        parsed.head !== prefix &&
        !(prefix === "transaksi" && parsed.head === "transaction")
      )
        return;
      if (parsed.second) results.push(parsed.second);
      else if (parsed.third) results.push(parsed.third);
      else results.push(permission);
    });

    return unique(results);
  }

  const allowedPTCodes = computed(() => {
    if (isSuperAdmin.value) return [];
    return extractAllowedCodes(scope.value.ptAccess, "pt");
  });

  const allowedEstateCodes = computed(() => {
    if (isSuperAdmin.value) return [];
    return extractAllowedCodes(scope.value.estateAccess, "estate");
  });

  const allowedTransactions = computed(() => {
    if (isSuperAdmin.value) return [];
    const a = extractAllowedCodes(scope.value.transactionAccess, "transaksi");
    const b = extractAllowedCodes(scope.value.transactionAccess, "transaction");
    return unique([...a, ...b]);
  });

  return {
    permissions,
    scope,
    isSuperAdmin,
    hasPermission,
    canAccessMenuPath,
    allowedPTCodes,
    allowedEstateCodes,
    allowedTransactions,
  };
}
