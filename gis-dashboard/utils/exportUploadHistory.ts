import type { UploadHistoryItem } from "~/stores/uploadHistoryStore";

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

function formatPeriode(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("id-ID", { month: "long", year: "numeric" });
}

function statusLabel(status: string): string {
  switch (status) {
    case "SUCCESS": return "Berhasil";
    case "PARTIAL_SUCCESS": return "Berhasil Sebagian";
    case "FAILED": return "Gagal";
    case "IN_PROGRESS": return "Diproses";
    case "ABANDONED": return "Dibatalkan";
    default: return status;
  }
}

function sourceLabel(source: string): string {
  return source === "GEOJSON_UPLOAD" ? "GeoJSON" : source === "EXCEL_UPLOAD" ? "Excel" : source;
}

function makeTimestamp(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const h = String(now.getHours()).padStart(2, "0");
  const i = String(now.getMinutes()).padStart(2, "0");
  return `${y}${m}${d}_${h}${i}`;
}

export async function exportUploadHistoryExcel(items: UploadHistoryItem[], scopeLabel = "Semua Data"): Promise<void> {
  const XLSX = await import("xlsx");
  const headers = [
    "No",
    "Waktu Upload",
    "Nama File",
    "Sumber",
    "Tujuan (Layer / Tabel)",
    "Periode Data",
    "Jumlah Data",
    "Status",
    "Diupload Oleh",
    "Username Pengunggah",
  ];

  const rows = items.map((item, idx) => [
    idx + 1,
    formatDateTime(item.mulai),
    item.nama_file || "-",
    sourceLabel(item.jenis_sumber),
    item.layer ? `${item.layer} (${item.tabel_tujuan})` : item.tabel_tujuan,
    formatPeriode(item.periode),
    item.jumlah_data,
    statusLabel(item.status),
    item.diupload_oleh?.nama_lengkap || "User terhapus",
    item.diupload_oleh ? `@${item.diupload_oleh.username}` : "-",
  ]);

  const workbook = XLSX.utils.book_new();
  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows]);

  worksheet["!cols"] = [
    { wch: 6 },
    { wch: 22 },
    { wch: 30 },
    { wch: 14 },
    { wch: 30 },
    { wch: 20 },
    { wch: 14 },
    { wch: 18 },
    { wch: 25 },
    { wch: 18 },
  ];

  XLSX.utils.book_append_sheet(workbook, worksheet, "Riwayat Upload");
  XLSX.writeFile(workbook, `riwayat_upload_${makeTimestamp()}.xlsx`, { compression: true });
}

export async function exportUploadHistoryPdf(items: UploadHistoryItem[], scopeLabel = "Semua Data"): Promise<void> {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });

  const pageW = 297;
  const pageH = 210;
  const margin = 10;

  // Header
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(14);
  pdf.setTextColor(31, 42, 24);
  pdf.text("Laporan Riwayat Upload", margin, margin + 5);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(100, 100, 100);
  const printedAt = `Dicetak: ${new Date().toLocaleString("id-ID")} (${scopeLabel})`;
  pdf.text(printedAt, pageW - margin, margin + 5, { align: "right" });

  // Columns & widths
  const cols = [
    { name: "No", w: 10 },
    { name: "Waktu", w: 40 },
    { name: "Nama File", w: 65 },
    { name: "Tujuan", w: 55 },
    { name: "Jumlah", w: 25 },
    { name: "Status", w: 32 },
    { name: "Pengunggah", w: 50 },
  ];

  let y = margin + 14;
  const rowHeight = 7;
  const headerHeight = 8;

  function drawTableHeader(yPos: number) {
    pdf.setFillColor(240, 243, 238);
    pdf.rect(margin, yPos, pageW - margin * 2, headerHeight, "F");
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(8);
    pdf.setTextColor(31, 42, 24);

    let x = margin + 2;
    for (const col of cols) {
      pdf.text(col.name, x, yPos + 5.5);
      x += col.w;
    }
    return yPos + headerHeight;
  }

  y = drawTableHeader(y);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);

  for (let i = 0; i < items.length; i++) {
    if (y + rowHeight > pageH - 12) {
      pdf.addPage("a4", "landscape");
      y = drawTableHeader(margin + 5);
      pdf.setFont("helvetica", "normal");
      pdf.setFontSize(8);
    }

    const item = items[i]!;
    if (i % 2 === 1) {
      pdf.setFillColor(250, 251, 249);
      pdf.rect(margin, y, pageW - margin * 2, rowHeight, "F");
    }

    pdf.setTextColor(40, 40, 40);
    let x = margin + 2;

    // No
    pdf.text(String(i + 1), x, y + 4.8);
    x += cols[0]!.w;

    // Waktu
    pdf.text(formatDateTime(item.mulai), x, y + 4.8);
    x += cols[1]!.w;

    // Nama File
    const fileNameText = item.nama_file || "-";
    const truncatedFile = pdf.splitTextToSize(fileNameText, cols[2]!.w - 3)[0] ?? fileNameText;
    pdf.text(String(truncatedFile), x, y + 4.8);
    x += cols[2]!.w;

    // Tujuan
    const targetText = item.layer || item.tabel_tujuan;
    const truncatedTarget = pdf.splitTextToSize(targetText, cols[3]!.w - 3)[0] ?? targetText;
    pdf.text(String(truncatedTarget), x, y + 4.8);
    x += cols[3]!.w;

    // Jumlah Data
    pdf.text(item.jumlah_data.toLocaleString("id-ID"), x, y + 4.8);
    x += cols[4]!.w;

    // Status
    pdf.text(statusLabel(item.status), x, y + 4.8);
    x += cols[5]!.w;

    // Pengunggah
    const uploaderText = item.diupload_oleh?.nama_lengkap || "User terhapus";
    const truncatedUploader = pdf.splitTextToSize(uploaderText, cols[6]!.w - 3)[0] ?? uploaderText;
    pdf.text(String(truncatedUploader), x, y + 4.8);

    // Bottom border line
    pdf.setDrawColor(230, 230, 230);
    pdf.setLineWidth(0.1);
    pdf.line(margin, y + rowHeight, pageW - margin, y + rowHeight);

    y += rowHeight;
  }

  // Footer page numbers
  const totalPages = pdf.getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    pdf.setPage(p);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7);
    pdf.setTextColor(130, 130, 130);
    pdf.text(`Halaman ${p} dari ${totalPages}`, pageW - margin, pageH - 4, { align: "right" });
  }

  pdf.save(`riwayat_upload_${makeTimestamp()}.pdf`);
}
