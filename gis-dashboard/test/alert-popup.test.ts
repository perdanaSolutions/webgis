import { describe, expect, it, vi } from "vitest";
import { createAlertController } from "../utils/alertQueue";
import { mapLoginError, validateLoginInput } from "../utils/loginError";

describe("createAlertController", () => {
  it("menampilkan satu popup per waktu dan mengantre sisanya", async () => {
    const c = createAlertController();
    const p1 = c.error("A");
    const p2 = c.success("B");
    expect(c.current()?.title).toBe("A");
    expect(c.current()?.icon).toBe("error");
    expect(c.pending()).toBe(1);
    c.close(true);
    await expect(p1).resolves.toBe(true);
    expect(c.current()?.title).toBe("B");
    c.close(false);
    await expect(p2).resolves.toBe(false);
    expect(c.current()).toBeNull();
  });

  it("confirm resolve true/false dan memakai teks default Indonesia", async () => {
    const c = createAlertController();
    const yes = c.confirm("Hapus?");
    expect(c.current()).toMatchObject({ showCancel: true, confirmText: "OK", cancelText: "Batal", icon: "question" });
    c.close(true);
    await expect(yes).resolves.toBe(true);
    const no = c.confirm("Hapus?", "teks", { confirmText: "Hapus" });
    expect(c.current()?.confirmText).toBe("Hapus");
    c.close(false);
    await expect(no).resolves.toBe(false);
  });

  it("menutup otomatis dengan timer", async () => {
    vi.useFakeTimers();
    const c = createAlertController();
    const p = c.info("Info", "x", { timer: 1500 });
    const p2 = c.info("Next");
    vi.advanceTimersByTime(1499);
    expect(c.current()?.title).toBe("Info");
    vi.advanceTimersByTime(1);
    await expect(p).resolves.toBe(false);
    expect(c.current()?.title).toBe("Next");
    vi.advanceTimersByTime(5000);
    expect(c.current()?.title).toBe("Next");
    c.close(true);
    await expect(p2).resolves.toBe(true);
    vi.useRealTimers();
  });

  it("clearAll menolak semua popup", async () => {
    const c = createAlertController();
    const ps = [c.info("1"), c.info("2"), c.info("3")];
    c.clearAll();
    await expect(Promise.all(ps)).resolves.toEqual([false, false, false]);
    expect(c.current()).toBeNull();
  });
});

const err = (status: number | undefined, data?: any, headers?: Record<string, string>) => ({
  statusCode: status,
  data,
  response: headers ? { headers: new Headers(headers) } : undefined,
});
const be = (type: string, msg: string) => ({ errors: [{ type, field: "auth", msg, input: null }] });

describe("mapLoginError", () => {
  it("401 kredensial salah memakai pesan backend", () => {
    const r = mapLoginError(err(401, be("invalid_credentials", "Email atau Password yang Anda masukkan salah")));
    expect(r).toMatchObject({ icon: "error", title: "Login gagal", text: "Email atau Password yang Anda masukkan salah" });
  });
  it("403 akun terkunci", () => {
    const r = mapLoginError(err(403, be("account_locked", "Akun Anda terkunci ...")));
    expect(r.title).toBe("Akun terkunci");
    expect(r.text).toBe("Akun Anda terkunci ...");
  });
  it("403 akun tidak aktif", () => {
    const r = mapLoginError(err(403, be("inactive_account", "Akun tidak aktif")));
    expect(r.title).toBe("Akun tidak aktif");
    expect(r.text).toContain("hubungi administrator");
  });
  it("429 dengan Retry-After", () => {
    expect(mapLoginError(err(429, undefined, { "retry-after": "30" })).text).toContain("30 detik");
    expect(mapLoginError(err(429, undefined, { "retry-after": "120" })).text).toContain("2 menit");
    expect(mapLoginError(err(429)).text).toContain("tunggu sebentar");
  });
  it("422 validasi", () => {
    const r = mapLoginError(err(422, { errors: [{ type: "value_error", field: "email", msg: "bukan email" }] }));
    expect(r).toMatchObject({ icon: "warning", title: "Data tidak valid", text: "bukan email" });
  });
  it("5xx dan jaringan", () => {
    expect(mapLoginError(err(500, { errors: [{ msg: "trace internal" }] })).text).toContain("kode 500");
    expect(mapLoginError(err(503)).title).toBe("Layanan tidak tersedia");
    expect(mapLoginError(new TypeError("fetch failed")).title).toBe("Tidak dapat terhubung");
  });
});

describe("validateLoginInput", () => {
  it("mendeteksi field kosong", () => {
    expect(validateLoginInput("", "")?.text).toBe("Email dan Password wajib diisi.");
    expect(validateLoginInput(" a@b.c ", "")?.text).toBe("Password wajib diisi.");
    expect(validateLoginInput("a@b.c", "x")).toBeNull();
  });
});
