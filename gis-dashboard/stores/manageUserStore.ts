import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

export type UserItem = {
  id: string;
  username: string;
  email: string;
  nama_lengkap: string;
  role: RoleItem;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

export type CreateUserPayload = {
  username: string;
  email: string;
  nama_lengkap: string;
  role_id: string;
  is_active: boolean;
  password: string;
};

export type UpdateUserPayload = {
  username: string;
  email: string;
  nama_lengkap: string;
  role_id: string;
  password: string;
  is_active: boolean;
};

export type UserListResponse = {
  total_data: number;
  page: number;
  limit: number;
  total_page: number;
  data: UserItem[];
};

export type UserListQuery = {
  search?: string;
  page?: number;
  limit?: number;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

function buildQueryParams(query: UserListQuery = {}) {
  const params = new URLSearchParams();

  if (query.search) params.set("search", query.search);
  if (typeof query.page === "number") params.set("page", String(query.page));
  if (typeof query.limit === "number") params.set("limit", String(query.limit));

  return params.toString();
}

export const useManageUserStore = defineStore("manageUser", () => {
  const { $api } = useNuxtApp();

  const users = ref<UserItem[]>([]);
  const selectedUser = ref<UserItem | null>(null);

  const totalData = ref(0);
  const page = ref(1);
  const limit = ref(10);
  const totalPage = ref(0);

  const roles = ref<RoleItem[]>([]);

  const loadingList = ref(false);
  const loadingDetail = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingDelete = ref(false);
  const loadingRoles = ref(false);

  const errorMessage = ref("");

  const hasUsers = computed(() => users.value.length > 0);

  function getAuthHeaders() {
    return {
      accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  function clearError() {
    errorMessage.value = "";
  }

  async function fetchUsers(query: UserListQuery = {}) {
    loadingList.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const queryString = buildQueryParams(query);
      const endpoint = `${baseUrl}/v1/users`;
      const url = queryString ? `${endpoint}?${queryString}` : endpoint;

      const response = await $api<UserListResponse>(url, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      users.value = response.data ?? [];
      totalData.value = response.total_data ?? 0;
      page.value = response.page ?? query.page ?? 1;
      limit.value = response.limit ?? query.limit ?? 10;
      totalPage.value = response.total_page ?? 0;

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil daftar user.",
      );
      throw error;
    } finally {
      loadingList.value = false;
    }
  }

  async function fetchUserById(userId: string) {
    loadingDetail.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<UserItem>(`${baseUrl}/v1/users/${userId}`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      selectedUser.value = response;
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil detail user.",
      );
      throw error;
    } finally {
      loadingDetail.value = false;
    }
  }

  async function createUser(payload: CreateUserPayload) {
    loadingCreate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<UserItem>(`${baseUrl}/v1/users`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal membuat user baru.");
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  async function updateUser(userId: string, payload: UpdateUserPayload) {
    loadingUpdate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<UserItem>(`${baseUrl}/v1/users/${userId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal memperbarui user.");
      throw error;
    } finally {
      loadingUpdate.value = false;
    }
  }

  async function deleteUser(userId: string) {
    loadingDelete.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api(`${baseUrl}/v1/users/${userId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal menghapus user.");
      throw error;
    } finally {
      loadingDelete.value = false;
    }
  }

  async function fetchRoles() {
    loadingRoles.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<RoleItem[]>(`${baseUrl}/v1/roles/`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      roles.value = response ?? [];
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil daftar role.",
      );
      throw error;
    } finally {
      loadingRoles.value = false;
    }
  }

  return {
    users,
    selectedUser,
    totalData,
    page,
    limit,
    totalPage,
    roles,
    loadingList,
    loadingDetail,
    loadingCreate,
    loadingUpdate,
    loadingDelete,
    loadingRoles,
    errorMessage,
    hasUsers,
    fetchUsers,
    fetchUserById,
    createUser,
    updateUser,
    deleteUser,
    fetchRoles,
    clearError,
  };
});
