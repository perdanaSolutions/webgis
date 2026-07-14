import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import {
  parsePermissionMeta,
  type PermissionScopeCategory,
} from "~/composables/usePermissionScope";

export type PermissionItem = {
  kode: string;
  resource: string;
  aksi: string;
  deskripsi: string;
  id: string;
};

export type PermissionScopeSelection = {
  menuPermissionIds: string[];
  ptPermissionIds: string[];
  estatePermissionIds: string[];
  transactionPermissionIds: string[];
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

export type ScopePermissionGroup = {
  category: PermissionScopeCategory;
  label: string;
  items: PermissionItem[];
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

  const scopeGroups = computed<ScopePermissionGroup[]>(() => {
    const menu: PermissionItem[] = [];
    const pt: PermissionItem[] = [];
    const estate: PermissionItem[] = [];
    const transaction: PermissionItem[] = [];
    const general: PermissionItem[] = [];

    permissions.value.forEach((permission) => {
      const meta = parsePermissionMeta(permission);
      if (meta.category === "menu") menu.push(permission);
      else if (meta.category === "pt") pt.push(permission);
      else if (meta.category === "estate") estate.push(permission);
      else if (meta.category === "transaction") transaction.push(permission);
      else general.push(permission);
    });

    return [
      {
        category: "menu",
        label: "Level 1 - Akses Menu / Modul Dashboard",
        items: menu,
      },
      { category: "pt", label: "Level 2 - Akses Data Map per PT", items: pt },
      {
        category: "estate",
        label: "Level 3 - Akses Data Map per Estate",
        items: estate,
      },
      {
        category: "transaction",
        label: "Level 4 - Akses Data Transaksi",
        items: transaction,
      },
      { category: "general", label: "Permission Lainnya", items: general },
    ];
  });

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
    scopeGroups,
    fetchPermissions,
    createPermission,
    updatePermission,
    deletePermission,
    clearError,
  };
});
