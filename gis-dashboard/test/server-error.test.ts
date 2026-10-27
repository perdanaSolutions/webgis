import { describe, expect, it } from "vitest";
import {
  classifyFetchError,
  createRedirectDebouncer,
  isServerErrorReason,
  isServerErrorStatus,
  isServerProblemError,
  sanitizeReturnPath,
  serverErrorRedirectTarget,
  SERVER_RECOVERY_POLL_MS,
} from "../utils/serverError";
import { maintenanceRedirect } from "../utils/maintenance";

describe("klasifikasi status", () => {
  it("500/502/503/504 = masalah server", () => {
    for (const s of [500, 502, 503, 504]) expect(isServerErrorStatus(s)).toBe(true);
    for (const s of [200, 400, 401, 403, 404, 422, 429, 501]) expect(isServerErrorStatus(s)).toBe(false);
    expect(isServerErrorStatus(undefined)).toBe(false);
  });

  it("classifyFetchError", () => {
    expect(classifyFetchError({ response: { status: 500 } })).toBe("server");
    expect(classifyFetchError({ statusCode: 502 })).toBe("server");
    expect(classifyFetchError({ response: { status: 503, _data: { maintenance: true } } })).toBe("maintenance");
    expect(classifyFetchError({ response: { status: 503, _data: { detail: "x" } } })).toBe("server");
    expect(classifyFetchError({ response: { status: 401 } })).toBe("client");
    expect(classifyFetchError({ response: { status: 422 } })).toBe("client");
    expect(classifyFetchError({ response: { status: 400 } })).toBe("client");
    expect(classifyFetchError(new TypeError("fetch failed"))).toBe("server");
    expect(classifyFetchError({ name: "TimeoutError" })).toBe("server");
    expect(classifyFetchError({ name: "AbortError" })).toBe("abort");
    expect(classifyFetchError({ cause: { name: "AbortError" } })).toBe("abort");
    expect(isServerProblemError({ response: { status: 504 } })).toBe(true);
    expect(isServerProblemError({ response: { status: 404 } })).toBe(false);
  });
});

describe("sanitizeReturnPath", () => {
  it("menerima path internal", () => {
    expect(sanitizeReturnPath("/dashboard")).toBe("/dashboard");
    expect(sanitizeReturnPath("/peta?x=1#a")).toBe("/peta?x=1#a");
    expect(sanitizeReturnPath(["/users", "/x"])).toBe("/users");
  });
  it("menolak open redirect dan nilai aneh", () => {
    for (const bad of ["https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)", "evil", "", null, undefined, 5, "/\n/evil"]) {
      expect(sanitizeReturnPath(bad)).toBe("/");
    }
    expect(sanitizeReturnPath("/maintenance?reason=server-error")).toBe("/");
  });
});

describe("serverErrorRedirectTarget", () => {
  it("membawa reason tanpa from", () => {
    const t = serverErrorRedirectTarget("/peta", "/peta?a=1")!;
    const u = new URL(t, "http://x");
    expect(u.pathname).toBe("/maintenance");
    expect(u.searchParams.get("reason")).toBe("server-error");
    expect(u.searchParams.get("from")).toBeNull();
  });
  it("tidak redirect saat sudah di /maintenance (anti loop)", () => {
    expect(serverErrorRedirectTarget("/maintenance")).toBeNull();
    expect(serverErrorRedirectTarget("/maintenance/")).toBeNull();
  });
  it("reason", () => {
    expect(isServerErrorReason("server-error")).toBe(true);
    expect(isServerErrorReason(["server-error"])).toBe(true);
    expect(isServerErrorReason(undefined)).toBe(false);
  });
  it("middleware maintenance tidak memantulkan halaman server-error ke /", () => {
    expect(maintenanceRedirect("/maintenance", false, "server-error")).toBeNull();
    expect(maintenanceRedirect("/maintenance", false)).toBe("/login");
    expect(maintenanceRedirect("/dashboard", true, "server-error")).toBe("/maintenance");
  });
});

describe("debounce", () => {
  it("banyak 500 bersamaan = satu navigasi", () => {
    let now = 1000;
    const d = createRedirectDebouncer(5000, () => now);
    expect(d.tryAcquire("/maintenance?a")).toBe(true);
    expect(d.tryAcquire("/maintenance?b")).toBe(false);
    expect(d.pending()).toBe("/maintenance?a");
    now += 4999;
    expect(d.tryAcquire("/maintenance?c")).toBe(false);
    now += 1;
    expect(d.pending()).toBeNull();
    expect(d.tryAcquire("/maintenance?d")).toBe(true);
    d.reset();
    expect(d.pending()).toBeNull();
  });
  it("interval pemulihan halaman /maintenance 60 detik", () => {
    expect(SERVER_RECOVERY_POLL_MS).toBe(60 * 1000);
  });
});
