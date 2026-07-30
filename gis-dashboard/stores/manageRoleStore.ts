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
    // console.log(`data payload : ${JSON.stringify(payload)}`);
    loadingCreate.value = true;
    clearError();
    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<RoleItem>(`${baseUrl}/v1/roles/`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: payload,
      });

      // console.log(`hasil create role : ${JSON.stringify(response)}`);

      var idResponseRole = response?.id ?? "";

      if (idResponseRole) {
        await createAksesMenu(idResponseRole, payload.menu_ids);
        await createAksesData(
          idResponseRole,
          payload.perusahaan_ids ?? [],
          payload.estate_ids ?? [],
          payload.area_ids ?? [],
          payload.afdeling_ids ?? [],
          payload,
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

  async function createAksesData(
    roleId: string,
    perusahaanIds: string[] = [],
    estateAkses: string[] = [],
    areaAkses: string[] = [],
    afdelingAkses: string[] = [],
    selectedHierarchy: any = {},
  ) {
    if (!roleId) return;

    const uniqueAreaIds = uniqueStringArray(areaAkses);
    const uniquePerusahaanIds = uniqueStringArray(perusahaanIds);
    const uniqueEstateCodes = uniqueStringArray(estateAkses);
    const uniqueAfdelingCodes = uniqueStringArray(afdelingAkses);

    if (
      uniqueAreaIds.length === 0 ||
      uniquePerusahaanIds.length === 0 ||
      uniqueEstateCodes.length === 0 ||
      uniqueAfdelingCodes.length === 0
    ) {
      return;
    }

    const baseUrl = getApiBaseUrl();

    const normalize = (v: any) => String(v ?? "").trim();

    const areaList = (allDataArea.value ?? []) as any[];
    const perusahaanList = (allDataPerusahaan.value ?? []) as any[];

    const selectedAreaItems = Array.isArray(
      selectedHierarchy?.selected_area_items,
    )
      ? selectedHierarchy.selected_area_items
      : [];
    const selectedPerusahaanItems = Array.isArray(
      selectedHierarchy?.selected_perusahaan_items,
    )
      ? selectedHierarchy.selected_perusahaan_items
      : [];
    const selectedEstateItems = Array.isArray(
      selectedHierarchy?.selected_estate_items,
    )
      ? selectedHierarchy.selected_estate_items
      : [];
    const selectedAfdelingItems = Array.isArray(
      selectedHierarchy?.selected_afdeling_items,
    )
      ? selectedHierarchy.selected_afdeling_items
      : [];

    const selectedAreas =
      selectedAreaItems.length > 0
        ? selectedAreaItems.map((area: any) => ({
            id: normalize(area?.id),
            area_id: normalize(area?.area_id ?? area?.id),
            nama_area: normalize(area?.nama_area ?? area?.nama ?? area?.id),
          }))
        : areaList
            .filter((area: any) => uniqueAreaIds.includes(normalize(area?.id)))
            .map((area) => ({
              id: normalize(area?.id),
              area_id: normalize(area?.area_id ?? area?.id),
              nama_area: normalize(area?.nama_area ?? area?.nama ?? area?.id),
            }));

    const selectedPerusahaan =
      selectedPerusahaanItems.length > 0
        ? selectedPerusahaanItems.map((pt: any) => ({
            id: normalize(pt?.id),
            kode_pt: normalize(pt?.kode_pt ?? pt?.kode ?? pt?.id),
            kode_area: normalize(
              pt?.kode_area ?? pt?.area_id ?? pt?.area?.area_id,
            ),
            nama_pt: normalize(
              pt?.nama_pt ?? pt?.nama_perusahaan ?? pt?.nama ?? pt?.kode_pt,
            ),
          }))
        : perusahaanList
            .filter((pt) => {
              const id = normalize(pt?.id);
              const kodePt = normalize(pt?.kode_pt ?? pt?.kode);
              return (
                uniquePerusahaanIds.includes(id) ||
                uniquePerusahaanIds.includes(kodePt)
              );
            })
            .map((pt) => ({
              id: normalize(pt?.id),
              kode_pt: normalize(pt?.kode_pt ?? pt?.kode ?? pt?.id),
              kode_area: normalize(
                pt?.kode_area ?? pt?.area_id ?? pt?.area?.area_id,
              ),
              nama_pt: normalize(
                pt?.nama_pt ?? pt?.nama_perusahaan ?? pt?.nama ?? pt?.kode_pt,
              ),
            }));

    const selectedEstateMap = new Map<
      string,
      { id: string; kode_est: string; kode_pt: string; nama_estate: string }
    >();
    if (selectedEstateItems.length > 0) {
      selectedEstateItems.forEach((est: any) => {
        const kodeEst = normalize(est?.kode_est ?? est?.id);
        if (!kodeEst) return;
        selectedEstateMap.set(kodeEst, {
          id: normalize(est?.id ?? kodeEst),
          kode_est: kodeEst,
          kode_pt: normalize(est?.kode_pt),
          nama_estate: normalize(est?.nama_estate ?? est?.nama ?? kodeEst),
        });
      });
    }

    const selectedAfdelingMap = new Map<
      string,
      { id: string; kode_afd: string; kode_est: string; nama_afdeling: string }
    >();
    if (selectedAfdelingItems.length > 0) {
      selectedAfdelingItems.forEach((afd: any) => {
        const kodeAfd = normalize(afd?.kode_afd ?? afd?.id);
        const kodeEst = normalize(afd?.kode_est);
        if (!kodeAfd || !kodeEst) return;
        selectedAfdelingMap.set(`${kodeEst}::${kodeAfd}`, {
          id: normalize(afd?.id ?? kodeAfd),
          kode_afd: kodeAfd,
          kode_est: kodeEst,
          nama_afdeling: normalize(
            afd?.nama_afdeling ?? afd?.nama ?? afd?.kode_afd ?? kodeAfd,
          ),
        });
      });
    }

    const selectedAfdelingKeys = new Set(
      uniqueAfdelingCodes
        .map((code) => {
          const normalizedCode = normalize(code);
          if (normalizedCode.includes("::")) return normalizedCode;

          return Array.from(selectedAfdelingMap.keys()).filter((key) =>
            key.endsWith(`::${normalizedCode}`),
          );
        })
        .flat(),
    );

    const areaNodes = selectedAreas.map((area: any) => {
      const areaId = normalize(area?.area_id ?? area?.id);
      const areaName = normalize(area?.nama_area ?? area?.nama ?? areaId);

      return {
        id_area: areaId,
        nama_area: areaName,
        perusahaan: [] as Array<{
          id_perusahaan: string;
          nama_perusahaan: string;
          estate: Array<{
            id_estate: string;
            nama_estate: string;
            afdeling: Array<{
              id_afdeling: string;
              nama_afdeling: string;
            }>;
          }>;
        }>,
      };
    });

    const areaMap = new Map<string, any>();
    areaNodes.forEach((node: any) =>
      areaMap.set(normalize(node.id_area), node),
    );

    for (const perusahaan of selectedPerusahaan) {
      const ptAreaCode = normalize(perusahaan?.kode_area);
      const ptCode = normalize(perusahaan?.kode_pt ?? perusahaan?.id);
      const ptName = normalize(perusahaan?.nama_pt ?? ptCode);

      const areaNode = areaMap.get(ptAreaCode);
      if (!areaNode || !ptCode) continue;

      const estatesResponse = await initDataEstate(ptCode);
      const estates = (estatesResponse ?? []) as any[];

      const estateNodes: Array<{
        id_estate: string;
        nama_estate: string;
        afdeling: Array<{ id_afdeling: string; nama_afdeling: string }>;
      }> = [];

      for (const estate of estates) {
        const kodeEst = normalize(estate?.kode_est ?? estate?.id);
        if (!kodeEst || !uniqueEstateCodes.includes(kodeEst)) continue;

        const selectedEstateMeta = selectedEstateMap.get(kodeEst);

        const afdelingsResponse = await initDataAfdelingByEstate(kodeEst);
        const afdelings = (afdelingsResponse ?? []) as any[];

        const afdelingNodes = afdelings
          .filter((afd) => {
            const kodeAfd = normalize(
              afd?.kode_afd ?? afd?.kode_afdeling ?? afd?.kode ?? afd?.id,
            );
            if (!kodeAfd) return false;

            const selectionKey = `${kodeEst}::${kodeAfd}`;
            if (selectedAfdelingMap.size > 0) {
              return selectedAfdelingMap.has(selectionKey);
            }

            return selectedAfdelingKeys.has(selectionKey);
          })
          .map((afd) => {
            const kodeAfd = normalize(
              afd?.kode_afd ?? afd?.kode_afdeling ?? afd?.kode ?? afd?.id,
            );
            const selectionKey = `${kodeEst}::${kodeAfd}`;

            return {
            id_afdeling: normalize(
              selectedAfdelingMap.get(selectionKey)?.id ??
                afd?.id ??
                afd?.kode_afd ??
                afd?.kode ??
                "",
            ),
            nama_afdeling: normalize(
              afd?.kode_afd ??
                afd?.nama_afdeling ??
                afd?.nama ??
                afd?.kode ??
                "",
            ),
          };
          });

        if (afdelingNodes.length === 0) continue;

        estateNodes.push({
          id_estate: normalize(
            selectedEstateMeta?.id ?? estate?.id ?? estate?.kode_est ?? "",
          ),
          nama_estate: normalize(
            selectedEstateMeta?.nama_estate ??
              estate?.nama_estate ??
              estate?.nama ??
              estate?.kode_est ??
              "",
          ),
          afdeling: afdelingNodes,
        });
      }

      if (estateNodes.length === 0) continue;

      areaNode.perusahaan.push({
        id_perusahaan: normalize(perusahaan?.id ?? perusahaan?.kode_pt ?? ""),
        nama_perusahaan: ptName,
        estate: estateNodes,
      });
    }

    const bodyPayload = areaNodes.filter(
      (area: any) =>
        Array.isArray(area.perusahaan) && area.perusahaan.length > 0,
    );

    if (bodyPayload.length === 0) return;

    // console.log(`hasil body payload : ${JSON.stringify(bodyPayload)}`);

    await $api(`${baseUrl}/v1/akses-data/data/role/${roleId}`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: bodyPayload,
    });
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

  const hasArrayChanged = (arr1: string[], arr2: string[]): boolean => {
    if (arr1.length !== arr2.length) return true;

    const set1 = new Set(arr1);
    const set2 = new Set(arr2);

    if (set1.size !== set2.size) return true;

    for (const item of set1) {
      if (!set2.has(item)) return true;
    }

    return false;
  };

  async function updateRole(roleId: string, payload: any) {
    loadingUpdate.value = true;
    clearError();
    try {
      const baseUrl = getApiBaseUrl();
      const response = await $api<RoleItem>(`${baseUrl}/v1/roles/${roleId}`, {
        method: "PUT",
        headers: getAuthHeaders(),
        body: {
          nama: payload.nama,
          deskripsi: payload.deskripsi,
        },
      });
      // 5. Eksekusi DELETE + CREATE secara efisien (Gunakan Promise.all agar paralel)
      if (roleId) {
        // A. Update Akses Menu jika ada perubahan
        if (payload.menu_ids.length > 0) {
          await createAksesMenu(roleId, payload.menu_ids);
        }

        if (payload.area_ids.length > 0) {
          await createAksesData(
            roleId,
            payload.perusahaan_ids ?? [],
            payload.estate_ids ?? [],
            payload.area_ids ?? [],
            payload.afdeling_ids ?? [],
            payload,
          );
        }

        // C. Update Akses Transaksi jika ada perubahan
        if (payload.transaksi_ids.length > 0) {
          await createAksesTransaksi(roleId, payload.transaksi_ids);
        }
      }
      loadingUpdate.value = false;
      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(error, "Gagal memperbarui role.");
      loadingUpdate.value = false;
      throw error;
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
