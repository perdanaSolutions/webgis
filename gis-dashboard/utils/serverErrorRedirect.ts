import type { NuxtApp } from "#app";
import {
  maintenanceTarget,
  MAINTENANCE_STATE_KEY,
  parseMaintenanceBody,
  type MaintenanceStatus,
} from "./maintenance";
import {
  classifyFetchError,
  createRedirectDebouncer,
  serverErrorRedirectTarget,
} from "./serverError";

// Satu debouncer per tab (client). Di server dipakai flag per-request di ssrContext.
const clientDebouncer = createRedirectDebouncer();

/** Target /maintenance yang sedang dituju (agar pemanggil lain tidak menimpa ke /login). */
export function pendingServerErrorRedirect(): string | null {
  return import.meta.client ? clientDebouncer.pending() : null;
}

/**
 * Handler pusat: maintenance -> /maintenance?from=..; masalah server -> /maintenance?reason=server-error&from=..
 * Mengembalikan true jika error tergolong masalah server (redirect dipicu / sudah berjalan).
 */
export function redirectOnServerProblem(error: unknown, nuxtApp?: NuxtApp): boolean {
  const kind = classifyFetchError(error);
  if (kind !== "server" && kind !== "maintenance") return false;
  const app = nuxtApp ?? useNuxtApp();
  const route = app.$router?.currentRoute?.value;
  const path = import.meta.client ? window.location.pathname : route?.path ?? "/";
  const fullPath = import.meta.client
    ? `${window.location.pathname}${window.location.search}${window.location.hash}`
    : route?.fullPath ?? path;
  let target: string | null;
  if (kind === "maintenance") {
    // Body { maintenance: true } / errors[].type === "maintenance" (HTTP 200 atau 503).
    const err = error as { response?: { _data?: unknown }; data?: unknown };
    const parsed = parseMaintenanceBody(err?.response?._data ?? err?.data);
    if (parsed) app.runWithContext(() => {
      useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null).value = parsed;
    });
    target = serverErrorRedirectTarget(path, fullPath) ? maintenanceTarget(fullPath) : null;
  } else {
    target = serverErrorRedirectTarget(path, fullPath);
  }
  if (!target) return true; // sudah di /maintenance: jangan loop

  if (import.meta.server) {
    const ctx = app.ssrContext as (Record<string, unknown> & { serverErrorRedirected?: boolean }) | undefined;
    if (ctx?.serverErrorRedirected) return true;
    if (ctx) ctx.serverErrorRedirected = true;
    void app.runWithContext(() => navigateTo(target, { replace: true, redirectCode: 302 }));
    return true;
  }

  if (!clientDebouncer.tryAcquire(target)) return true;
  void Promise.resolve(app.runWithContext(() => navigateTo(target, { replace: true }))).catch(() => {
    window.location.replace(target);
  });
  return true;
}
