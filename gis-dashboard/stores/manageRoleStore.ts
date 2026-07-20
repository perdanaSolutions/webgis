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

      allDataMenu.value = response as any;

      return response;
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

  async function initDataTableTransaksi() {
    loadingTransaction.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      // kerangka endpoint transaksi
      const response = await $api<any[]>(`${baseUrl}/v1/database/tables`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      const normalizedData = Array.isArray(response)
        ? response
        : ((response as any)?.data ?? []);

      allDataTransaksi.value = normalizedData as any;

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

  async function createRole(payload: any) {
    loadingCreate.value = true;
    clearError();

    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<RoleItem>(`${baseUrl}/v1/roles/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      var idResponseRole = response?.id ?? "";

      if (idResponseRole) {
        await createAksesMenu(idResponseRole, payload.menu_ids);
        await createAksesPerusahaanEstate(
          idResponseRole,
          payload.perusahaan_ids[0],
          payload.estate_ids,
        );
        await createAksesTransaksi(idResponseRole, payload.transaksi_ids);
      }

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal membuat role.");
      throw error;
    } finally {
      loadingCreate.value = false;
    }
  }

  async function createAksesMenu(roleId: string, menusAkses: string[] = []) {
    if (!roleId || !Array.isArray(menusAkses) || menusAkses.length === 0)
      return;
    createRole;

    const baseUrl = getApiBaseUrl();

    await Promise.all(
      menusAkses
        .filter((menuId) => !!menuId)
        .map((menuId) =>
          $api(`${baseUrl}/v1/akses-data/menu`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: {
              role_id: roleId,
              menu_id: menuId,
            },
          }),
        ),
    );
  }

  async function createAksesPerusahaanEstate(
    roleId: string,
    perusahaanId: string,
    estateAkses: string[] = [],
  ) {
    if (
      !roleId ||
      !perusahaanId ||
      !Array.isArray(estateAkses) ||
      estateAkses.length === 0
    ) {
      return;
    }

    const perusahaanList = (allDataPerusahaan.value ?? []) as any[];
    const selectedPerusahaan = perusahaanList.find(
      (item) => String(item?.id) === String(perusahaanId),
    ) as any;

    const kodePt = String(
      selectedPerusahaan?.kode_pt ??
        selectedPerusahaan?.kode ??
        selectedPerusahaan?.id ??
        "",
    );

    if (!kodePt) return;

    const baseUrl = getApiBaseUrl();

    await Promise.all(
      estateAkses
        .filter((kodeEst) => !!kodeEst)
        .map((kodeEst) =>
          $api(`${baseUrl}/v1/akses-data/data`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: {
              role_id: roleId,
              kode_pt: kodePt,
              kode_est: String(kodeEst),
            },
          }),
        ),
    );
  }

  async function createAksesTransaksi(
    roleId: string,
    transaksiAkses: string[] = [],
  ) {
    if (
      !roleId ||
      !Array.isArray(transaksiAkses) ||
      transaksiAkses.length === 0
    ) {
      return;
    }

    const baseUrl = getApiBaseUrl();

    await Promise.all(
      transaksiAkses
        .filter((namaTable) => !!namaTable)
        .map((namaTable) =>
          $api(`${baseUrl}/v1/akses-data/transaksi`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: {
              role_id: roleId,
              nama_table_transaksi: String(namaTable),
            },
          }),
        ),
    );
  }

  async function getExistingAksesByRole(roleId: string) {
    const baseUrl = getApiBaseUrl();

    const [menuAccess, dataAccess, transaksiAccess] = await Promise.all([
      $api<any[]>(`${baseUrl}/v1/akses-data/menu/role/${roleId}`, {
        method: "GET",
        headers: getAuthHeaders(),
      }),
      $api<any[]>(`${baseUrl}/v1/akses-data/data/role/${roleId}`, {
        method: "GET",
        headers: getAuthHeaders(),
      }),
      $api<any[]>(`${baseUrl}/v1/akses-data/transaksi/role/${roleId}`, {
        method: "GET",
        headers: getAuthHeaders(),
      }),
    ]);

    return {
      menu: Array.isArray(menuAccess) ? menuAccess : [],
      data: Array.isArray(dataAccess) ? dataAccess : [],
      transaksi: Array.isArray(transaksiAccess) ? transaksiAccess : [],
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

  async function deleteAksesMenuByLogIds(logIds: Array<string | number>) {
    if (!Array.isArray(logIds) || logIds.length === 0) return;
    const baseUrl = getApiBaseUrl();

    await Promise.all(
      logIds.map((logId) =>
        $api(`${baseUrl}/v1/akses-data/menu/${logId}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        }),
      ),
    );
  }

  async function deleteAksesDataByLogIds(logIds: Array<string | number>) {
    if (!Array.isArray(logIds) || logIds.length === 0) return;
    const baseUrl = getApiBaseUrl();

    await Promise.all(
      logIds.map((logId) =>
        $api(`${baseUrl}/v1/akses-data/data/${logId}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        }),
      ),
    );
  }

  async function deleteAksesTransaksiByLogIds(logIds: Array<string | number>) {
    if (!Array.isArray(logIds) || logIds.length === 0) return;
    const baseUrl = getApiBaseUrl();

    await Promise.all(
      logIds.map((logId) =>
        $api(`${baseUrl}/v1/akses-data/transaksi/${logId}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        }),
      ),
    );
  }

  async function updateRole(roleId: string, payload: any) {
    loadingUpdate.value = true;
    clearError();
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api<RoleItem>(`${baseUrl}/v1/roles/${roleId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: payload,
      });

      const existing = await getExistingAksesByRole(roleId);

      const selectedMenuIds = uniqueStringArray(payload?.menu_ids ?? []);
      const existingMenuIds = uniqueStringArray(
        (existing.menu ?? []).map((item: any) => item?.menu_id),
      );

      const existingDataKeys = uniqueStringArray(
        (existing.data ?? []).map(
          (item: any) =>
            `${String(item?.kode_pt ?? "")}|${String(item?.kode_est ?? "")}`,
        ),
      );

      const perusahaanList = (allDataPerusahaan.value ?? []) as any[];
      const selectedPerusahaan = perusahaanList.find(
        (item) =>
          String(item?.id) === String(payload?.perusahaan_ids?.[0] ?? ""),
      ) as any;

      const selectedKodePt = String(
        selectedPerusahaan?.kode_pt ??
          selectedPerusahaan?.kode ??
          selectedPerusahaan?.id ??
          "",
      );

      const selectedEstateCodes = uniqueStringArray(payload?.estate_ids ?? []);
      const selectedDataKeys = uniqueStringArray(
        selectedEstateCodes.map(
          (kodeEst) => `${selectedKodePt}|${String(kodeEst)}`,
        ),
      );

      const selectedTransaksiNames = uniqueStringArray(
        payload?.transaksi_ids ?? [],
      );
      const existingTransaksiNames = uniqueStringArray(
        (existing.transaksi ?? []).map(
          (item: any) => item?.nama_table_transaksi,
        ),
      );

      const menuToDelete = (existing.menu ?? []).filter(
        (item: any) => !selectedMenuIds.includes(String(item?.menu_id ?? "")),
      );
      const menuToCreate = selectedMenuIds.filter(
        (menuId) => !existingMenuIds.includes(menuId),
      );

      const dataToDelete = (existing.data ?? []).filter((item: any) => {
        const key = `${String(item?.kode_pt ?? "")}|${String(item?.kode_est ?? "")}`;
        return !selectedDataKeys.includes(key);
      });
      const dataToCreate = selectedDataKeys.filter(
        (key) => !existingDataKeys.includes(key),
      );

      const transaksiToDelete = (existing.transaksi ?? []).filter(
        (item: any) =>
          !selectedTransaksiNames.includes(
            String(item?.nama_table_transaksi ?? ""),
          ),
      );
      const transaksiToCreate = selectedTransaksiNames.filter(
        (name) => !existingTransaksiNames.includes(name),
      );

      await deleteAksesMenuByLogIds(
        menuToDelete.map((item: any) => item?.id).filter((id: any) => !!id),
      );
      await deleteAksesDataByLogIds(
        dataToDelete.map((item: any) => item?.id).filter((id: any) => !!id),
      );
      await deleteAksesTransaksiByLogIds(
        transaksiToDelete
          .map((item: any) => item?.id)
          .filter((id: any) => !!id),
      );

      if (menuToCreate.length > 0) {
        await createAksesMenu(roleId, menuToCreate);
      }

      if (dataToCreate.length > 0) {
        const groupedByPt = dataToCreate.reduce(
          (acc: Record<string, string[]>, key) => {
            const [kodePt, kodeEst] = String(key).split("|");
            if (!kodePt || !kodeEst) return acc;
            if (!acc[kodePt]) acc[kodePt] = [];
            acc[kodePt].push(kodeEst);
            return acc;
          },
          {},
        );

        await Promise.all(
          Object.entries(groupedByPt).map(async ([kodePt, estateCodes]) => {
            const perusahaan = perusahaanList.find((item: any) => {
              const itemKodePt = String(
                item?.kode_pt ?? item?.kode ?? item?.id ?? "",
              );
              return itemKodePt === String(kodePt);
            });

            if (!perusahaan?.id) return;

            await createAksesPerusahaanEstate(
              roleId,
              String(perusahaan.id),
              uniqueStringArray(estateCodes),
            );
          }),
        );
      }

      if (transaksiToCreate.length > 0) {
        await createAksesTransaksi(roleId, transaksiToCreate);
      }

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
