/** Utilitas tabel berhalaman untuk rincian hasil analisa. */
export const PAGE_SIZES = [10, 25, 50, 100] as const;

export function humanizeColumn(key: string): string {
  return String(key)
    .replace(/_/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Array apa pun -> baris objek. Array string/angka menjadi tabel satu kolom. */
export function toTableRows(
  value: unknown[],
  scalarColumn = "nilai",
): { columns: string[]; rows: Record<string, unknown>[] } {
  const rows = value.map((row) =>
    typeof row === "object" && row !== null && !Array.isArray(row)
      ? (row as Record<string, unknown>)
      : { [scalarColumn]: row },
  );
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  return { columns, rows };
}

export function paginate<T>(rows: T[], page: number, pageSize: number): {
  items: T[];
  page: number;
  totalPages: number;
  total: number;
  start: number;
  end: number;
} {
  const total = rows.length;
  const size = Math.max(1, Math.floor(pageSize) || 10);
  const totalPages = Math.max(1, Math.ceil(total / size));
  const current = Math.min(Math.max(1, Math.floor(page) || 1), totalPages);
  const startIdx = (current - 1) * size;
  const items = rows.slice(startIdx, startIdx + size);
  return {
    items,
    page: current,
    totalPages,
    total,
    start: total ? startIdx + 1 : 0,
    end: startIdx + items.length,
  };
}

export function formatCell(value: unknown): string {
  if (value == null || value === "") return "-";
  if (Array.isArray(value)) {
    return value.every((v) => typeof v !== "object" || v === null) ? value.join(", ") : JSON.stringify(value);
  }
  if (typeof value === "number") return value.toLocaleString("id-ID");
  if (typeof value === "boolean") return value ? "Ya" : "Tidak";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
