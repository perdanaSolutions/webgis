import type { MonitoringUserItem } from "~/stores/monitoringUserStore";

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });
}

function accountNote(item: MonitoringUserItem): string {
  if (item.terkunci) return "Akun terkunci";
  if (!item.akun_aktif) return "Akun nonaktif";
  return "-";
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

export async function exportMonitoringExcel(items: MonitoringUserItem[], scopeLabel = "Semua Data"): Promise<void> {
  const XLSX = await import("xlsx");
  const headers = [
    "No",
    "Status",
    "Nama Lengkap",
    "Username",
    "Email",
    "Role",
    "Catatan Akun",
    "Login Terakhir",
    "Logout Terakhir",
    "Aktivitas Terakhir",
    "IP Terakhir",
  ];

  const rows = items.map((item, idx) => [
    idx + 1,
    item.status === "online" ? "Online" : "Offline",
    item.nama_lengkap || "-",
    item.username,
    item.email,
    item.role.length ? item.role.join(", ") : "-",
    accountNote(item),
    formatDateTime(item.login_terakhir),
    formatDateTime(item.logout_terakhir),
    formatDateTime(item.aktivitas_terakhir),
    item.ip_terakhir || "-",
  ]);

  const workbook = XLSX.utils.book_new();
  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows]);

  worksheet["!cols"] = [
    { wch: 6 },
    { wch: 12 },
    { wch: 25 },
    { wch: 18 },
    { wch: 28 },
    { wch: 20 },
    { wch: 16 },
    { wch: 22 },
    { wch: 22 },
    { wch: 22 },
    { wch: 16 },
  ];

  XLSX.utils.book_append_sheet(workbook, worksheet, "Monitoring User");
  XLSX.writeFile(workbook, `monitoring_user_${makeTimestamp()}.xlsx`, { compression: true });
}

export async function exportMonitoringPdf(items: MonitoringUserItem[], scopeLabel = "Semua Data"): Promise<void> {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });

  const pageW = 297;
  const pageH = 210;
  const margin = 10;

  // Header
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(14);
  pdf.setTextColor(31, 42, 24);
  pdf.text("Laporan Monitoring User", margin, margin + 5);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(100, 100, 100);
  const printedAt = `Dicetak: ${new Date().toLocaleString("id-ID")} (${scopeLabel})`;
  pdf.text(printedAt, pageW - margin, margin + 5, { align: "right" });

  // Columns & widths
  const cols = [
    { name: "No", w: 10 },
    { name: "Status", w: 16 },
    { name: "User", w: 55 },
    { name: "Role", w: 32 },
    { name: "Login Terakhir", w: 42 },
    { name: "Logout Terakhir", w: 42 },
    { name: "Aktivitas Terakhir", w: 45 },
    { name: "IP", w: 35 },
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

    // Status
    if (item.status === "online") {
      pdf.setTextColor(22, 128, 61);
      pdf.text("Online", x, y + 4.8);
    } else {
      pdf.setTextColor(100, 116, 139);
      pdf.text("Offline", x, y + 4.8);
    }
    pdf.setTextColor(40, 40, 40);
    x += cols[1]!.w;

    // User (Nama / Username)
    const userText = item.nama_lengkap ? `${item.nama_lengkap} (@${item.username})` : `@${item.username}`;
    const truncatedUser = pdf.splitTextToSize(userText, cols[2]!.w - 3)[0] ?? userText;
    pdf.text(String(truncatedUser), x, y + 4.8);
    x += cols[2]!.w;

    // Role
    const roleText = item.role.length ? item.role.join(", ") : "-";
    const truncatedRole = pdf.splitTextToSize(roleText, cols[3]!.w - 3)[0] ?? roleText;
    pdf.text(String(truncatedRole), x, y + 4.8);
    x += cols[3]!.w;

    // Login Terakhir
    pdf.text(formatDateTime(item.login_terakhir), x, y + 4.8);
    x += cols[4]!.w;

    // Logout Terakhir
    pdf.text(formatDateTime(item.logout_terakhir), x, y + 4.8);
    x += cols[5]!.w;

    // Aktivitas Terakhir
    pdf.text(formatDateTime(item.aktivitas_terakhir), x, y + 4.8);
    x += cols[6]!.w;

    // IP
    pdf.text(item.ip_terakhir || "-", x, y + 4.8);

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

  pdf.save(`monitoring_user_${makeTimestamp()}.pdf`);
}
