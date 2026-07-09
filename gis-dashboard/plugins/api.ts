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

      const token = useCookie<string | null>("auth_token");
      const tokenType = useCookie<string | null>("auth_token_type");
      const user = useCookie("auth_user");

      token.value = null;
      tokenType.value = null;
      user.value = null;

      if (process.client && window.location.pathname !== "/login") {
        await navigateTo("/login");
      }
    },
  });

  return {
    provide: {
      api,
    },
  };
});
