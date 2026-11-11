import { describe, expect, it } from "vitest";

import { PROTECTED_PAGE_PATHS } from "../utils/menuRouteAccess";
import { buildMonitoringQuery } from "../utils/monitoringQuery";

describe("buildMonitoringQuery", () => {
  it("hanya memuat parameter yang terisi", () => {
    expect(buildMonitoringQuery({})).toBe("");
    expect(buildMonitoringQuery({ search: "budi", status: "online", page: 2, limit: 20 })).toBe(
      "search=budi&status=online&page=2&limit=20",
    );
    expect(buildMonitoringQuery({ search: "", status: "" })).toBe("");
  });
});

describe("halaman monitoring user", () => {
  it("terdaftar sebagai halaman terproteksi (hak menu)", () => {
    expect(PROTECTED_PAGE_PATHS).toContain("/monitoring-user");
  });
});
