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

export type MenuAccessItem = {
  id: string;
  title: string;
  to: string;
};

export type MasterDataAccessItem = {
  id: string;
  title: string;
  type: "pt" | "estate";
};

export type TransactionAccessItem = {
  id: string;
  title: string;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const useManageRoleStore = defineStore("manageRole", () => {
  const { $api } = useNuxtApp();

  const roles = ref<RoleItem[]>([]);
  const menuItems = ref<MenuAccessItem[]>([]);
  const masterDataItems = ref<MasterDataAccessItem[]>([]);
  const transactionItems = ref<TransactionAccessItem[]>([]);
  const allDataMenu = ref([]);
  const allDataPerusahaan = ref([]);
  const allDataEstate = ref([]);
  const allDataTransaksi = ref([]);

  const loadingList = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingMenu = ref(false);
  const loadingMasterData = ref(false);
  const loadingTransaction = ref(false);
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

  async function initDataMenu() {
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api(`${baseUrl}/v1/menus/`, {
        method: "GET",
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
      });

      allDataMenu.value = response as any;

      return response;
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataPerusahaan() {
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api(`${baseUrl}/v1/spatial/pt?limit=100`, {
        method: "GET",
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
      });
      var getResponse = response as any;
      allDataPerusahaan.value = getResponse.data ?? [];

      return response;
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataEstate(kodept: string) {
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api(
        `${baseUrl}/v1/spatial/estate?kode_pt=${kodept}`,
        {
          method: "GET",
          headers: {
            accept: "application/json",
            "Content-Type": "application/json",
          },
        },
      );

      allDataEstate.value = response as any;

      return response;
    } catch (error: any) {
      throw error;
    }
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

  async function fetchMasterDataItems() {
    loadingMasterData.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      // kerangka endpoint master data (PT & Estate)
      const [ptResponse, estateResponse] = await Promise.all([
        $api<any[]>(`${baseUrl}/v1/pts/`, {
          method: "GET",
          headers: getAuthHeaders(),
        }),
        $api<any[]>(`${baseUrl}/v1/estates/`, {
          method: "GET",
          headers: getAuthHeaders(),
        }),
      ]);

      const normalizedPt = (ptResponse ?? []).map((item, index) => ({
        id: String(item.id ?? item.uuid ?? `pt-${index}`),
        title: String(
          item.nama ?? item.name ?? item.title ?? `PT ${index + 1}`,
        ),
        type: "pt" as const,
      }));

      const normalizedEstate = (estateResponse ?? []).map((item, index) => ({
        id: String(item.id ?? item.uuid ?? `estate-${index}`),
        title: String(
          item.nama ?? item.name ?? item.title ?? `Estate ${index + 1}`,
        ),
        type: "estate" as const,
      }));

      masterDataItems.value = [...normalizedPt, ...normalizedEstate];
      return masterDataItems.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil data perusahaan & estate.",
      );
      throw error;
    } finally {
      loadingMasterData.value = false;
    }
  }

  async function fetchTransactionItems() {
    loadingTransaction.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      // kerangka endpoint transaksi
      const response = await $api<any[]>(
        `${baseUrl}/v1/transactions/access-options/`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      transactionItems.value = (response ?? []).map((item, index) => ({
        id: String(item.id ?? item.uuid ?? `trx-${index}`),
        title: String(
          item.nama ?? item.name ?? item.title ?? `Transaksi ${index + 1}`,
        ),
      }));

      return transactionItems.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil data akses transaksi.",
      );
      throw error;
    } finally {
      loadingTransaction.value = false;
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
    menuItems,
    masterDataItems,
    transactionItems,
    loadingList,
    loadingCreate,
    loadingUpdate,
    loadingMenu,
    loadingMasterData,
    loadingTransaction,
    errorMessage,
    hasRoles,
    allDataMenu,
    allDataPerusahaan,
    allDataEstate,
    fetchRoles,
    fetchMasterDataItems,
    fetchTransactionItems,
    createRole,
    updateRole,
    clearError,
    initDataMenu,
    initDataPerusahaan,
    initDataEstate,
  };
});
