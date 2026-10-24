import { afterEach, describe, expect, it, vi } from "vitest";
import { newUploadGroupId } from "./uploadGroupId";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("newUploadGroupId", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("menghasilkan UUID v4", () => {
    expect(newUploadGroupId()).toMatch(UUID_V4);
  });

  it("tetap UUID saat randomUUID tidak ada (HTTP / non-secure context)", () => {
    vi.stubGlobal("crypto", { getRandomValues: (a: Uint8Array) => { a.fill(7); return a; } });
    const id = newUploadGroupId();
    expect(id).toMatch(UUID_V4);
    expect(id.startsWith("grp-")).toBe(false);
  });

  it("tetap UUID tanpa Web Crypto sama sekali", () => {
    vi.stubGlobal("crypto", undefined);
    expect(newUploadGroupId()).toMatch(UUID_V4);
  });
});
