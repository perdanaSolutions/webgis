import { describe, expect, it } from "vitest";
import { blobErrorMessage, countQuarantined, failedRowsUrl, filenameFromDisposition } from "./failedRowsDownload";

describe("failedRowsDownload", () => {
  it("membangun URL endpoint", () => {
    expect(failedRowsUrl("https://api/x", "a b")).toBe("https://api/x/v1/upload-jobs/a%20b/data-gagal.xlsx");
  });

  it("membaca nama file dari Content-Disposition", () => {
    expect(filenameFromDisposition('attachment; filename="data_gagal_blok_x_20261027-0710.xlsx"', "f.xlsx"))
      .toBe("data_gagal_blok_x_20261027-0710.xlsx");
    expect(filenameFromDisposition("attachment; filename*=UTF-8''data%20gagal.xlsx", "f.xlsx")).toBe("data gagal.xlsx");
    expect(filenameFromDisposition(null, "f.xlsx")).toBe("f.xlsx");
  });

  it("menjumlahkan karantina_count dari respons execute bersarang", () => {
    expect(countQuarantined({ data: { karantina_count: 3 }, detail: [{ karantina_count: 2 }] })).toBe(5);
    expect(countQuarantined(null)).toBe(0);
  });

  it("membaca pesan error dari blob JSON", async () => {
    const data = new Blob([JSON.stringify({ message: "Tidak ada data gagal pada proses upload ini." })]);
    expect(await blobErrorMessage({ data, statusCode: 404 }, "x")).toBe("Tidak ada data gagal pada proses upload ini.");
    expect(await blobErrorMessage({ statusCode: 403 }, "x")).toContain("tidak memiliki akses");
    expect(await blobErrorMessage({}, "fallback")).toBe("fallback");
  });
});
