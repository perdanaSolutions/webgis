import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import { buildMonitoringQuery, type MonitoringQuery, type MonitoringStatus } from "~/utils/monitoringQuery";

export type { MonitoringQuery, MonitoringStatus };

export type MonitoringUserItem = {
  id: string;
  username: string;
  nama_lengkap: string;
  email: string;
  role: string[];
  akun_aktif: boolean;
  terkunci: boolean;
  status: MonitoringStatus;
  jumlah_sesi: number;
  login_terakhir: string | null;
  logout_terakhir: string | null;
  aktivitas_terakhir: string | null;
  ip_terakhir: string | null;
};

export type MonitoringSummary = {
  total_user: number;
  online: number;
  offline: number;
};

export type MonitoringListResponse = {
  total_data: number;
  page: number;
  limit: number;
  total_page: number;
  data: MonitoringUserItem[];
  ringkasan: MonitoringSummary;
  /** redis = registry sesi (akurat); log_aktivitas = perkiraan dari log LOGIN/LOGOUT. */
  sumber: "redis" | "log_aktivitas";
};

export const useMonitoringUserStore = defineStore("monitoringUser", () => {
  const { $api } = useNuxtApp();

  const items = ref<MonitoringUserItem[]>([]);
  const summary = ref<MonitoringSummary>({ total_user: 0, online: 0, offline: 0 });
  const sumber = ref<MonitoringListResponse["sumber"] | "">("");

  const totalData = ref(0);
  const page = ref(1);
  const limit = ref(10);
  const totalPage = ref(0);

  const loading = ref(false);
  const errorMessage = ref("");
  const lastFetchedAt = ref<Date | null>(null);

  const hasItems = computed(() => items.value.length > 0);

  function clearError() {
    errorMessage.value = "";
  }

  /** `silent` = muat ulang otomatis: tabel tidak berkedip "Memuat…" dan kegagalan tidak menimpa data lama. */
  async function fetchUsers(query: MonitoringQuery = {}, options: { silent?: boolean } = {}) {
    if (!options.silent) loading.value = true;
    clearError();

    try {
      const baseUrl = useRuntimeConfig().public.apiBaseUrlPython;
      const queryString = buildMonitoringQuery(query);
      const endpoint = `${baseUrl}/v1/monitoring/users`;
      const response = await $api<MonitoringListResponse>(
        queryString ? `${endpoint}?${queryString}` : endpoint,
        { method: "GET", headers: { accept: "application/json" } },
      );

      items.value = response.data ?? [];
      summary.value = response.ringkasan ?? { total_user: 0, online: 0, offline: 0 };
      sumber.value = response.sumber ?? "";
      totalData.value = response.total_data ?? 0;
      page.value = response.page ?? query.page ?? 1;
      limit.value = response.limit ?? query.limit ?? 10;
      totalPage.value = response.total_page ?? 0;
      lastFetchedAt.value = new Date();
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal mengambil data monitoring user.");
      throw error;
    } finally {
      if (!options.silent) loading.value = false;
    }
  }

  return {
    items,
    summary,
    sumber,
    totalData,
    page,
    limit,
    totalPage,
    loading,
    errorMessage,
    lastFetchedAt,
    hasItems,
    clearError,
    fetchUsers,
  };
});
