import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import { flattenMenuTree } from "~/utils/menuTree";

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
  parent_id: string | null;
  level: number;
  children: MenuItem[];
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
  parent_id: string | null;
};

export type MenuFormState = Omit<CreateMenuPayload, "parent_id"> & {
  parent_id: string;
};

export type UpdateMenuPayload = CreateMenuPayload;

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

function normalizeMenu(raw: any): MenuItem {
  const children = Array.isArray(raw?.children) ? raw.children.map(normalizeMenu) : [];
  return {
    id: String(raw?.id ?? ""),
    title: String(raw?.title ?? ""),
    description: String(raw?.description ?? ""),
    bg_class: String(raw?.bg_class ?? raw?.bgClass ?? "bg-blue-50"),
    icon_class: String(raw?.icon_class ?? raw?.iconClass ?? "text-blue-500"),
    arrow_class: String(raw?.arrow_class ?? raw?.arrowClass ?? "text-blue-500"),
    to: String(raw?.to ?? ""),
    icon: String(raw?.icon ?? "report"),
    order_position: Number(raw?.order_position ?? 0),
    parent_id: raw?.parent_id ?? raw?.parentId ?? null,
    level: Number(raw?.level ?? 1),
    children,
  };
}

export const useManageMenuStore = defineStore("manageMenu", () => {
  const { $api } = useNuxtApp();

  const menus = ref<MenuItem[]>([]);
  const loadingList = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingDelete = ref(false);
  const errorMessage = ref("");

  const flatMenus = computed(() => flattenMenuTree(menus.value));
  const hasMenus = computed(() => flatMenus.value.length > 0);

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
      const response = await $api<any[]>(`${baseUrl}/v1/menus/`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      menus.value = Array.isArray(response) ? response.map(normalizeMenu) : [];
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
      const response = await $api<any>(`${baseUrl}/v1/menus/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      return normalizeMenu(response);
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
      const response = await $api<any>(`${baseUrl}/v1/menus/${menuId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: payload,
      });

      return normalizeMenu(response);
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
    flatMenus,
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
