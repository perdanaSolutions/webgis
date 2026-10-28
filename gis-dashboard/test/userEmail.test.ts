import { describe, expect, it } from "vitest";
import {
  buildUserEmail,
  foreignEmailDomain,
  splitEmail,
  USER_EMAIL_DOMAIN,
  USER_EMAIL_LOCAL_ERROR,
} from "../utils/userEmail";

describe("email user @teladanprima.com", () => {
  it("split di @ terakhir", () => {
    expect(splitEmail("bayuhardiansyah@teladanprima.com")).toEqual({ local: "bayuhardiansyah", domain: "teladanprima.com" });
    expect(splitEmail(" a@b@Plantation.COM ")).toEqual({ local: "a@b", domain: "plantation.com" });
    expect(splitEmail("tanpa_domain")).toEqual({ local: "tanpa_domain", domain: "" });
    expect(splitEmail(null)).toEqual({ local: "", domain: "" });
  });
  it("deteksi domain lama", () => {
    expect(foreignEmailDomain("x@teladanprima.com")).toBeNull();
    expect(foreignEmailDomain("x@TeladanPrima.com")).toBeNull();
    expect(foreignEmailDomain("superadmin@plantation.com")).toBe("plantation.com");
    expect(foreignEmailDomain("x")).toBeNull();
  });
  it("join + validasi sama dengan Tambah", () => {
    expect(USER_EMAIL_DOMAIN).toBe("teladanprima.com");
    expect(buildUserEmail(" bayu.h ")).toEqual({ ok: true, email: "bayu.h@teladanprima.com" });
    for (const bad of ["", "  ", "a@b", "a b", null, undefined]) {
      expect(buildUserEmail(bad)).toEqual({ ok: false, error: USER_EMAIL_LOCAL_ERROR });
    }
  });
});
