import { describe, expect, it } from "vitest";
import {
  isLoginPath,
  isMaintenancePath,
  isMaintenanceResponse,
  maintenanceRedirect,
  maintenanceTarget,
  parseMaintenanceBody,
  shouldFetchMaintenanceOnRoute,
  MAINTENANCE_DEFAULT_MESSAGE,
  MAINTENANCE_PATH,
  MAINTENANCE_POLL_MS,
  MAINTENANCE_STATUS_ENDPOINT,
} from "../utils/maintenance";
import { classifyFetchError, redirectsToMaintenance } from "../utils/serverError";

const MSG = "Website sedang dalam perbaikan. Mohon coba beberapa saat lagi.";
const BODY_503 = {
  maintenance: true,
  message: MSG,
  errors: [{ type: "maintenance", field: "global", msg: MSG, input: null }],
};

describe("parseMaintenanceBody", () => {
  it("body 503 lengkap dari middleware backend", () => {
    expect(parseMaintenanceBody(BODY_503)).toEqual({ maintenance: true, message: MSG });
  });
  it("body 200 dari /v1/system/maintenance", () => {
    expect(parseMaintenanceBody({ maintenance: true, message: MSG })).toEqual({ maintenance: true, message: MSG });
    expect(parseMaintenanceBody({ maintenance: false, message: MSG })).toBeNull();
  });
  it("hanya errors[].type === maintenance", () => {
    expect(parseMaintenanceBody({ errors: [{ type: "x" }, { type: "maintenance", msg: "m" }] })).toEqual({ maintenance: true, message: "m" });
    expect(parseMaintenanceBody({ errors: [{ type: "maintenance" }] })).toEqual({ maintenance: true, message: MAINTENANCE_DEFAULT_MESSAGE });
    expect(parseMaintenanceBody({ errors: [{ type: "validation" }] })).toBeNull();
  });
  it("body bukan objek", () => {
    for (const b of [null, undefined, "x", 1, [], { detail: "x" }]) expect(parseMaintenanceBody(b)).toBeNull();
  });
});

describe("isMaintenanceResponse & klasifikasi error", () => {
  it("200 dan 503 dengan body maintenance", () => {
    expect(isMaintenanceResponse(503, BODY_503)).toBe(true);
    expect(isMaintenanceResponse(200, BODY_503)).toBe(true);
    expect(isMaintenanceResponse(503, { errors: [{ type: "maintenance" }] })).toBe(true);
    expect(isMaintenanceResponse(503, { detail: "x" })).toBe(false);
    expect(isMaintenanceResponse(500, BODY_503)).toBe(false);
    expect(isMaintenanceResponse(200, { maintenance: false })).toBe(false);
  });
  it("error $fetch 503 maintenance dialihkan; 4xx tidak", () => {
    expect(classifyFetchError({ response: { status: 503, _data: BODY_503 } })).toBe("maintenance");
    expect(redirectsToMaintenance({ response: { status: 503, _data: BODY_503 } })).toBe(true);
    expect(redirectsToMaintenance({ response: { status: 401, _data: { detail: "x" } } })).toBe(false);
    expect(redirectsToMaintenance({ response: { status: 422 } })).toBe(false);
  });
});

describe("keputusan middleware / redirect", () => {
  it("maintenance aktif: semua halaman ke /maintenance dengan from", () => {
    expect(maintenanceRedirect("/dashboard", true, undefined, { fullPath: "/dashboard?x=1" }))
      .toBe("/maintenance?from=%2Fdashboard%3Fx%3D1");
    expect(maintenanceRedirect("/login", true)).toBe("/maintenance?from=%2Flogin");
    expect(maintenanceRedirect("/", true)).toBe(MAINTENANCE_PATH);
    expect(maintenanceRedirect("/maintenance", true)).toBeNull();
  });
  it("maintenance mati: kembali ke from (disanitasi)", () => {
    expect(maintenanceRedirect("/maintenance", false)).toBe("/");
    expect(maintenanceRedirect("/maintenance/", false, undefined, { from: "/peta" })).toBe("/peta");
    expect(maintenanceRedirect("/maintenance", false, undefined, { from: "//evil.com" })).toBe("/");
    expect(maintenanceRedirect("/maintenance", false, "server-error", { from: "/peta" })).toBeNull();
    expect(maintenanceRedirect("/dashboard", false)).toBeNull();
  });
  it("middleware cek di setiap navigasi kecuali /maintenance", () => {
    expect(shouldFetchMaintenanceOnRoute("/login")).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/users", false)).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/dashboard", true)).toBe(true);
    expect(shouldFetchMaintenanceOnRoute("/maintenance")).toBe(false);
    expect(shouldFetchMaintenanceOnRoute("/maintenance/")).toBe(false);
  });
  it("target & path", () => {
    expect(maintenanceTarget("/maintenance")).toBe(MAINTENANCE_PATH);
    expect(isMaintenancePath("/maintenance/")).toBe(true);
    expect(isLoginPath("/login/")).toBe(true);
  });
  it("endpoint v1 dan poll 30 detik", () => {
    expect(MAINTENANCE_STATUS_ENDPOINT).toBe("/v1/system/maintenance");
    expect(MAINTENANCE_POLL_MS).toBe(30 * 1000);
  });
});
