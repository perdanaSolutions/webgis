import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

type UserInfo = {
  id: string;
  username: string;
  nama_lengkap: string;
  email: string;
  role: string;
  permissions: string[];
};

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

  function setAuthData(payload: LoginResponse) {
    token.value = payload.access_token;
    tokenType.value = payload.token_type ?? "bearer";
    user.value = payload.user;
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
      // 1. Transformasi data ke format x-www-form-urlencoded menggunakan URLSearchParams
      const formData = new URLSearchParams();
      formData.append("grant_type", "");
      formData.append("email", email); // Memetakan parameter email ke field username di API
      formData.append("password", password);
      formData.append("scope", "");
      formData.append("client_id", "");
      formData.append("client_secret", "");

      // 2. Sesuaikan path route menjadi /api/v1/auth/login sesuai dengan cURL
      const response = await $fetch<LoginResponse>(`${baseUrl}/v1/auth/login`, {
        method: "POST",
        headers: {
          accept: "application/json",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData, // Kirim objek URLSearchParams
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

      user.value = me;
      return me;
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
    login,
    validateToken,
    logout,
    clearAuthData,
  };
});
