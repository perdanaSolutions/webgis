import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import type { PermissionItem } from "~/stores/managePermissionStore";

function flattenMenusForAccess(
  items: any[] | null | undefined,
  parentTitle = "",
): MenuAccessItem[] {
  const result: MenuAccessItem[] = [];
  for (const menu of items ?? []) {
    result.push({
      id: String(menu?.id ?? ""),
      title: String(menu?.title ?? ""),
      to: String(menu?.to ?? ""),
      level: Number(menu?.level ?? 1),
      parentTitle,
    });
    if (Array.isArray(menu?.children) && menu.children.length) {
      result.push(
        ...flattenMenusForAccess(menu.children, String(menu?.title ?? "")),
      );
    }
  }
  return result;
}

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
  level: number;
  parentTitle: string;
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
  const allDataArea = ref([]);
  const allDataPerusahaan = ref([]);
  const allDataEstate = ref([]);
  const allDataAfdeling = ref([]);
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

      allDataMenu.value = flattenMenusForAccess(
        Array.isArray(response) ? response : [],
      ) as any;

      return allDataMenu.value;
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataArea() {
    try {
      const baseUrl = getApiBaseUrl();

      // TODO: sesuaikan endpoint area jika berbeda
      const response = await $api(`${baseUrl}/v1/spatial/area?limit=100`, {
        method: "GET",
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
      });

      const getResponse = response as any;
      allDataArea.value =
        getResponse?.data ?? (Array.isArray(response) ? response : []);

      return allDataArea.value;
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

  async function initDataPerusahaanByArea(areaId: string) {
    try {
      if (!areaId) return [];

      const baseUrl = getApiBaseUrl();

      // TODO: sesuaikan endpoint perusahaan by area jika berbeda
      const response = await $api(
        `${baseUrl}/v1/spatial/pt?area_id=${encodeURIComponent(areaId)}&limit=100`,
        {
          method: "GET",
          headers: {
            accept: "application/json",
            "Content-Type": "application/json",
          },
        },
      );

      const normalized = Array.isArray(response)
        ? response
        : ((response as any)?.data ?? []);

      return normalized as any[];
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataEstate(kodept: string) {
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api(
        `${baseUrl}/v1/spatial/estate?kode_pt=${kodept}&limit=100`,
        {
          method: "GET",
          headers: {
            accept: "application/json",
            "Content-Type": "application/json",
          },
        },
      );

      const normalizedEstate = Array.isArray(response)
        ? response
        : ((response as any)?.data ?? []);

      allDataEstate.value = normalizedEstate as any;

      return normalizedEstate;
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataAfdelingByEstate(kodeEstate: string) {
    try {
      if (!kodeEstate) return [];

      const baseUrl = getApiBaseUrl();

      // TODO: sesuaikan endpoint afdeling by estate jika berbeda
      const response = await $api(
        `${baseUrl}/v1/spatial/afdeling?kode_est=${encodeURIComponent(kodeEstate)}&limit=100`,
        {
          method: "GET",
          headers: {
            accept: "application/json",
            "Content-Type": "application/json",
          },
        },
      );

      const normalized = Array.isArray(response)
        ? response
        : ((response as any)?.data ?? []);

      return normalized as any[];
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

  function resolveTransactionTableName(
    kode: string,
    tableName: string,
    validTables: string[],
  ) {
    const validByLower = new Map(
      validTables.map((name) => [name.toLowerCase(), name]),
    );
    const candidates = [tableName, kode].filter(Boolean);

    for (const candidate of candidates) {
      const exact = validByLower.get(candidate.toLowerCase());
      if (exact) return exact;
    }

    for (const candidate of candidates) {
      const suffix = `.${candidate.toLowerCase()}`;
      const match = validTables.find((name) => name.toLowerCase().endsWith(suffix));
      if (match) return match;
    }

    // Endpoint daftar tabel gagal, tapi nama di katalog sudah schema.tabel.
    if (tableName.includes(".")) return tableName;
    return "";
  }

  async function initDataTableTransaksi() {
    loadingTransaction.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const [jenisResponse, tablesResponse] = await Promise.all([
        $api<any[]>(`${baseUrl}/v1/spatial/geo/jenis`, {
          method: "GET",
          headers: getAuthHeaders(),
        }),
        $api<string[]>(`${baseUrl}/v1/database/tables`, {
          method: "GET",
          headers: getAuthHeaders(),
        }).catch(() => [] as string[]),
      ]);

      const normalizedData = Array.isArray(jenisResponse)
        ? jenisResponse
        : ((jenisResponse as any)?.data ?? []);
      const validTables = (Array.isArray(tablesResponse) ? tablesResponse : [])
        .map((name) => String(name ?? "").trim())
        .filter(Boolean);

      const seen = new Set<string>();
      allDataTransaksi.value = normalizedData.flatMap((item: any) => {
        const kode = String(item?.kode ?? item?.code ?? "").trim();
        const tableName = String(item?.table_name ?? "").trim();
        const qualified = resolveTransactionTableName(kode, tableName, validTables);
        const key = qualified.toLowerCase();
        if (!qualified || seen.has(key)) return [];
        seen.add(key);
        return [{
          id: qualified,
          kode,
          table_name: qualified,
          nama_table_transaksi: qualified,
          title: String(item?.nama ?? item?.name ?? (kode || qualified)),
        }];
      }) as any;

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

  function saveErrorMessage(error: any, fallback: string) {
    if (error?.data) return getErrorMessage(error, fallback);
    return error?.message || fallback;
  }

  function toRoleBody(payload: any) {
    const menuIds = uniqueStringArray(payload?.akses_menu ?? payload?.menu_ids ?? []);
    const requestedTransaksi = uniqueStringArray(
      payload?.akses_transaksi ?? payload?.transaksi_ids ?? [],
    );
    const transaksiIds = uniqueStringArray(
      requestedTransaksi
        .map((value) => lookupTransactionTable(String(value)))
        .filter(Boolean),
    );
    const tree = Array.isArray(payload?.akses_data) ? payload.akses_data : [];
    const wantsWilayah =
      uniqueStringArray([
        ...(payload?.area_ids ?? []),
        ...(payload?.perusahaan_ids ?? []),
        ...(payload?.estate_ids ?? []),
        ...(payload?.afdeling_ids ?? []),
      ]).length > 0;

    if (wantsWilayah && tree.length === 0) {
      throw new Error(
        "Data wilayah belum siap disimpan. Tunggu pilihan area selesai dimuat, lalu simpan lagi.",
      );
    }
    if (requestedTransaksi.length > 0 && transaksiIds.length === 0) {
      throw new Error(
        "Tabel transaksi tidak dikenali. Muat ulang daftar transaksi, lalu simpan lagi.",
      );
    }

    return {
      nama: String(payload?.nama ?? "").trim(),
      deskripsi: payload?.deskripsi ?? "",
      akses_menu: menuIds,
      akses_data: tree,
      akses_transaksi: transaksiIds,
    };
  }

  async function createRole(payload: any) {
    loadingCreate.value = true;
    clearError();
    try {
      const baseUrl = getApiBaseUrl();
      return await $api<RoleItem>(`${baseUrl}/v1/roles/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: toRoleBody(payload),
      });
    } catch (error: any) {
      errorMessage.value = saveErrorMessage(error, "Gagal membuat role.");
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  function lookupTransactionTable(value: string) {
    const key = value.trim().toLowerCase();
    if (!key) return "";
    const match = (allDataTransaksi.value as any[]).find((item) =>
      [item?.id, item?.kode, item?.table_name, item?.nama_table_transaksi]
        .map((field) => String(field ?? "").trim().toLowerCase())
        .includes(key),
    );
    const resolved = String(
      match?.nama_table_transaksi ?? match?.table_name ?? "",
    ).trim();
    if (resolved) return resolved;
    return value.includes(".") ? value.trim() : "";
  }

  async function getExistingAksesByRole(roleId: string) {
    const baseUrl = getApiBaseUrl();
    const role = await $api<any>(`${baseUrl}/v1/roles/${roleId}`, {
      method: "GET",
      headers: getAuthHeaders(),
    });

    return {
      menu: Array.isArray(role?.akses_menu) ? role.akses_menu : [],
      data: Array.isArray(role?.akses_wilayah) ? role.akses_wilayah : [],
      transaksi: Array.isArray(role?.akses_transaksi) ? role.akses_transaksi : [],
    };
  }

  function uniqueStringArray(values: any[] = []) {
    return Array.from(
      new Set(
        (values ?? [])
          .map((item) => String(item ?? "").trim())
          .filter((item) => !!item),
      ),
    );
  }

  async function updateRole(roleId: string, payload: any) {
    loadingUpdate.value = true;
    clearError();
    try {
      const baseUrl = getApiBaseUrl();
      return await $api<RoleItem>(`${baseUrl}/v1/roles/${roleId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: toRoleBody(payload),
      });
    } catch (error: any) {
      errorMessage.value = saveErrorMessage(error, "Gagal memperbarui role.");
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
    allDataArea,
    allDataPerusahaan,
    allDataEstate,
    allDataAfdeling,
    allDataTransaksi,
    fetchRoles,
    createRole,
    updateRole,
    getExistingAksesByRole,
    clearError,
    initDataMenu,
    initDataArea,
    initDataPerusahaan,
    initDataPerusahaanByArea,
    initDataEstate,
    initDataAfdelingByEstate,
    initDataTableTransaksi,
  };
});
