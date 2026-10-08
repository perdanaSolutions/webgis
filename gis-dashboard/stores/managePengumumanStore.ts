import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

export type PengumumanStatus = "aktif" | "terjadwal" | "kedaluwarsa" | "nonaktif";

export type PengumumanItem = {
  id: string;
  judul: string;
  isi: string;
  is_active: boolean;
  status: PengumumanStatus;
  tanggal_mulai: string | null;
  tanggal_berakhir: string | null;
  dibuat_oleh: string | null;
  created_at?: string;
  updated_at?: string;
};

export type PengumumanPayload = {
  judul: string;
  isi: string;
  is_active: boolean;
  tanggal_mulai: string | null;
  tanggal_berakhir: string | null;
};

export type PengumumanListResponse = {
  total_data: number;
  page: number;
  limit: number;
  total_page: number;
  data: PengumumanItem[];
};

export type PengumumanListQuery = {
  search?: string;
  status?: PengumumanStatus | "";
  page?: number;
  limit?: number;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

function buildQueryParams(query: PengumumanListQuery = {}) {
  const params = new URLSearchParams();

  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (typeof query.page === "number") params.set("page", String(query.page));
  if (typeof query.limit === "number") params.set("limit", String(query.limit));

  return params.toString();
}

export const useManagePengumumanStore = defineStore("managePengumuman", () => {
  const { $api } = useNuxtApp();

  const items = ref<PengumumanItem[]>([]);
  const activeItems = ref<PengumumanItem[]>([]);
  const selectedItem = ref<PengumumanItem | null>(null);

  const totalData = ref(0);
  const page = ref(1);
  const limit = ref(10);
  const totalPage = ref(0);

  const loadingList = ref(false);
  const loadingActive = ref(false);
  const loadingDetail = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingDelete = ref(false);

  const errorMessage = ref("");

  const hasItems = computed(() => items.value.length > 0);

  function getAuthHeaders() {
    return {
      accept: "application/json",
      "Content-Type": "application/json",
    };
  }

  function clearError() {
    errorMessage.value = "";
  }

  async function fetchPengumuman(query: PengumumanListQuery = {}) {
    loadingList.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const queryString = buildQueryParams(query);
      const endpoint = `${baseUrl}/v1/pengumuman/`;
      const url = queryString ? `${endpoint}?${queryString}` : endpoint;

      const response = await $api<PengumumanListResponse>(url, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      items.value = response.data ?? [];
      totalData.value = response.total_data ?? 0;
      page.value = response.page ?? query.page ?? 1;
      limit.value = response.limit ?? query.limit ?? 10;
      totalPage.value = response.total_page ?? 0;

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil daftar pengumuman.",
      );
      throw error;
    } finally {
      loadingList.value = false;
    }
  }

  async function fetchActivePengumuman() {
    loadingActive.value = true;

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PengumumanListResponse>(
        `${baseUrl}/v1/pengumuman/?status=aktif&page=1&limit=50`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      activeItems.value = response.data ?? [];
      return response;
    } catch {
      activeItems.value = [];
    } finally {
      loadingActive.value = false;
    }
  }

  async function fetchPengumumanById(announcementId: string) {
    loadingDetail.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PengumumanItem>(
        `${baseUrl}/v1/pengumuman/${announcementId}`,
        {
          method: "GET",
          headers: getAuthHeaders(),
        },
      );

      selectedItem.value = response;
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil detail pengumuman.",
      );
      throw error;
    } finally {
      loadingDetail.value = false;
    }
  }

  async function createPengumuman(payload: PengumumanPayload) {
    loadingCreate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PengumumanItem>(`${baseUrl}/v1/pengumuman/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal membuat pengumuman baru.",
      );
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  async function updatePengumuman(
    announcementId: string,
    payload: PengumumanPayload,
  ) {
    loadingUpdate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<PengumumanItem>(
        `${baseUrl}/v1/pengumuman/${announcementId}`,
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
        "Gagal memperbarui pengumuman.",
      );
      throw error;
    } finally {
      loadingUpdate.value = false;
    }
  }

  async function deletePengumuman(announcementId: string) {
    loadingDelete.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api(
        `${baseUrl}/v1/pengumuman/${announcementId}`,
        {
          method: "DELETE",
          headers: getAuthHeaders(),
        },
      );

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal menghapus pengumuman.",
      );
      throw error;
    } finally {
      loadingDelete.value = false;
    }
  }

  return {
    items,
    activeItems,
    selectedItem,
    totalData,
    page,
    limit,
    totalPage,
    loadingList,
    loadingActive,
    loadingDetail,
    loadingCreate,
    loadingUpdate,
    loadingDelete,
    errorMessage,
    hasItems,
    fetchPengumuman,
    fetchActivePengumuman,
    fetchPengumumanById,
    createPengumuman,
    updatePengumuman,
    deletePengumuman,
    clearError,
  };
});
