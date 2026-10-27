import { describe, expect, it } from "vitest";
import {
  isLoginPath,
  isMaintenancePath,
  isMaintenanceResponse,
  maintenanceRedirect,
  shouldFetchMaintenanceOnRoute,
  MAINTENANCE_PATH,
  MAINTENANCE_POLL_MS,
} from "../utils/maintenance";

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

  it("mengenali path dan respons 503 maintenance dari API lain", () => {
    expect(isMaintenancePath("/maintenance/")).toBe(true);
    expect(isLoginPath("/login/")).toBe(true);
    expect(isMaintenanceResponse(503, { maintenance: true })).toBe(true);
    expect(isMaintenanceResponse(503, { detail: "x" })).toBe(false);
    expect(isMaintenanceResponse(500, { maintenance: true })).toBe(false);
    expect(isMaintenanceResponse(200, { maintenance: true })).toBe(false);
  });

  it("hanya fetch pada login enter atau ganti menu saat login", () => {
    expect(shouldFetchMaintenanceOnRoute("/login", false)).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/login", true)).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/users", true)).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/dashboard", true)).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/users", false)).toBe(false);
    expect(shouldFetchMaintenanceOnRoute("/maintenance", true)).toBe(false);
    expect(shouldFetchMaintenanceOnRoute("/maintenance", false)).toBe(false);
  });

  it("interval poll 30 menit", () => {
    expect(MAINTENANCE_POLL_MS).toBe(30 * 60 * 1000);
  });
});
