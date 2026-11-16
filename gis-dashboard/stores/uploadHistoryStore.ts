import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

export type UploadStatus =
  | "IN_PROGRESS"
  | "SUCCESS"
  | "PARTIAL_SUCCESS"
  | "FAILED"
  | "ABANDONED";

export type UploadSourceType = "GEOJSON_UPLOAD" | "EXCEL_UPLOAD";

export type UploadHistoryItem = {
  id: string;
  jenis_sumber: string;
  tabel_tujuan: string;
  layer: string | null;
  nama_file: string | null;
  periode: string | null;
  jumlah_data: number;
  status: UploadStatus;
  pesan_error: string | null;
  diupload_oleh: {
    id: string;
    nama_lengkap: string;
    username: string;
  } | null;
  mulai: string;
  selesai: string | null;
  durasi_detik: number | null;
};

export type UploadHistoryDetail = UploadHistoryItem & {
  metadata: Record<string, any> | null;
};

export type UploadHistoryListResponse = {
  total_data: number;
  page: number;
  limit: number;
  total_page: number;
  data: UploadHistoryItem[];
};

export type UploadHistoryListQuery = {
  search?: string;
  status?: UploadStatus | "";
  source_type?: UploadSourceType | "";
  tanggal_dari?: string;
  tanggal_sampai?: string;
  bulan?: number | "";
  tahun?: number | "";
  hari?: number | ""; // 1-31
  page?: number;
  limit?: number;
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

function buildQueryParams(query: UploadHistoryListQuery = {}) {
  const params = new URLSearchParams();

  if (query.search) params.set("search", query.search);
  if (query.status) params.set("status", query.status);
  if (query.source_type) params.set("source_type", query.source_type);
  if (query.tanggal_dari) params.set("tanggal_dari", query.tanggal_dari);
  if (query.tanggal_sampai) params.set("tanggal_sampai", query.tanggal_sampai);
  if (query.tahun) params.set("tahun", String(query.tahun));
  if (query.bulan) params.set("bulan", String(query.bulan));
  if (query.hari) params.set("hari", String(query.hari));
  if (typeof query.page === "number") params.set("page", String(query.page));
  if (typeof query.limit === "number") params.set("limit", String(query.limit));

  return params.toString();
}

export const useUploadHistoryStore = defineStore("uploadHistory", () => {
  const { $api } = useNuxtApp();

  const items = ref<UploadHistoryItem[]>([]);
  const selectedItem = ref<UploadHistoryDetail | null>(null);

  const totalData = ref(0);
  const page = ref(1);
  const limit = ref(10);
  const totalPage = ref(0);

  const loadingList = ref(false);
  const loadingDetail = ref(false);

  const errorMessage = ref("");

  const hasItems = computed(() => items.value.length > 0);

  function getAuthHeaders() {
    return {
      accept: "application/json",
    };
  }

  function clearError() {
    errorMessage.value = "";
  }

  async function fetchUploadHistory(query: UploadHistoryListQuery = {}) {
    loadingList.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const queryString = buildQueryParams(query);
      const endpoint = `${baseUrl}/v1/upload-history/`;
      const url = queryString ? `${endpoint}?${queryString}` : endpoint;

      const response = await $api<UploadHistoryListResponse>(url, {
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
        "Gagal mengambil riwayat upload.",
      );
      throw error;
    } finally {
      loadingList.value = false;
    }
  }

  async function fetchUploadHistoryById(batchId: string) {
    loadingDetail.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<UploadHistoryDetail>(
        `${baseUrl}/v1/upload-history/${batchId}`,
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
        "Gagal mengambil detail riwayat upload.",
      );
      throw error;
    } finally {
      loadingDetail.value = false;
    }
  }

  /**
   * Ambil SEMUA data yang cocok dengan filter (tanpa pagination) untuk di-export.
   * Tidak mengubah state halaman/items yang sedang ditampilkan. Limit 100 per halaman (batas backend).
   */
  async function fetchAllMatching(query: UploadHistoryListQuery = {}): Promise<UploadHistoryItem[]> {
    const baseUrl = getApiBaseUrl();
    const firstQuery = buildQueryParams({ ...query, page: 1, limit: 100 });
    const first = await $api<UploadHistoryListResponse>(
      `${baseUrl}/v1/upload-history/?${firstQuery}`,
      { method: "GET", headers: getAuthHeaders() },
    );
    const all = [...(first.data ?? [])];
    const totalPage = first.total_page ?? 1;
    let currentPage = first.page ?? 1;
    while (currentPage < totalPage) {
      currentPage += 1;
      const qs = buildQueryParams({ ...query, page: currentPage, limit: 100 });
      const resp = await $api<UploadHistoryListResponse>(
        `${baseUrl}/v1/upload-history/?${qs}`,
        { method: "GET", headers: getAuthHeaders() },
      );
      all.push(...(resp.data ?? []));
    }
    return all;
  }

  return {
    items,
    selectedItem,
    totalData,
    page,
    limit,
    totalPage,
    loadingList,
    loadingDetail,
    errorMessage,
    hasItems,
    fetchUploadHistory,
    fetchUploadHistoryById,
    clearError,
    fetchAllMatching,
  };
});
