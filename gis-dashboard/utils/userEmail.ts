/** Email user wajib @teladanprima.com: user hanya mengisi nama email (bagian sebelum @). */
export const USER_EMAIL_DOMAIN = "teladanprima.com";
export const USER_EMAIL_LOCAL_ERROR = "Isi nama email saja, tanpa domain. Contoh: nama_email";

/** Pecah email di '@' terakhir. Tanpa '@' -> seluruh teks dianggap nama email. */
export function splitEmail(email: string | null | undefined): { local: string; domain: string } {
  const text = String(email ?? "").trim();
  const at = text.lastIndexOf("@");
  if (at < 0) return { local: text, domain: "" };
  return { local: text.slice(0, at), domain: text.slice(at + 1).toLowerCase() };
}

/** Domain lama berbeda dari domain perusahaan (akan diganti saat simpan). */
export function foreignEmailDomain(email: string | null | undefined): string | null {
  const { domain } = splitEmail(email);
  return domain && domain !== USER_EMAIL_DOMAIN ? domain : null;
}

/** Validasi sama dengan form Tambah: wajib, tanpa '@' dan spasi. */
export function buildUserEmail(local: string | null | undefined):
  | { ok: true; email: string }
  | { ok: false; error: string } {
  const value = String(local ?? "").trim();
  if (!value || /[@\s]/.test(value)) return { ok: false, error: USER_EMAIL_LOCAL_ERROR };
  return { ok: true, email: `${value}@${USER_EMAIL_DOMAIN}` };
}
