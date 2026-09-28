import { computed, ref } from "vue";
import { defineStore } from "pinia";
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

export const useAuthStore = defineStore("auth", () => {
  const token = useCookie<string | null>("auth_token", {
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7,
  });

  const tokenType = useCookie<string | null>("auth_token_type", {
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7,
  });

  const user = useCookie<UserInfo | null>("auth_user", {
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7,
  });

  const loading = ref(false);
  const errorMessage = ref("");

  const isAuthenticated = computed(() => Boolean(token.value));
  const isSuperAdmin = computed(() =>
    (user.value?.roles ?? []).some((role) => role.toLowerCase() === "superadmin"),
  );

  function setAuthData(payload: LoginResponse) {
    token.value = payload.access_token;
    tokenType.value = payload.token_type ?? "bearer";
    user.value = normalizeUser(payload.user);
  }

  function clearAuthData() {
    token.value = null;
    tokenType.value = null;
    user.value = null;
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

  async function validateToken() {
    if (!token.value) {
      clearAuthData();
      await navigateTo("/login");
      return null;
    }

    try {
      const baseUrl = getApiBaseUrl();
      const me = await $fetch<UserInfo>(`${baseUrl}/v1/auth/me`, {
        headers: {
          Authorization: `${tokenType.value ?? "bearer"} ${token.value}`,
        },
      });

      user.value = normalizeUser(me);
      return user.value;
    } catch {
      clearAuthData();
      await navigateTo("/login");
      return null;
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
    validateToken,
    logout,
    clearAuthData,
  };
});
