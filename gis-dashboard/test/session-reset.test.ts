import { describe, expect, it } from "vitest";
import {
  AUTH_CACHE_NAMES,
  AUTH_COOKIE_NAMES,
  AUTH_LOCAL_STORAGE_KEYS,
  AUTH_SESSION_STORAGE_KEYS,
  clearBrowserAuthStorage,
  clearStorageKeys,
} from "../utils/sessionReset";

function mem(initial: Record<string, string>) {
  const data = { ...initial };
  return {
    data,
    removeItem: (k: string) => { delete data[k]; },
  };
}

describe("hapus sesi login saat maintenance", () => {
  it("daftar yang dihapus", () => {
    expect([...AUTH_COOKIE_NAMES]).toEqual(["auth_token", "auth_token_type", "auth_user"]);
    expect([...AUTH_LOCAL_STORAGE_KEYS]).toEqual(["auth_user", "blok-profile-last-search"]);
    expect([...AUTH_SESSION_STORAGE_KEYS]).toEqual([
      "menu-route-catalog-v1", "menu-access-denied", "document-upload-job-id", "trx-upload-job-id",
    ]);
    expect(AUTH_CACHE_NAMES.length).toBe(1);
  });

  it("hapus semua key auth, preferensi non-auth tetap", async () => {
    const local = mem({ "auth_user": "{}", "blok-profile-last-search": "x", "basemap": "osm" });
    const session = mem({
      "menu-route-catalog-v1": "[]", "menu-access-denied": "1",
      "document-upload-job-id": "a", "trx-upload-job-id": "b", "lain": "1",
    });
    const deleted: string[] = [];
    const res = await clearBrowserAuthStorage({
      localStorage: local,
      sessionStorage: session,
      caches: { delete: async (n: string) => { deleted.push(n); return true; } },
    });
    expect(local.data).toEqual({ basemap: "osm" });
    expect(session.data).toEqual({ lain: "1" });
    expect(deleted).toEqual([...AUTH_CACHE_NAMES]);
    expect(res.local.length + res.session.length).toBe(6);
  });

  it("storage error / tidak ada tidak melempar", async () => {
    expect(clearStorageKeys(null, ["a"])).toEqual([]);
    const bad = { removeItem: () => { throw new Error("private"); } };
    expect(clearStorageKeys(bad, ["a"])).toEqual([]);
    await expect(clearBrowserAuthStorage({ localStorage: bad, caches: { delete: async () => { throw new Error("x"); } } }))
      .resolves.toBeTruthy();
  });
});
