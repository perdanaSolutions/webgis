/** Katalog upload transaksi (hanya file Excel .xlsx/.xls). Nama kolom mengikuti header yang diterima backend. */

/** Tidak dibatasi di browser; file besar dipecah per part lalu antre ke worker. */
export const TRX_UPLOAD_MAX_BYTES = Number.POSITIVE_INFINITY;

export type TrxKindId = "areal-statement" | "rotasi-pusingan";
export type TrxFileMode = "excel";
export type CellScalar = string | number | boolean | null;

/** Hanya file Excel yang boleh diupload di halaman /transaksi. */
export const TRX_ALLOWED_EXTENSIONS = [".xlsx", ".xls"] as const;
export const TRX_FILE_ACCEPT = ".xlsx,.xls,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
export const TRX_UNSUPPORTED_FILE_MESSAGE =
  "Format file tidak didukung. Hanya file Excel (.xlsx atau .xls) yang bisa diupload.";

export function isTrxExcelFile(name: string | null | undefined): boolean {
  const lower = String(name ?? "").trim().toLowerCase();
  return TRX_ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export type TrxColumnGroup = {
  label: string;
  names: string[];
};

export type TrxKindSpec = {
  id: TrxKindId;
  label: string;
  description: string;
  excelFilename: string;
  endpoints: {
    analyze: string;
    excel: string;
  };
  /** Kode `layer` untuk POST /v1/upload-jobs (sama dengan id jenis). */
  uploadJobLayer: TrxKindId;
  columns: string[];
  requiredGroups: TrxColumnGroup[];
  example: Record<string, CellScalar>;
  rules: string[];
};

const PERIOD_BY_DATE: TrxColumnGroup = {
  label: "Periode lewat Tanggal (YYYY-MM-DD), bila Year/Month atau Bulan kosong",
  names: ["Tanggal", "tanggal", "Date"],
};

export const TRX_KINDS: TrxKindSpec[] = [
  {
    id: "areal-statement",
    label: "Areal Statement",
    description: "Upsert data areal per blok dan bulan. Blok yang tidak ada di file tidak dihapus.",
    excelFilename: "template-areal-statement.xlsx",
    endpoints: {
      analyze: "/v1/areal-statement/import-excel/analyze",
      excel: "/v1/areal-statement/import-excel",
    },
    uploadJobLayer: "areal-statement",
    columns: [
      "Year",
      "Month",
      "Group",
      "AreaCode",
      "CompanyCode",
      "Estate",
      "UnitCode",
      "EstateShortName",
      "DivisionCode",
      "KodeBlok",
      "TipeBlok",
      "StatusTanam",
      "TahunTanam",
      "BulanTanam",
      "LuasTanam",
      "LuasTanah",
      "TotalPokok",
      "SPH",
      "JenisBibit",
      "JenisTopografi",
      "TanahDatar",
      "Berbukit",
      "Gelombang",
      "Curam",
      "JenisTanah",
    ],
    requiredGroups: [
      { label: "Tahun (Year)", names: ["Year", "Tahun", "tahun", "Periode"] },
      { label: "Bulan (Month)", names: ["Month", "Bulan", "bulan"] },
      PERIOD_BY_DATE,
      { label: "AreaCode", names: ["AreaCode", "Area", "KodeArea"] },
      { label: "StatusTanam", names: ["StatusTanam", "Status Tanam", "status_tanam"] },
      { label: "Kode blok", names: ["KodeBlok", "Kode Blok", "Blok", "kode_blok", "BlockCode"] },
      { label: "Afdeling (DivisionCode)", names: ["DivisionCode", "Divisi", "Afdeling", "KodeAfdeling", "Kode Afdeling", "Afd"] },
      { label: "Estate", names: ["UnitCode", "EstateCode", "KodeEstate", "Kode Estate", "EstID", "EstateShortName", "Estate"] },
    ],
    example: {
      Year: 2026,
      Month: 1,
      Group: "TPA",
      AreaCode: "KUTIM2",
      CompanyCode: 1500,
      Estate: "Long Mesangat Estate",
      UnitCode: "E013",
      EstateShortName: "LME",
      DivisionCode: "AFDI04",
      KodeBlok: "H033",
      TipeBlok: "Inti",
      StatusTanam: "TM",
      TahunTanam: 2007,
      BulanTanam: "Sep",
      LuasTanam: 41.38,
      LuasTanah: 42.16,
      TotalPokok: 5726,
      SPH: 138.38,
      JenisBibit: "Socfin",
      JenisTopografi: "DATAR",
      TanahDatar: 100,
      Berbukit: 0,
      Gelombang: 0,
      Curam: 0,
      JenisTanah: "TANAH MINERAL",
    },
    rules: [
      "File .xlsx atau .xls tanpa batas ukuran di browser; server menerima per part lewat antrian. Yang dibaca hanya sheet pertama (sheet Data pada template). Baris pertama harus nama kolom.",
      "Setiap baris dicocokkan ke master dari estate + afdeling (DivisionCode) + blok (KodeBlok). Ketiganya harus ada dan cocok persis. Sistem tidak menebak.",
      "Wajib diisi: Year, Month, AreaCode, StatusTanam, KodeBlok, DivisionCode, dan satu penanda estate (UnitCode, EstateShortName, atau Estate). StatusTanam kosong membuat baris ditolak.",
      "Nama alternatif yang diterima antara lain Tahun/Bulan untuk Year/Month. Periode dari kolom Tanggal (YYYY-MM-DD) juga dikenali bila Year dan Month tidak ada.",
      "Baris yang ditolak (blok tidak ketemu, nilai negatif, kolom wajib kosong) masuk karantina. Baris yang benar tetap masuk. Error sistem di tengah proses tidak menyimpan data setengah-setengah.",
      "File boleh diunggah ulang. Pola upsert per blok dan bulan: data lama diperbarui, data baru ditambahkan, isi yang sama persis tidak ditulis ulang. Blok yang tidak ada di file tidak dihapus.",
      "Baris ganda untuk blok dan bulan yang sama: baris terakhir yang dipakai.",
      "TahunTanam harus 1900–2100. Nilai 0 atau kosong berarti belum ditanam. BulanTanam boleh angka atau nama bulan (Jan, Januari).",
      "TanahDatar, Berbukit, Gelombang, dan Curam masing-masing 0–100, dan jumlahnya tidak boleh lebih dari 100.",
      "LuasTanam, LuasTanah, TotalPokok, dan SPH tidak boleh negatif.",
      "JenisBibit boleh lebih dari satu, dipisah koma, /, ;, +, &, atau kata \"dan\".",
      "CompanyCode yang berbeda dari PT blok hanya peringatan; baris tetap masuk (peringatan_company_code).",
      "Group (TPA/SGA) hanya peringatan. Grup resmi PT berasal dari GeoJSON batas blok, jadi import ini tidak mengubahnya (peringatan_grup).",
      "AreaCode disimpan sebagai riwayat area bulan itu. Bila berbeda dari area estate di master, baris tetap masuk dan dilaporkan di peringatan_area. Area estate di master tidak diubah, kecuali estate yang belum punya area: area itu diisi dari periode terbaru di file.",
      "TipeBlok (Inti/Plasma) ikut memperbarui tipe blok di master.",
      "Nilai referensi baru (AreaCode, status tanam, jenis tanah, topografi, bibit, atau tipe blok) dibuat otomatis. Periksa nilai_referensi_baru agar tidak ada salah ketik.",
      "Penanda kosong seperti (blank), (Blanks), n/a, null, none, nan, -, dan -- dianggap sel kosong.",
    ],
  },
  {
    id: "rotasi-pusingan",
    label: "Rotasi & Pusingan",
    description: "Upsert rotasi dan pusingan per blok dan bulan. Blok yang tidak ada di file tidak dihapus.",
    excelFilename: "template-rotasi-pusingan.xlsx",
    endpoints: {
      analyze: "/v1/trx-rotasi-pusingan/import-rotasi-pusingan/analyze",
      excel: "/v1/trx-rotasi-pusingan/import-rotasi-pusingan",
    },
    uploadJobLayer: "rotasi-pusingan",
    columns: [
      "Periode",
      "Area",
      "PT",
      "Estate",
      "Afdeling",
      "Blok",
      "Luas",
      "Pokok",
      "Rotasi",
      "Pusingan",
      "Status Pusingan",
      "Bulan",
      "Tanggal",
    ],
    requiredGroups: [
      { label: "Tahun (Periode)", names: ["Periode", "Year", "Tahun", "tahun"] },
      { label: "Bulan", names: ["Bulan", "Month", "bulan"] },
      PERIOD_BY_DATE,
      { label: "Blok", names: ["KodeBlok", "Kode Blok", "Blok", "kode_blok", "BlockCode"] },
      { label: "Afdeling", names: ["DivisionCode", "Divisi", "Afdeling", "KodeAfdeling", "Kode Afdeling", "Afd"] },
      { label: "Estate", names: ["UnitCode", "EstateCode", "KodeEstate", "Kode Estate", "EstID", "EstateShortName", "Estate"] },
    ],
    example: {
      Periode: 2026,
      Area: "BERAU",
      PT: "PT. INTI ENERGI KALTIM",
      Estate: "Ampen Medang Estate",
      Afdeling: "AFDI01",
      Blok: "C012",
      Luas: 26.55,
      Pokok: 3709,
      Rotasi: 4,
      Pusingan: 3,
      "Status Pusingan": "Normal",
      Bulan: "Jan",
      Tanggal: "2026-01-01",
    },
    rules: [
      "File .xlsx atau .xls tanpa batas ukuran di browser; server menerima per part lewat antrian. Yang dibaca hanya sheet pertama (sheet Data pada template). Baris pertama harus nama kolom.",
      "Setiap baris dicocokkan ke master dari estate + afdeling + blok. Ketiganya harus ada dan cocok persis. Sistem tidak menebak.",
      "Wajib diisi: tahun (kolom Periode), bulan, Blok, Afdeling, dan estate. Bulan boleh angka atau nama (1, Jan, Januari). Bila kolom Bulan kosong, bulan diambil dari kolom Tanggal (YYYY-MM-DD).",
      "Estate dikenali dari kode estate (UnitCode), singkatan (EstateShortName), atau nama estate.",
      "Area dan PT boleh ada di file tetapi tidak disimpan. Kolom BulanID (jika ada) juga diabaikan.",
      "Luas, Pokok, Rotasi, dan Pusingan tidak boleh negatif dan boleh kosong.",
      "Status Pusingan yang belum terdaftar dibuat otomatis. Periksa nilai_referensi_baru agar tidak ada salah ketik.",
      "Baris yang ditolak masuk karantina. Baris yang benar tetap masuk. Error sistem di tengah proses tidak menyimpan data setengah-setengah.",
      "File boleh diunggah ulang. Pola upsert per blok dan bulan: data lama diperbarui, data baru ditambahkan, isi yang sama persis tidak ditulis ulang. Blok yang tidak ada di file tidak dihapus.",
      "Baris ganda untuk blok dan bulan yang sama: baris terakhir yang dipakai.",
      "Penanda kosong seperti (blank), (Blanks), n/a, null, none, nan, -, dan -- dianggap sel kosong.",
    ],
  },
];

const BLANK_MARKERS = new Set([
  "",
  "(blank)",
  "(blanks)",
  "-",
  "--",
  "n/a",
  "#n/a",
  "null",
  "none",
  "nan",
]);

export function findTrxKind(id: string): TrxKindSpec {
  const match = TRX_KINDS.find((item) => item.id === id);
  if (match) return match;
  const fallback = TRX_KINDS[0];
  if (!fallback) throw new Error("Katalog jenis transaksi kosong.");
  return fallback;
}

export function normalizeCell(value: unknown): string {
  if (value == null) return "";
  const text = String(value).trim();
  if (BLANK_MARKERS.has(text.toLowerCase())) return "";
  return text;
}

export function fileModeFromName(name: string): TrxFileMode | null {
  return isTrxExcelFile(name) ? "excel" : null;
}

function isPeriodGroup(group: TrxColumnGroup) {
  return group === PERIOD_BY_DATE || group.names.some((name) =>
    name === "Year" || name === "Periode" || name === "Month" || name === "Bulan",
  );
}

/** Kelompok wajib yang header-nya belum ada. Periode cukup tahun + bulan, atau kolom Tanggal. */
/** Kunci header longgar: tanpa beda huruf besar/kecil, spasi, dan garis bawah ("Kode Blok" == "kodeblok"). */
export function headerKey(name: string): string {
  return String(name ?? "").replace(/[\s_]+/g, "").toLowerCase();
}

export function missingHeaderGroups(headers: string[], spec: TrxKindSpec) {
  const present = new Set(headers.map(headerKey));
  const has = (group: TrxColumnGroup) => group.names.some((name) => present.has(headerKey(name)));
  const year = spec.requiredGroups.find((group) => group.names.includes("Year") || group.names.includes("Periode"));
  const month = spec.requiredGroups.find((group) => group.names.includes("Month") || group.names.includes("Bulan"));
  const hasPeriod = Boolean((year && month && has(year) && has(month)) || has(PERIOD_BY_DATE));
  const missing = spec.requiredGroups.filter((group) => !isPeriodGroup(group) && !has(group));
  if (!hasPeriod) {
    missing.unshift({ label: "Periode (Year + Month, atau Tanggal)", names: [] });
  }
  return missing;
}
