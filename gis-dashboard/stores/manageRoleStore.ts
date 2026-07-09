import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import type { PermissionItem } from "~/stores/managePermissionStore";

export type RoleItem = {
  id: string;
  nama: string;
  deskripsi: string;
  created_at: string;
  permissions: PermissionItem[];
};

export type CreateRolePayload = {
  nama: string;
  deskripsi: string;
  permission_ids: string[];
};

export type UpdateRolePayload = {
  nama: string;
  deskripsi: string;
  permission_ids: string[];
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const useManageRoleStore = defineStore("manageRole", () => {
  const { $api } = useNuxtApp();

  const roles = ref<RoleItem[]>([]);
  const permissions = ref<PermissionItem[]>([]);

  const loadingList = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingPermissions = ref(false);
  const errorMessage = ref("");

  const hasRoles = computed(() => roles.value.length > 0);

  function getAuthHeaders() {
    return {
      accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  function clearError() {
    errorMessage.value = "";
  }

  async function fetchRoles() {
    loadingList.value = true;
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
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data role.");
      throw error;
    } finally {
      loadingList.value = false;
    }
  }

  async function fetchPermissions() {
    loadingPermissions.value = true;
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
      loadingPermissions.value = false;
    }
  }

  async function createRole(payload: CreateRolePayload) {
    loadingCreate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<RoleItem>(`${baseUrl}/v1/roles/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal membuat role.");
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  async function updateRole(roleId: string, payload: UpdateRolePayload) {
    loadingUpdate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<RoleItem>(`${baseUrl}/v1/roles/${roleId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal memperbarui role.");
      throw error;
    } finally {
      loadingUpdate.value = false;
    }
  }

  return {
    roles,
    permissions,
    loadingList,
    loadingCreate,
    loadingUpdate,
    loadingPermissions,
    errorMessage,
    hasRoles,
    fetchRoles,
    fetchPermissions,
    createRole,
    updateRole,
    clearError,
  };
});
