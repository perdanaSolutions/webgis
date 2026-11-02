import type { NuxtApp } from "#app";
import { AUTH_COOKIE_NAMES, clearBrowserAuthStorage } from "./sessionReset";
import { revokeAuthSession } from "./revokeAuthSession";

/**
 * Hapus seluruh sesi login saat user benar-benar berada di /maintenance.
 * SSR: cookie di-expire lewat Set-Cookie. Client: + storage, cache API peta, state Pinia.
 * Logout backend dipanggil best-effort (gagal diabaikan, tanpa redirect).
 */
export async function clearLoginSession(nuxtApp?: NuxtApp) {
  const app = nuxtApp ?? useNuxtApp();
  await app.runWithContext(async () => {
    const config = useRuntimeConfig();
    const base = String(
      (import.meta.server ? config.apiBaseUrlPythonServer : "") || config.public.apiBaseUrlPython || "",
    ).replace(/\/+$/, "");
    const token = useCookie<string | null>("auth_token", { path: "/" });
    const tokenType = useCookie<string | null>("auth_token_type", { path: "/" });

    if (token.value && base) {
      // Best-effort: saat maintenance backend biasanya 503; abaikan semua error.
      await revokeAuthSession({
        baseUrl: base,
        token: token.value,
        tokenType: tokenType.value,
        timeoutMs: 3000,
      });
    }

    try {
      useAuthStore().clearAuthData();
    } catch {
      /* store belum tersedia */
    }
    for (const name of AUTH_COOKIE_NAMES) {
      const cookie = useCookie<string | null>(name, { path: "/", sameSite: "lax", maxAge: 0 });
      cookie.value = null;
    }

    if (import.meta.client) {
      await clearBrowserAuthStorage({
        localStorage: window.localStorage,
        sessionStorage: window.sessionStorage,
        caches: typeof caches === "undefined" ? null : caches,
      });
    }
  });
}
