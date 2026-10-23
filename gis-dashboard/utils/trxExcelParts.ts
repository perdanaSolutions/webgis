/** Pecah baris Excel transaksi jadi beberapa part untuk antrian upload (sama konsepnya dengan GeoJSON). */

import type { ExcelPreview } from "./trxExcelFile";

export const TRX_ROWS_PER_PART = 2000;

export type TrxRowPart = {
  headers: string[];
  rows: Record<string, string>[];
};

export function chunkTrxRows(
  headers: string[],
  rows: Record<string, string>[],
  size = TRX_ROWS_PER_PART,
): TrxRowPart[] {
  if (!rows.length) return [];
  const parts: TrxRowPart[] = [];
  for (let i = 0; i < rows.length; i += size) {
    parts.push({ headers, rows: rows.slice(i, i + size) });
  }
  return parts;
}

/** Offset baris Excel (nomor baris data pertama part) untuk `feature_offset` backend. */
export function partRowOffset(partIndex: number, size = TRX_ROWS_PER_PART): number {
  const dataRowsBefore = Math.max(0, (partIndex - 1) * size);
  return dataRowsBefore + 1;
}

export async function rowsToExcelFile(
  part: TrxRowPart,
  baseName: string,
  partIndex: number,
  partTotal: number,
): Promise<File> {
  const XLSX = await import("xlsx");
  const matrix = [part.headers, ...part.rows.map((row) => part.headers.map((h) => row[h] ?? ""))];
  const sheet = XLSX.utils.aoa_to_sheet(matrix);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, "Data");
  const output = XLSX.write(workbook, { bookType: "xlsx", type: "array" }) as ArrayBuffer | Uint8Array | number[];
  const bytes = output instanceof ArrayBuffer
    ? new Uint8Array(output)
    : ArrayBuffer.isView(output)
      ? new Uint8Array(output.buffer, output.byteOffset, output.byteLength)
      : Uint8Array.from(output);
  const stem = baseName.replace(/\.(xlsx|xls)$/i, "") || "upload";
  return new File([bytes], `${stem}.part${partIndex}of${partTotal}.xlsx`, {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
}

export function previewFromParts(parts: TrxRowPart[]): Pick<ExcelPreview, "headers" | "rows"> {
  if (!parts.length) return { headers: [], rows: [] };
  const headers = parts[0]!.headers;
  return { headers, rows: parts.flatMap((p) => p.rows) };
}
