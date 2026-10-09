import { AUTH_USER_STORAGE_KEY } from "~/utils/authSession";

export default defineNuxtPlugin(() => {
  const config = useRuntimeConfig();

  const api = $fetch.create({
    baseURL: config.public.apiBaseUrlPython,
    onRequest({ options }) {
      const token = useCookie<string | null>("auth_token");
      const tokenType = useCookie<string | null>("auth_token_type");

      const headers = new Headers(options.headers as HeadersInit);

      if (token.value) {
        headers.set(
          "Authorization",
          `${tokenType.value ?? "bearer"} ${token.value}`,
        );
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
        const token = useCookie<string | null>("auth_token");
        const tokenType = useCookie<string | null>("auth_token_type");
        const user = useCookie("auth_user");
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
