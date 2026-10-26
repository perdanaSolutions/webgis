import { describe, expect, it } from "vitest";
import { isMaintenancePath, isMaintenanceResponse, maintenanceRedirect, MAINTENANCE_PATH } from "../utils/maintenance";

describe("maintenanceRedirect", () => {
  it("mengalihkan semua halaman ke /maintenance saat aktif", () => {
    expect(maintenanceRedirect("/dashboard", true)).toBe(MAINTENANCE_PATH);
    expect(maintenanceRedirect("/login", true)).toBe(MAINTENANCE_PATH);
    expect(maintenanceRedirect("/maintenance", true)).toBeNull();
  });

  it("kembali ke beranda saat maintenance dimatikan", () => {
    expect(maintenanceRedirect("/maintenance", false)).toBe("/");
    expect(maintenanceRedirect("/maintenance/", false)).toBe("/");
    expect(maintenanceRedirect("/dashboard", false)).toBeNull();
  });

  it("mengenali path dan respons 503 maintenance", () => {
    expect(isMaintenancePath("/maintenance/")).toBe(true);
    expect(isMaintenanceResponse(503, { maintenance: true })).toBe(true);
    expect(isMaintenanceResponse(503, { detail: "x" })).toBe(false);
    expect(isMaintenanceResponse(500, { maintenance: true })).toBe(false);
  });
});
