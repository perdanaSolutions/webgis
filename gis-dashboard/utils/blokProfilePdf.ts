import { BUDGET_GAP_LAYERS, type LegendItem, type OverlayStyle } from "./mapLayers";

export type PdfSwatch = { label: string; color: string };

export type PdfOverlayLegend = {
  name: string;
  legend: LegendItem[];
  style: Pick<OverlayStyle, "defaultColor">;
};

/** Nama berkas unduhan. Karakter di luar huruf, angka, dan tanda hubung menjadi garis bawah. */
export function pdfFileName(scope: string) {
  const slug = scope
    .replace(/[^\w-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .toLowerCase();
  return `blok-profile-${slug || "semua-wilayah"}.pdf`;
}

/** Swatch legenda hanya untuk batas dan layer yang sedang aktif. */
export function buildPdfLegend(input: {
  showBlocks: boolean;
  showYieldGap: boolean;
  /** Legenda tahun tanam; kosong bila layer Tahun Tanam mati. */
  plantingYears?: LegendItem[];
  budgetColors: Record<string, boolean>;
  overlays: PdfOverlayLegend[];
}): PdfSwatch[] {
  const items: PdfSwatch[] = [];
  if (input.showBlocks) items.push({ label: "Batas blok", color: "#d4d4d4" });
  if (input.showYieldGap) {
    for (const item of BUDGET_GAP_LAYERS) {
      if (input.budgetColors[item.key] === false) continue;
      items.push({ label: item.label, color: item.color });
    }
  }
  for (const item of input.plantingYears ?? []) items.push(item);
  for (const layer of input.overlays) {
    if (layer.legend.length) {
      for (const entry of layer.legend) items.push({ label: `${layer.name} · ${entry.label}`, color: entry.color });
    } else {
      items.push({ label: layer.name, color: layer.style.defaultColor });
    }
  }
  return items;
}

export function rgbOf(color: string): [number, number, number] {
  const match = /^#([\da-f]{3}|[\da-f]{6})$/i.exec(color.trim());
  if (!match?.[1]) return [99, 136, 64];
  const body = match[1].length === 3 ? match[1].split("").map((char) => char + char).join("") : match[1];
  return [parseInt(body.slice(0, 2), 16), parseInt(body.slice(2, 4), 16), parseInt(body.slice(4, 6), 16)];
}

/** Atribusi tile sering berisi HTML. PDF hanya membutuhkan teksnya. */
export function plainAttribution(html: string) {
  return html
    .replace(/<[^>]+>/g, "")
    .replace(/&copy;/g, "©")
    .replace(/&mdash;/g, "—")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * PDF dibangun peta dulu lalu kartu. Halaman kartu pertama (Informasi Blok) dipindah ke depan:
 * jsPDF.movePage(from, before). null bila belum ada halaman kartu.
 */
export function infoPageFirstMove(totalPages: number): { from: number; before: number } | null {
  return totalPages >= 2 ? { from: 2, before: 1 } : null;
}
