import { watch } from "vue";
import { accessTokenExpiryMs, isAccessTokenExpired } from "~/utils/authSession";

export default defineNuxtPlugin((nuxtApp) => {
  const auth = useAuthStore();
  let timer = 0;

  function leaveIfSessionEnded() {
    if (window.location.pathname === "/login") return;
    if (auth.token && !isAccessTokenExpired(auth.token)) return;
    auth.clearAuthData();
    window.location.replace("/login");
  }

  function armExpiryTimer() {
    window.clearTimeout(timer);
    const expiresAt = accessTokenExpiryMs(auth.token);
    if (!auth.token || !expiresAt || expiresAt <= Date.now()) {
      leaveIfSessionEnded();
      return;
    }
    timer = window.setTimeout(leaveIfSessionEnded, expiresAt - Date.now());
  }

  nuxtApp.hook("app:mounted", async () => {
    auth.hydrateUser();
    watch(() => auth.token, armExpiryTimer);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") leaveIfSessionEnded();
    });

    if (window.location.pathname === "/login") {
      armExpiryTimer();
      return;
    }

    if (!auth.token || isAccessTokenExpired(auth.token)) {
      leaveIfSessionEnded();
      return;
    }

    if (!auth.user?.id) {
      const me = await auth.ensureSession();
      if (!me && window.location.pathname !== "/login") {
        window.location.replace("/login");
        return;
      }
    }

    armExpiryTimer();
  });
});
