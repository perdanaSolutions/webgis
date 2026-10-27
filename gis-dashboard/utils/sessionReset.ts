import { AUTH_USER_STORAGE_KEY } from "./authSession";
import { MAP_PWA_CACHE } from "./mapCacheSchema";

/** Cookie sesi login yang di-set app (stores/authStore.ts, path "/"). */
export const AUTH_COOKIE_NAMES = ["auth_token", "auth_token_type", "auth_user"] as const;
/** localStorage yang terikat user login. Preferensi basemap TIDAK dihapus. */
export const AUTH_LOCAL_STORAGE_KEYS = [AUTH_USER_STORAGE_KEY, "blok-profile-last-search"] as const;
/** sessionStorage yang terikat user login (katalog menu, flag akses ditolak, job upload aktif). */
export const AUTH_SESSION_STORAGE_KEYS = [
  "menu-route-catalog-v1",
  "menu-access-denied",
  "document-upload-job-id",
  "trx-upload-job-id",
] as const;
/** Cache Cache-API berisi respons API peta per user. Cache tile/halaman tidak dihapus. */
export const AUTH_CACHE_NAMES = [MAP_PWA_CACHE] as const;

type StorageLike = Pick<Storage, "removeItem">;

/** Hapus key dari storage; error (mode privat/kuota) diabaikan. Mengembalikan key yang dihapus. */
export function clearStorageKeys(storage: StorageLike | null | undefined, keys: readonly string[]): string[] {
  if (!storage) return [];
  const done: string[] = [];
  for (const key of keys) {
    try {
      storage.removeItem(key);
      done.push(key);
    } catch {
      /* abaikan */
    }
  }
  return done;
}

/** Bagian sesi yang bisa dihapus tanpa Nuxt (client): storage + Cache API. */
export async function clearBrowserAuthStorage(env: {
  localStorage?: StorageLike | null;
  sessionStorage?: StorageLike | null;
  caches?: Pick<CacheStorage, "delete"> | null;
}) {
  const local = clearStorageKeys(env.localStorage, AUTH_LOCAL_STORAGE_KEYS);
  const session = clearStorageKeys(env.sessionStorage, AUTH_SESSION_STORAGE_KEYS);
  const cachesCleared: string[] = [];
  if (env.caches) {
    for (const name of AUTH_CACHE_NAMES) {
      try {
        await env.caches.delete(name);
        cachesCleared.push(name);
      } catch {
        /* abaikan */
      }
    }
  }
  return { local, session, caches: cachesCleared };
}
