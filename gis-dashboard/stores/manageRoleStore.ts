import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import type { PermissionItem } from "~/stores/managePermissionStore";

function flattenMenusForAccess(
  items: any[] | null | undefined,
  parentId: string | null = null,
  parentTitle = "",
): MenuAccessItem[] {
  const result: MenuAccessItem[] = [];
  for (const menu of items ?? []) {
    const id = String(menu?.id ?? "");
    result.push({
      id,
      title: String(menu?.title ?? ""),
      to: String(menu?.to ?? ""),
      level: Number(menu?.level ?? 1),
      parent_id: parentId,
      parentTitle,
    });
    if (Array.isArray(menu?.children) && menu.children.length) {
      result.push(
        ...flattenMenusForAccess(
          menu.children,
          id,
          String(menu?.title ?? ""),
        ),
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
  parent_id: string | null;
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
  const allDataMenu = ref<any[]>([]);
  const allDataArea = ref<any[]>([]);
  const allDataPerusahaan = ref<any[]>([]);
  const allDataEstate = ref<any[]>([]);
  const allDataAfdeling = ref<any[]>([]);
  const allDataLayer = ref<any[]>([]);
  const allDataTransaksi = ref<any[]>([]);

  const loadingList = ref(false);
  const loadingCreate = ref(false);
  const loadingUpdate = ref(false);
  const loadingMenu = ref(false);
  const loadingMasterData = ref(false);
  const loadingLayer = ref(false);
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

  async function fetchAllSpatialPages(pathWithQuery: string) {
    const baseUrl = getApiBaseUrl();
    const limit = 100;
    const items: any[] = [];
    let page = 1;
    let totalPage = 1;

    while (page <= totalPage && page <= 200) {
      const joiner = pathWithQuery.includes("?") ? "&" : "?";
      const response = await $api(
        `${baseUrl}${pathWithQuery}${joiner}page=${page}&limit=${limit}`,
        {
          method: "GET",
          headers: {
            accept: "application/json",
          },
        },
      );

      const batch = Array.isArray(response)
        ? response
        : ((response as any)?.data ?? []);
      items.push(...batch);

      const reportedPages = Number((response as any)?.total_page ?? 1);
      const totalData = Number((response as any)?.total_data ?? items.length);
      totalPage = Number.isFinite(reportedPages) && reportedPages > 0 ? reportedPages : 1;
      if (Array.isArray(response) || batch.length < limit || items.length >= totalData) break;
      page += 1;
    }

    return items;
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

      allDataArea.value = await fetchAllSpatialPages("/v1/spatial/area");

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

      return await fetchAllSpatialPages(
        `/v1/spatial/pt?area_id=${encodeURIComponent(areaId)}`,
      );
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataEstate(kodept: string) {
    try {
      const normalizedEstate = await fetchAllSpatialPages(
        `/v1/spatial/estate?kode_pt=${encodeURIComponent(kodept)}`,
      );

      allDataEstate.value = normalizedEstate as any;

      return normalizedEstate;
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataAfdelingByEstate(kodeEstate: string) {
    try {
      if (!kodeEstate) return [];

      return await fetchAllSpatialPages(
        `/v1/spatial/afdeling?kode_est=${encodeURIComponent(kodeEstate)}`,
      );
    } catch (error: any) {
      throw error;
    }
  }

  async function initDataBlokByAfdeling(kodeEstate: string, kodeAfd: string) {
    try {
      if (!kodeEstate || !kodeAfd) return [];

      return await fetchAllSpatialPages(
        `/v1/spatial/blok?kode_est=${encodeURIComponent(kodeEstate)}&kode_afd=${encodeURIComponent(kodeAfd)}`,
      );
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

  function grantKeys(item: any) {
    return [
      item?.id,
      item?.kode,
      item?.table,
      item?.table_name,
      item?.nama_table_transaksi,
      item?.physical_table,
    ]
      .map((field) => String(field ?? "").trim().toLowerCase())
      .filter(Boolean);
  }

  function physicalTableOf(item: any) {
    return String(
      item?.nama_table_transaksi ?? item?.physical_table ?? item?.table_name ?? "",
    ).trim();
  }

  function matchPhysicalTable(catalog: any[], value: string) {
    const key = String(value ?? "").trim().toLowerCase();
    if (!key) return "";
    const match = (catalog ?? []).find((item) => grantKeys(item).includes(key));
    return match ? physicalTableOf(match) : "";
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

  async function initDataLayer() {
    loadingLayer.value = true;
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
      allDataLayer.value = normalizedData.flatMap((item: any) => {
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

      return allDataLayer.value;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Gagal mengambil data layer.",
      );
      throw error;
    } finally {
      loadingLayer.value = false;
    }
  }

  async function initDataTableTransaksi() {
    loadingTransaction.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<any>(`${baseUrl}/v1/spatial/history/tables`, {
        method: "GET",
        headers: getAuthHeaders(),
      });
      const rows = Array.isArray(response)
        ? response
        : ((response as any)?.data ?? []);

      const seen = new Set<string>();
      allDataTransaksi.value = rows.flatMap((item: any) => {
        const physical = String(item?.physical_table ?? "").trim();
        const table = String(item?.table ?? "").trim();
        const key = physical.toLowerCase();
        if (!physical || seen.has(key)) return [];
        seen.add(key);
        const label = String(item?.label ?? (table || physical));
        return [{
          id: physical,
          table,
          physical_table: physical,
          table_name: physical,
          nama_table_transaksi: physical,
          label,
          title: label,
        }];
      }) as any;

      return allDataTransaksi.value;
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

  function splitSavedGrants(rows: any[] = []) {
    const layerIds: string[] = [];
    const transaksiIds: string[] = [];
    const preserved: string[] = [];

    for (const row of rows ?? []) {
      const saved = String(row?.nama_table_transaksi ?? row ?? "").trim();
      if (!saved) continue;

      const layer = matchPhysicalTable(allDataLayer.value as any[], saved);
      if (layer) {
        layerIds.push(layer);
        continue;
      }

      const transaksi = matchPhysicalTable(allDataTransaksi.value as any[], saved);
      if (transaksi) {
        transaksiIds.push(transaksi);
        continue;
      }

      if (saved.includes(".")) preserved.push(saved);
    }

    return {
      layer_ids: uniqueStringArray(layerIds),
      transaksi_ids: uniqueStringArray(transaksiIds),
      preserved_grant_ids: uniqueStringArray(preserved),
    };
  }

  function saveErrorMessage(error: any, fallback: string) {
    if (error?.data) return getErrorMessage(error, fallback);
    return error?.message || fallback;
  }

  function toRoleBody(payload: any) {
    const menuIds = uniqueStringArray(payload?.akses_menu ?? payload?.menu_ids ?? []);
    const layerRequested = uniqueStringArray(payload?.layer_ids ?? []);
    const transaksiRequested = uniqueStringArray(payload?.transaksi_ids ?? []);
    const preserved = uniqueStringArray(payload?.preserved_grant_ids ?? []);
    const layerTables = uniqueStringArray(
      layerRequested
        .map((value) => matchPhysicalTable(allDataLayer.value as any[], String(value)))
        .filter(Boolean),
    );
    const transaksiTables = uniqueStringArray(
      transaksiRequested
        .map((value) => matchPhysicalTable(allDataTransaksi.value as any[], String(value)))
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
    if (layerRequested.length !== layerTables.length) {
      throw new Error(
        "Layer data tidak dikenali. Muat ulang daftar layer, lalu simpan lagi.",
      );
    }
    if (transaksiRequested.length !== transaksiTables.length) {
      throw new Error(
        "Tabel transaksi tidak dikenali. Muat ulang daftar transaksi, lalu simpan lagi.",
      );
    }

    return {
      nama: String(payload?.nama ?? "").trim(),
      deskripsi: payload?.deskripsi ?? "",
      akses_menu: menuIds,
      akses_data: tree,
      akses_transaksi: uniqueStringArray([
        ...layerTables,
        ...transaksiTables,
        ...preserved,
      ]),
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
    loadingLayer,
    loadingTransaction,
    errorMessage,
    hasRoles,
    allDataMenu,
    allDataArea,
    allDataPerusahaan,
    allDataEstate,
    allDataAfdeling,
    allDataLayer,
    allDataTransaksi,
    fetchRoles,
    createRole,
    updateRole,
    getExistingAksesByRole,
    splitSavedGrants,
    clearError,
    initDataMenu,
    initDataArea,
    initDataPerusahaan,
    initDataPerusahaanByArea,
    initDataEstate,
    initDataAfdelingByEstate,
    initDataBlokByAfdeling,
    initDataLayer,
    initDataTableTransaksi,
  };
});
