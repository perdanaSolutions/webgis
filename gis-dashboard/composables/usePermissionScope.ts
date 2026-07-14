import { computed } from "vue";
import type { PermissionItem } from "~/stores/managePermissionStore";

export type PermissionScopeCategory =
  | "menu"
  | "pt"
  | "estate"
  | "transaction"
  | "general";

export type PermissionScope = {
  menu: PermissionItem[];
  pt: PermissionItem[];
  estate: PermissionItem[];
  transaction: PermissionItem[];
  general: PermissionItem[];
};

export type ParsedPermissionMeta = {
  category: PermissionScopeCategory;
  ptCode: string | null;
  estateCode: string | null;
  transactionCode: string | null;
};

const TRANSACTION_HINTS = [
  "transaksi",
  "transaction",
  "panen",
  "produksi",
  "pupuk",
  "infrastruktur",
  "jalan",
  "drainase",
  "jembatan",
];

function normalize(input: string | null | undefined) {
  return (input ?? "").trim().toLowerCase();
}

function tokenize(input: string | null | undefined) {
  return normalize(input)
    .replace(/[^a-z0-9:_\- ]+/g, " ")
    .split(/[\s:_\-]+/)
    .filter(Boolean);
}

function parseCodeValue(code: string) {
  const segments = normalize(code).split(":").filter(Boolean);
  const head = segments[0] ?? "";
  const tail = segments.slice(1);
  return { head, tail, segments };
}

function inferTransactionCode(value: string): string | null {
  const tokens = tokenize(value);
  const found = TRANSACTION_HINTS.find((hint) => tokens.includes(hint));
  return found ?? null;
}

function inferPtCode(value: string): string | null {
  const v = normalize(value);

  const direct = v.match(/\bpt[\s:_-]*([a-z0-9]+)/i);
  if (direct?.[1]) return `pt-${direct[1].toLowerCase()}`;

  const tokens = tokenize(v);
  const ptIndex = tokens.findIndex((t) => t === "pt");
  if (ptIndex >= 0 && tokens[ptIndex + 1]) {
    return `pt-${tokens[ptIndex + 1]}`;
  }

  return null;
}

function inferEstateCode(value: string): string | null {
  const v = normalize(value);

  const direct = v.match(/\bestate[\s:_-]*([a-z0-9]+)/i);
  if (direct?.[1]) return `estate-${direct[1].toLowerCase()}`;

  const tokens = tokenize(v);
  const estIndex = tokens.findIndex((t) => t === "estate");
  if (estIndex >= 0 && tokens[estIndex + 1]) {
    return `estate-${tokens[estIndex + 1]}`;
  }

  return null;
}

export function parsePermissionMeta(
  permission: PermissionItem,
): ParsedPermissionMeta {
  const kode = normalize(permission.kode);
  const resource = normalize(permission.resource);
  const aksi = normalize(permission.aksi);
  const deskripsi = normalize(permission.deskripsi);

  const parsedCode = parseCodeValue(kode);
  const merged = `${kode} ${resource} ${aksi} ${deskripsi}`;

  const hasMenuHint =
    resource.includes("menu") ||
    kode.includes("menu") ||
    deskripsi.includes("menu") ||
    deskripsi.includes("modul");

  const hasPtHint =
    resource.includes("pt") || kode.includes("pt") || deskripsi.includes("pt");

  const hasEstateHint =
    resource.includes("estate") ||
    kode.includes("estate") ||
    deskripsi.includes("estate");

  const hasTransactionHint =
    resource.includes("transaction") ||
    resource.includes("transaksi") ||
    kode.includes("transaction") ||
    kode.includes("transaksi") ||
    TRANSACTION_HINTS.some((hint) => merged.includes(hint));

  let category: PermissionScopeCategory = "general";

  if (hasMenuHint || parsedCode.head === "menu") category = "menu";
  else if (hasEstateHint || parsedCode.head === "estate") category = "estate";
  else if (hasPtHint || parsedCode.head === "pt") category = "pt";
  else if (
    hasTransactionHint ||
    parsedCode.head === "transaksi" ||
    parsedCode.head === "transaction"
  ) {
    category = "transaction";
  }

  return {
    category,
    ptCode: inferPtCode(merged),
    estateCode: inferEstateCode(merged),
    transactionCode: inferTransactionCode(merged),
  };
}

export function usePermissionScope(permissionsSource: () => PermissionItem[]) {
  const grouped = computed<PermissionScope>(() => {
    const bucket: PermissionScope = {
      menu: [],
      pt: [],
      estate: [],
      transaction: [],
      general: [],
    };

    permissionsSource().forEach((permission) => {
      const meta = parsePermissionMeta(permission);
      bucket[meta.category].push(permission);
    });

    return bucket;
  });

  const groupedWithMeta = computed(() => {
    return permissionsSource().map((permission) => ({
      permission,
      meta: parsePermissionMeta(permission),
    }));
  });

  return {
    grouped,
    groupedWithMeta,
    parsePermissionMeta,
  };
}
