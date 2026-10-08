import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { AUTH_USER_STORAGE_KEY, SESSION_MAX_AGE_SECONDS, isAccessTokenExpired } from "~/utils/authSession";
import { getErrorMessage } from "~/utils/getErrorMessage";

type AksesData = {
  kode_area?: string | null;
  kode_pt?: string | null;
  kode_est?: string | null;
  kode_afd?: string | null;
};

type UserInfo = {
  id: string;
  username: string;
  nama_lengkap: string;
  email: string;
  roles: string[];
  role?: string | null;
  is_active?: boolean;
  akses_menu: string[];
  akses_data: AksesData[];
  akses_transaksi: string[];
};

function uniqueText(values: unknown) {
  const list = Array.isArray(values) ? values : [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of list) {
    const text = String(value ?? "").trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    result.push(text);
  }
  return result;
}

function normalizeUser(raw: Partial<UserInfo> | null | undefined): UserInfo {
  const roleNames = uniqueText(
    (Array.isArray(raw?.roles) ? raw.roles : []).map((role) =>
      typeof role === "string" ? role : (role as { nama?: string })?.nama,
    ),
  );
  if (!roleNames.length && raw?.role) roleNames.push(String(raw.role));

  const aksesDataSeen = new Set<string>();
  const aksesData: AksesData[] = [];
  for (const row of Array.isArray(raw?.akses_data) ? raw.akses_data : []) {
    const item: AksesData = {
      kode_area: row?.kode_area ?? null,
      kode_pt: row?.kode_pt ?? null,
      kode_est: row?.kode_est ?? null,
      kode_afd: row?.kode_afd ?? null,
    };
    const key = [item.kode_area, item.kode_pt, item.kode_est, item.kode_afd]
      .map((value) => String(value ?? "").trim().toUpperCase())
      .join("|");
    if (aksesDataSeen.has(key)) continue;
    aksesDataSeen.add(key);
    aksesData.push(item);
  }

  return {
    id: String(raw?.id ?? ""),
    username: String(raw?.username ?? ""),
    nama_lengkap: String(raw?.nama_lengkap ?? ""),
    email: String(raw?.email ?? ""),
    roles: roleNames,
    role: roleNames[0] ?? raw?.role ?? null,
    is_active: raw?.is_active !== false,
    akses_menu: uniqueText(raw?.akses_menu),
    akses_data: aksesData,
    akses_transaksi: uniqueText(
      (Array.isArray(raw?.akses_transaksi) ? raw.akses_transaksi : []).map((item: any) =>
        typeof item === "string" ? item : item?.nama_table_transaksi ?? item?.table_name ?? "",
      ),
    ),
  };
}

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: UserInfo;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

const cookieOptions = {
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  maxAge: SESSION_MAX_AGE_SECONDS,
};

