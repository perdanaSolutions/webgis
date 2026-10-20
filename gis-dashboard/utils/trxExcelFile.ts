import { normalizeCell, type TrxKindSpec } from "./trxUpload";

export type ExcelPreview = {
  sheetName: string;
  headers: string[];
  rows: Record<string, string>[];
};

function cellText(value: unknown) {
  if (value == null) return "";
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${value.getFullYear()}-${month}-${day}`;
  }
  return normalizeCell(value);
}

function isEmptyRow(row: unknown[]) {
  return row.every((value) => cellText(value) === "");
}

export async function readExcelPreview(file: File): Promise<ExcelPreview> {
  const XLSX = await import("xlsx");
  const workbook = XLSX.read(await file.arrayBuffer(), { type: "array", cellDates: true });
  const sheetName = workbook.SheetNames[0];
  if (!sheetName) throw new Error("File Excel tidak memiliki sheet.");

  const matrix = XLSX.utils.sheet_to_json<unknown[]>(workbook.Sheets[sheetName], {
    header: 1,
    defval: null,
    raw: true,
  });
  while (matrix.length > 0 && isEmptyRow(matrix[matrix.length - 1] ?? [])) matrix.pop();
  if (!matrix.length) {
    throw new Error("Sheet pertama kosong. Baris pertama harus berisi nama kolom.");
  }

  const headerRow = matrix[0] ?? [];
  const headers = headerRow.map((value) => cellText(value));
  while (headers.length && !headers[headers.length - 1]) headers.pop();
  if (!headers.length) throw new Error("Baris pertama harus berisi nama kolom.");
  if (headers.some((header) => !header)) {
    throw new Error("Ada nama kolom yang kosong di baris pertama. Isi semua header sebelum kolom terakhir.");
  }
  const duplicated = headers.filter((header, index) => headers.indexOf(header) !== index);
  if (duplicated.length) {
    throw new Error(`Nama kolom dobel: ${[...new Set(duplicated)].join(", ")}.`);
  }

  const rows = matrix.slice(1).map((row) => {
    const display: Record<string, string> = {};
    headers.forEach((header, index) => {
      display[header] = cellText(row?.[index]);
    });
    return display;
  });

  return { sheetName, headers, rows };
}

export async function buildExcelTemplate(spec: TrxKindSpec) {
  const XLSX = await import("xlsx");
  const workbook = XLSX.utils.book_new();
  const example = spec.columns.map((column) => spec.example[column] ?? "");

  const dataSheet = XLSX.utils.aoa_to_sheet([spec.columns]);
  dataSheet["!cols"] = spec.columns.map((column) => ({ wch: Math.max(column.length + 2, 14) }));
  XLSX.utils.book_append_sheet(workbook, dataSheet, "Data");

  const exampleSheet = XLSX.utils.aoa_to_sheet([spec.columns, example]);
  exampleSheet["!cols"] = dataSheet["!cols"];
  XLSX.utils.book_append_sheet(workbook, exampleSheet, "Contoh");

  const notes = [
    ["Yang diimpor hanya sheet Data. Sheet Contoh dan Petunjuk tidak dibaca."],
    ["Ganti isi sheet Data. Jangan mengunggah sheet Contoh sebagai data sungguhan."],
    ...spec.rules.map((rule) => [rule]),
  ];
  const noteSheet = XLSX.utils.aoa_to_sheet(notes);
  noteSheet["!cols"] = [{ wch: 110 }];
  XLSX.utils.book_append_sheet(workbook, noteSheet, "Petunjuk");
  return workbook;
}

export async function downloadExcelTemplate(spec: TrxKindSpec) {
  const XLSX = await import("xlsx");
  const workbook = await buildExcelTemplate(spec);
  const output = XLSX.write(workbook, { bookType: "xlsx", type: "array" }) as ArrayBuffer | Uint8Array | number[];
  const bytes = output instanceof ArrayBuffer
    ? new Uint8Array(output)
    : ArrayBuffer.isView(output)
      ? new Uint8Array(output.buffer, output.byteOffset, output.byteLength)
      : Uint8Array.from(output);
  const blob = new Blob([bytes], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = spec.excelFilename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadJsonTemplate(spec: TrxKindSpec) {
  const payload = {
    sumber: "template",
    data: [spec.example],
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = spec.jsonFilename;
  link.click();
  URL.revokeObjectURL(url);
}
