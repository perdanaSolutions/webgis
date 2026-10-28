import { describe, expect, it } from "vitest";
import { isOnMaintenancePage, maintenanceRedirect, shouldFetchMaintenanceOnRoute } from "../utils/maintenance";
import { serverErrorRedirectTarget } from "../utils/serverError";

describe("guard anti-loop /maintenance", () => {
  it("mengenali /maintenance dengan query, hash, trailing slash, baseURL", () => {
    for (const p of ["/maintenance", "/maintenance/", "/maintenance?reason=server-error", "/maintenance#x", "maintenance"]) {
      expect(isOnMaintenancePage(p)).toBe(true);
    }
    expect(isOnMaintenancePage("/app/maintenance?x=1", "/app/")).toBe(true);
    expect(isOnMaintenancePage("/app/maintenance/", "/app")).toBe(true);
    for (const p of ["/login", "/dashboard", "/maintenance-x", "/maintenancex", "", null, undefined]) {
      expect(isOnMaintenancePage(p)).toBe(false);
    }
  });
  it("tidak ada keputusan redirect ke /maintenance saat sudah di sana", () => {
    expect(maintenanceRedirect("/maintenance", true)).toBeNull();
    expect(maintenanceRedirect("/maintenance/", true, "server-error")).toBeNull();
    expect(serverErrorRedirectTarget("/maintenance")).toBeNull();
    expect(serverErrorRedirectTarget("/maintenance/")).toBeNull();
  });
  it("middleware tidak cek status di /maintenance", () => {
    expect(shouldFetchMaintenanceOnRoute("/maintenance")).toBe(false);
    expect(shouldFetchMaintenanceOnRoute("/maintenance/")).toBe(false);
  });
  it("maintenance selesai -> satu navigasi ke /login", () => {
    expect(maintenanceRedirect("/maintenance", false)).toBe("/login");
  });
});