function readStoredUser(): UserInfo | null {
  if (!import.meta.client) return null;
  try {
    const raw = localStorage.getItem(AUTH_USER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<UserInfo>;
    const user = normalizeUser(parsed);
    return user.id ? user : null;
  } catch {
    return null;
  }
}

export const useAuthStore = defineStore("auth", () => {
  const token = useCookie<string | null>("auth_token", cookieOptions);
  const tokenType = useCookie<string | null>("auth_token_type", cookieOptions);
  const profileCookie = useCookie<UserInfo | null>("auth_user", cookieOptions);
  const user = ref<UserInfo | null>(
    profileCookie.value?.id ? normalizeUser(profileCookie.value) : null,
  );

  const loading = ref(false);
  const errorMessage = ref("");

  const isAuthenticated = computed(
    () => Boolean(token.value) && !isAccessTokenExpired(token.value),
  );
  const isSuperAdmin = computed(() =>
    (user.value?.roles ?? []).some((role) => role.toLowerCase() === "superadmin"),
  );

  function compactUser(value: UserInfo): UserInfo {
    return {
      id: value.id,
      username: value.username,
      nama_lengkap: value.nama_lengkap,
      email: value.email,
      roles: value.roles,
      role: value.role ?? null,
      is_active: value.is_active !== false,
      akses_menu: [],
      akses_data: [],
      akses_transaksi: [],
    };
  }

  function persistUser(value: UserInfo | null) {
    user.value = value;
    profileCookie.value = value?.id ? compactUser(value) : null;
    if (!import.meta.client) return;
    if (!value?.id) {
      localStorage.removeItem(AUTH_USER_STORAGE_KEY);
      return;
    }
    localStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(value));
  }

  function hydrateUser() {
    const stored = readStoredUser();
    if (stored?.id) {
      user.value = stored;
      profileCookie.value = compactUser(stored);
      return stored;
    }
    if (profileCookie.value?.id) {
      const fromCookie = normalizeUser(profileCookie.value);
      user.value = fromCookie;
      const hasAccess = fromCookie.akses_menu.length || fromCookie.akses_data.length || fromCookie.akses_transaksi.length;
      if (hasAccess) persistUser(fromCookie);
      return user.value;
    }
    return user.value?.id ? user.value : null;
  }

  let sessionRequest: Promise<UserInfo | null> | null = null;

  async function ensureSession() {
    if (!token.value || isAccessTokenExpired(token.value)) {
      clearAuthData();
      return null;
    }
    if (readStoredUser()?.id) {
      return hydrateUser();
    }
    if (!sessionRequest) {
      sessionRequest = validateToken({ redirect: false }).finally(() => {
        sessionRequest = null;
      });
    }
    return sessionRequest;
  }

  async function redirectToLogin() {
    if (import.meta.client) {
      if (window.location.pathname !== "/login") window.location.replace("/login");
      return;
    }
    const nuxtApp = useNuxtApp();
    await nuxtApp.runWithContext(() => navigateTo("/login", { replace: true }));
  }

  function setAuthData(payload: LoginResponse) {
    token.value = payload.access_token;
    tokenType.value = payload.token_type ?? "bearer";
    persistUser(normalizeUser(payload.user));
  }

  function clearAuthData() {
    token.value = null;
    tokenType.value = null;
    persistUser(null);
  }

  async function login(email: string, password: string) {
    loading.value = true;
    errorMessage.value = "";
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $fetch<LoginResponse>(`${baseUrl}/v1/auth/login`, {
        method: "POST",
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
        // $fetch otomatis melakukan JSON.stringify jika mendeteksi Content-Type json / mendeteksi object
        body: {
          email: email,
          password: password,
        },
      });

      setAuthData(response);
      await navigateTo("/dashboard");
      return response;
    } catch (error: any) {
      clearAuthData();
      errorMessage.value = getErrorMessage(
        error,
        "Login gagal, Mohon periksa kembali inputan Anda.",
      );
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function validateToken(options?: { redirect?: boolean }) {
    const redirect = options?.redirect !== false;
    if (!token.value || isAccessTokenExpired(token.value)) {
      clearAuthData();
      if (redirect) await redirectToLogin();
      return null;
    }

    try {
      const baseUrl = getApiBaseUrl();
      const me = await $fetch<UserInfo>(`${baseUrl}/v1/auth/me`, {
        timeout: 8000,
        headers: {
          Authorization: `${tokenType.value ?? "bearer"} ${token.value}`,
        },
      });

      persistUser(normalizeUser(me));
      return user.value;
    } catch {
      clearAuthData();
      if (redirect) await redirectToLogin();
      return null;
    }
  }

  async function changePassword(passwordLama: string, passwordBaru: string) {
    loading.value = true;
    errorMessage.value = "";
    try {
      const baseUrl = getApiBaseUrl();
      const response = await $fetch<{ message: string }>(
        `${baseUrl}/v1/auth/me/password`,
        {
          method: "PUT",
          headers: {
            accept: "application/json",
            "Content-Type": "application/json",
            Authorization: `${tokenType.value ?? "bearer"} ${token.value}`,
          },
          body: {
            password_lama: passwordLama,
            password_baru: passwordBaru,
          },
        },
      );
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal memperbarui password.",
      );
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    clearAuthData();
    await navigateTo("/login");
  }

  return {
    token,
    tokenType,
    user,
    loading,
    errorMessage,
    isAuthenticated,
    isSuperAdmin,
    login,
    changePassword,
    validateToken,
    logout,
    clearAuthData,
    hydrateUser,
    ensureSession,
  };
});
