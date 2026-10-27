import type { AlertIcon } from "./alertQueue";

export interface LoginErrorInfo {
  icon: AlertIcon;
  title: string;
  text: string;
}

function backendMessage(data: any): string {
  if (!data) return "";
  if (Array.isArray(data.errors)) {
    const msgs = data.errors
      .map((e: any) => (typeof e?.msg === "string" ? e.msg.trim() : ""))
      .filter(Boolean);
    return msgs.join(" ");
  }
  if (typeof data.errors === "string") return data.errors;
  if (typeof data.detail === "string") return data.detail;
  if (typeof data.message === "string") return data.message;
  return "";
}

function errorType(data: any): string {
  return Array.isArray(data?.errors) ? String(data.errors[0]?.type ?? "") : "";
}

function retryAfterSeconds(error: any): number | null {
  const headers = error?.response?.headers;
  const raw = typeof headers?.get === "function" ? headers.get("retry-after") : headers?.["retry-after"];
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  if (Number.isFinite(n) && n >= 0) return Math.ceil(n);
  const date = Date.parse(String(raw));
  if (!Number.isNaN(date)) return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  return null;
}

function formatWait(sec: number): string {
  if (sec < 60) return `${sec} detik`;
  const m = Math.ceil(sec / 60);
  return `${m} menit`;
}

/** Validasi sisi client sebelum request login. Null = valid. */
export function validateLoginInput(email: string, password: string): LoginErrorInfo | null {
  const missing = [!email.trim() && "Email", !password && "Password"].filter(Boolean) as string[];
  if (missing.length) {
    return {
      icon: "warning",
      title: "Data belum lengkap",
      text: `${missing.join(" dan ")} wajib diisi.`,
    };
  }
  return null;
}

/** Memetakan error $fetch dari POST /v1/auth/login menjadi isi popup. */
export function mapLoginError(error: any): LoginErrorInfo {
  const status: number | undefined = error?.statusCode ?? error?.status ?? error?.response?.status;
  const data = error?.data;
  const msg = backendMessage(data);
  const type = errorType(data);

  if (!status) {
    return {
      icon: "error",
      title: "Tidak dapat terhubung",
      text: "Tidak dapat terhubung ke server. Periksa koneksi internet Anda lalu coba lagi.",
    };
  }
  if (status === 401) {
    return {
      icon: "error",
      title: "Login gagal",
      text: msg || "Email atau Password yang Anda masukkan salah.",
    };
  }
  if (status === 403 && type === "account_locked") {
    return {
      icon: "error",
      title: "Akun terkunci",
      text: msg || "Akun Anda terkunci. Silakan hubungi PA.",
    };
  }
  if (status === 403 && type === "inactive_account") {
    return {
      icon: "warning",
      title: "Akun tidak aktif",
      text: (msg || "Akun tidak aktif.") + " Silakan hubungi administrator.",
    };
  }
  if (status === 403) {
    return { icon: "error", title: "Akses ditolak", text: msg || "Anda tidak diizinkan masuk." };
  }
  if (status === 422 || status === 400) {
    return {
      icon: "warning",
      title: "Data tidak valid",
      text: msg || "Periksa kembali format email dan password Anda.",
    };
  }
  if (status === 429) {
    const wait = retryAfterSeconds(error);
    return {
      icon: "warning",
      title: "Terlalu banyak percobaan",
      text: wait != null
        ? `Terlalu banyak percobaan login. Silakan coba lagi dalam ${formatWait(wait)}.`
        : "Terlalu banyak percobaan login. Silakan tunggu sebentar lalu coba lagi.",
    };
  }
  if (status === 503) {
    return {
      icon: "info",
      title: "Layanan tidak tersedia",
      text: msg || "Server sedang dalam perbaikan. Silakan coba beberapa saat lagi.",
    };
  }
  if (status >= 500) {
    return {
      icon: "error",
      title: "Terjadi kesalahan server",
      text: `Server mengalami gangguan (kode ${status}). Silakan coba beberapa saat lagi.`,
    };
  }
  return { icon: "error", title: "Login gagal", text: msg || "Login gagal, mohon periksa kembali inputan Anda." };
}
