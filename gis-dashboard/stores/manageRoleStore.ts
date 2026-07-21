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
    // console.log(`data payload : ${JSON.stringify(payload)}`);
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
        if (!kodeAfd) return;
        selectedAfdelingMap.set(kodeAfd, {
          id: normalize(afd?.id ?? kodeAfd),
          kode_afd: kodeAfd,
          kode_est: normalize(afd?.kode_est),
          nama_afdeling: normalize(
            afd?.nama_afdeling ?? afd?.nama ?? afd?.kode_afd ?? kodeAfd,
          ),
        });
      });
    }

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
            return !!kodeAfd && uniqueAfdelingCodes.includes(kodeAfd);
          })
          .map((afd) => ({
            id_afdeling: normalize(
              selectedAfdelingMap.get(
                normalize(
                  afd?.kode_afd ?? afd?.kode_afdeling ?? afd?.kode ?? afd?.id,
                ),
              )?.id ??
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
          }));

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

    console.log(`hasil body payload : ${JSON.stringify(bodyPayload)}`);

    // await $api(`${baseUrl}/v1/akses-data/data`, {
    //   method: "POST",
    //   headers: getAuthHeaders(),
    //   body: bodyPayload,
    // });
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
        body: {
          nama: payload.nama,
          deskripsi: payload.deskripsi,
        },
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

            await createAksesData(
              roleId,
              [String(perusahaan.id)],
              uniqueStringArray(estateCodes),
              uniqueStringArray(payload?.area_ids ?? []),
              uniqueStringArray(payload?.afdeling_ids ?? []),
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
