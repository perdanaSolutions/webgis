/**
 * Format angka kartu kanan /map (perbaikan 30 Okt 2026).
 *
 * - Maksimal 2 angka di belakang koma, DIPOTONG (bukan dibulatkan): 1,456 -> "1,45".
 * - Bilangan bulat tanpa desimal: 12 -> "12"; ada pecahan -> selalu 2 digit: 1,5 -> "1,50".
 * - Format Indonesia: titik ribuan, koma desimal: 12345,678 -> "12.345,67".
 * - Aman floating point (1,15 tidak menjadi 1,14) dan negatif dipotong ke arah nol (-1,456 -> "-1,45").
 */
export function truncateDecimal(value: number, digits = 2): number {
  if (!Number.isFinite(value)) return value;
  const [int, frac = ""] = decimalParts(Math.abs(value));
  const out = Number(`${int}.${frac.slice(0, digits) || "0"}`);
  return value < 0 && out !== 0 ? -out : out;
}

function decimalParts(abs: number): [string, string] {
  // toPrecision(12) membuang galat biner (1.15 -> 1.15, bukan 1.1499999...), lalu tulis tanpa notasi eksponen.
  const clean = Number(abs.toPrecision(12));
  const text = clean >= 1e21 ? clean.toLocaleString("en-US", { useGrouping: false, maximumFractionDigits: 0 })
    : clean.toFixed(12);
  const [int, frac = ""] = text.split(".");
  return [int ?? "0", frac];
}

export function formatDecimalId(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined || value === "") return fallback;
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  const [int, rawFrac] = decimalParts(Math.abs(n));
  const cut = rawFrac.slice(0, 2);
  const frac = /[1-9]/.test(cut) ? cut.padEnd(2, "0") : "";
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const sign = n < 0 && (int !== "0" || frac) ? "-" : "";
  return `${sign}${grouped}${frac ? `,${frac}` : ""}`;
}
