import { AUTH_USER_STORAGE_KEY } from "~/utils/authSession";
import { authCookieOptions } from "~/stores/authStore";

function readAuthHeader() {
  try {
    const auth = useAuthStore();
    if (auth.token) return `${auth.tokenType ?? "bearer"} ${auth.token}`;
  } catch {
    const options = authCookieOptions();
    const token = useCookie<string | null>("auth_token", options);
    const tokenType = useCookie<string | null>("auth_token_type", options);
    if (token.value) return `${tokenType.value ?? "bearer"} ${token.value}`;
  }
  return null;
}

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig();

  const api = $fetch.create({
    baseURL: config.public.apiBaseUrlPython,
    onRequest({ options }) {
      const headers = new Headers(options.headers as HeadersInit);
      const authorization = readAuthHeader();

      if (authorization) {
        headers.set("Authorization", authorization);
      }

      if (!headers.has("accept")) {
        headers.set("accept", "application/json");
      }

      options.headers = headers;
    },
    async onResponseError({ response }) {
      if (response?.status !== 401) return;

      try {
        useAuthStore().clearAuthData();
      } catch {
        const options = authCookieOptions();
        const token = useCookie<string | null>("auth_token", options);
        const tokenType = useCookie<string | null>("auth_token_type", options);
        const user = useCookie("auth_user", options);
        token.value = null;
        tokenType.value = null;
        user.value = null;
        if (import.meta.client) localStorage.removeItem(AUTH_USER_STORAGE_KEY);
      }

      if (import.meta.client && window.location.pathname !== "/login") {
        window.location.replace("/login");
      }
    },
  });

  return {
    provide: {
      api,
    },
  };
});
