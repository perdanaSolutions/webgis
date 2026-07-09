import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

export type PermissionItem = {
  kode: string;
  resource: string;
  aksi: string;
  deskripsi: string;
  id: string;
};

export type CreatePermissionPayload = {
  kode: string;
  resource: string;
  aksi: string;
  deskripsi: string;
};

export type UpdatePermissionPayload = {
  kode: string;
  resource: string;
  aksi: string;
  deskripsi: string;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const useManagePermissionStore = defineStore("managePermission", () => {
  const { $api } = useNuxtApp();

  const permissions = ref<PermissionItem[]>([]);
  const selectedPermission = ref<PermissionItem | null>(null);

  const loadingList = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingDelete = ref(false);
  const errorMessage = ref("");

  const hasPermissions = computed(() => permissions.value.length > 0);

  function getAuthHeaders() {
    return {
      accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  function clearError() {
    errorMessage.value = "";
  }

  async function fetchPermissions() {
    loadingList.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PermissionItem[]>(
        `${baseUrl}/v1/permissions/`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      permissions.value = response ?? [];
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil data permission.",
      );
      throw error;
    } finally {
      loadingList.value = false;
    }
  }

  async function createPermission(payload: CreatePermissionPayload) {
    loadingCreate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PermissionItem>(
        `${baseUrl}/v1/permissions/`,
        {
          method: "POST",
          headers: getAuthHeaders(),
          body: payload,
        },
      );

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal membuat permission.");
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  async function updatePermission(
    permissionId: string,
    payload: UpdatePermissionPayload,
  ) {
    loadingUpdate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PermissionItem>(
        `${baseUrl}/v1/permissions/${permissionId}`,
        {
          method: "PUT",
          headers: getAuthHeaders(),
          body: payload,
        },
      );

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal memperbarui permission.",
      );
      throw error;
    } finally {
      loadingUpdate.value = false;
    }
  }

  async function deletePermission(permissionId: string) {
    loadingDelete.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api(`${baseUrl}/v1/permissions/${permissionId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal menghapus permission.",
      );
      throw error;
    } finally {
      loadingDelete.value = false;
    }
  }

  return {
    permissions,
    selectedPermission,
    loadingList,
    loadingCreate,
    loadingUpdate,
    loadingDelete,
    errorMessage,
    hasPermissions,
    fetchPermissions,
    createPermission,
    updatePermission,
    deletePermission,
    clearError,
  };
});
