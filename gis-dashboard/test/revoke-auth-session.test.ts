import { describe, expect, it, vi } from "vitest";
import { revokeAuthSession, revokeAuthSessionUrl } from "../utils/revokeAuthSession";

describe("revokeAuthSession (JWT + Redis jti, tanpa sticky)", () => {
  it("susun URL logout dari base API", () => {
    expect(revokeAuthSessionUrl("https://api.example/api")).toBe(
      "https://api.example/api/v1/auth/logout",
    );
    expect(revokeAuthSessionUrl("https://api.example/api/")).toBe(
      "https://api.example/api/v1/auth/logout",
    );
  });

  it("POST Authorization bearer dan mengembalikan true", async () => {
    const fetchImpl = vi.fn(async () => ({ message: "ok" }));
    const ok = await revokeAuthSession(
      { baseUrl: "https://api.example/api", token: "jwt-token", tokenType: "Bearer" },
      fetchImpl,
    );
    expect(ok).toBe(true);
    expect(fetchImpl).toHaveBeenCalledWith("https://api.example/api/v1/auth/logout", {
      method: "POST",
      timeout: 5000,
      headers: {
        Authorization: "Bearer jwt-token",
        accept: "application/json",
      },
    });
  });

  it("tanpa token atau base → false, tidak fetch", async () => {
    const fetchImpl = vi.fn();
    expect(await revokeAuthSession({ baseUrl: "", token: "x" }, fetchImpl)).toBe(false);
    expect(await revokeAuthSession({ baseUrl: "https://a", token: "" }, fetchImpl)).toBe(false);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("error jaringan → false (pemanggil tetap bersihkan lokal)", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network");
    });
    expect(
      await revokeAuthSession({ baseUrl: "https://api.example/api", token: "t" }, fetchImpl),
    ).toBe(false);
  });
});
