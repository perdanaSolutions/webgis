import { describe, expect, it } from "vitest";
import { getErrorMessage } from "../utils/getErrorMessage";

describe("getErrorMessage", () => {
  it("membaca errors[] dari body backend", () => {
    expect(
      getErrorMessage({
        data: {
          errors: [
            { field: "email", msg: "sudah dipakai" },
            { field: "global", msg: "gagal" },
          ],
        },
      }),
    ).toBe("email: sudah dipakai, gagal");
  });

  it("tidak throw bila error tanpa data (network / mixed content)", () => {
    expect(getErrorMessage({ message: "Failed to fetch" }, "fallback")).toBe(
      "Failed to fetch",
    );
    expect(getErrorMessage({}, "fallback")).toBe("fallback");
    expect(getErrorMessage(undefined, "fallback")).toBe("fallback");
  });

  it("membaca detail string", () => {
    expect(getErrorMessage({ data: { detail: "tidak diizinkan" } })).toBe(
      "tidak diizinkan",
    );
  });
});
