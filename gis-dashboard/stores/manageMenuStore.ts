import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

export type MenuItem = {
  id: string;
  title: string;
  description: string;
  bg_class: string;
  icon_class: string;
  arrow_class: string;
  to: string;
  icon: string;
  order_position: number;
  created_at?: string;
  updated_at?: string;
};

export type CreateMenuPayload = {
  title: string;
  description: string;
  bg_class: string;
  icon_class: string;
  arrow_class: string;
  to: string;
  icon: string;
  order_position: number;
};

export type UpdateMenuPayload = CreateMenuPayload;

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const useManageMenuStore = defineStore("manageMenu", () => {
  const { $api } = useNuxtApp();

  const menus = ref<MenuItem[]>([]);
  const loadingList = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingDelete = ref(false);
  const errorMessage = ref("");

  const hasMenus = computed(() => menus.value.length > 0);

  function getAuthHeaders() {
    return {
      accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  function clearError() {
    errorMessage.value = "";
  }

  async function fetchMenus() {
    loadingList.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<MenuItem[]>(`${baseUrl}/v1/menus/`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      menus.value = Array.isArray(response) ? response : [];
      return menus.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data menu.");
      throw error;
    } finally {
      loadingList.value = false;
    }
  }

  async function createMenu(payload: CreateMenuPayload) {
    loadingCreate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<MenuItem>(`${baseUrl}/v1/menus/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal menambah menu.");
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  async function updateMenu(menuId: string, payload: UpdateMenuPayload) {
    loadingUpdate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<MenuItem>(`${baseUrl}/v1/menus/${menuId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal memperbarui menu.");
      throw error;
    } finally {
      loadingUpdate.value = false;
    }
  }

  async function deleteMenu(menuId: string) {
    loadingDelete.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      await $api(`${baseUrl}/v1/menus/${menuId}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal menghapus menu.");
      throw error;
    } finally {
      loadingDelete.value = false;
    }
  }

  return {
    menus,
    loadingList,
    loadingCreate,
    loadingUpdate,
    loadingDelete,
    errorMessage,
    hasMenus,
    fetchMenus,
    createMenu,
    updateMenu,
    deleteMenu,
    clearError,
  };
});
