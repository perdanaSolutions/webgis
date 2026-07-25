// --- 1. Interface Data Sumber (Input API) ---
export interface SourceAfdeling {
  id_afdeling: string;
  nama_afdeling: string;
}

export interface SourceEstate {
  id_estate: string;
  nama_estate: string;
  afdeling?: SourceAfdeling[];
}

export interface SourcePerusahaan {
  id_perusahaan: string;
  nama_perusahaan: string;
  estate?: SourceEstate[];
}

export interface SourceArea {
  id_area: string;
  nama_area: string;
  perusahaan?: SourcePerusahaan[];
}

// --- 2. Interface Data Target (Output Form) ---
export interface SelectedAreaItem {
  id: string;
  area_id: string;
  nama_area: string;
}

export interface SelectedPerusahaanItem {
  id: string;
  kode_pt: string;
  kode_area: string;
  nama_pt: string;
}

export interface SelectedEstateItem {
  id: string;
  kode_est: string;
  kode_pt: string;
  nama_estate: string;
}

export interface SelectedAfdelingItem {
  id: string;
  kode_afd: string;
  kode_est: string;
  nama_afdeling: string;
}

export interface FormDataState {
  nama: string;
  deskripsi: string;
  menu_ids: string[];
  area_ids: string[];
  perusahaan_ids: string[];
  estate_ids: string[];
  afdeling_ids: string[];
  transaksi_ids: string[];
  selected_area_items: SelectedAreaItem[];
  selected_perusahaan_items: SelectedPerusahaanItem[];
  selected_estate_items: SelectedEstateItem[];
  selected_afdeling_items: SelectedAfdelingItem[];
}

export interface ExtraInfo {
  nama?: string;
  deskripsi?: string;
  menu_ids?: string[];
  transaksi_ids?: string[];
}

// --- 3. Dictionary / Mapping Rujukan (Optional / Custom Mapping) ---
// Jika ID area numerik (misal: "87", "88") tidak ada di data input,
// kita sediakan map default-nya:
const AREA_ID_MAP: Record<string, string> = {
  AR_BERAU: "87",
  AR_KUTIM2: "88",
};

// Mapping nama human-readable untuk Estate jika di-API berupa kode ID
const ESTATE_NAME_MAP: Record<string, string> = {
  PT_TANJUNG_BUYU_PERKASA_PLANTATION_E004: "Biatan Estate",
  PT_TANJUNG_BUYU_PERKASA_PLANTATION_E001: "Talisayan 1 Estate",
  PT_TELEN_PRIMA_SAWIT_E014: "Muara Bengkal 1 Estate",
};

// --- 4. Fungsi Helper ---
function formatPtName(kodePt: string): string {
  // Mengubah "PT_TANJUNG_BUYU_PERKASA_PLANTATION" -> "PT. TANJUNG BUYU PERKASA PLANTATION"
  return kodePt.replace(/^PT_/, "PT. ").replace(/_/g, " ");
}

// --- 5. Fungsi Logika Konversi ---
export function transformDataToForm(
  sourceData: SourceArea[],
  extraInfo: ExtraInfo = {},
): FormDataState {
  const estateIdsSet = new Set<string>();
  const afdelingIdsSet = new Set<string>();

  const selectedAreaItems: SelectedAreaItem[] = [];
  const selectedPerusahaanItems: SelectedPerusahaanItem[] = [];
  const selectedEstateItems: SelectedEstateItem[] = [];
  const selectedAfdelingItems: SelectedAfdelingItem[] = [];

  sourceData.forEach((area) => {
    // 1. Olah Area
    // Menggunakan ID numerik dari map jika ada, atau fallback ke id_area asal
    const mappedAreaId = AREA_ID_MAP[area.id_area] || area.id_area;
    const cleanedAreaName = area.nama_area.replace(/^AR_/, "");

    if (!selectedAreaItems.some((item) => item.area_id === area.id_area)) {
      selectedAreaItems.push({
        id: mappedAreaId,
        area_id: area.id_area,
        nama_area: cleanedAreaName,
      });
    }

    if (Array.isArray(area.perusahaan)) {
      area.perusahaan.forEach((pt) => {
        // 2. Olah Perusahaan
        // Deteksi kode_pt asli dari ID estate (misal: "PT_TANJUNG_BUYU_PERKASA_PLANTATION")
        let kodePt = pt.nama_perusahaan;
        const sampleEstateId = pt.estate?.[0]?.id_estate;

        if (sampleEstateId) {
          kodePt = sampleEstateId.replace(/_E\d+.*$/, "");
        }

        if (
          !selectedPerusahaanItems.some((item) => item.id === pt.id_perusahaan)
        ) {
          selectedPerusahaanItems.push({
            id: pt.id_perusahaan,
            kode_pt: kodePt,
            kode_area: area.id_area,
            nama_pt: formatPtName(kodePt),
          });
        }

        if (Array.isArray(pt.estate)) {
          pt.estate.forEach((est) => {
            // 3. Olah Estate
            // Ekstrak kode_est (contoh: "E004" dari "PT_..._E004")
            const kodeEst = est.id_estate.split("_").pop() || "";

            if (kodeEst) {
              estateIdsSet.add(kodeEst);
            }

            if (
              !selectedEstateItems.some((item) => item.id === est.id_estate)
            ) {
              selectedEstateItems.push({
                id: est.id_estate,
                kode_est: kodeEst,
                kode_pt: "",
                nama_estate: ESTATE_NAME_MAP[est.id_estate] || est.nama_estate,
              });
            }

            if (Array.isArray(est.afdeling)) {
              est.afdeling.forEach((afd) => {
                // 4. Olah Afdeling
                // Ekstrak kode_afd (contoh: "AFDI01" dari "PT_..._AFDI01")
                const kodeAfd = afd.id_afdeling.split("_").pop() || "";

                if (kodeAfd) {
                  afdelingIdsSet.add(kodeAfd);
                }

                if (
                  !selectedAfdelingItems.some(
                    (item) => item.id === afd.id_afdeling,
                  )
                ) {
                  selectedAfdelingItems.push({
                    id: afd.id_afdeling,
                    kode_afd: kodeAfd,
                    kode_est: kodeEst,
                    nama_afdeling: kodeAfd,
                  });
                }
              });
            }
          });
        }
      });
    }
  });

  return {
    nama: extraInfo.nama ?? "",
    deskripsi: extraInfo.deskripsi ?? "",
    menu_ids: extraInfo.menu_ids ?? [],
    area_ids: selectedAreaItems.map((item) => item.id),
    perusahaan_ids: selectedPerusahaanItems.map((item) => item.id),
    estate_ids: Array.from(estateIdsSet),
    afdeling_ids: Array.from(afdelingIdsSet),
    transaksi_ids: extraInfo.transaksi_ids ?? [],
    selected_area_items: selectedAreaItems,
    selected_perusahaan_items: selectedPerusahaanItems,
    selected_estate_items: selectedEstateItems,
    selected_afdeling_items: selectedAfdelingItems,
  };
}
