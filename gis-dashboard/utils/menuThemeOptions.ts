export type MenuBgClass =
  | "bg-blue-50"
  | "bg-sky-50"
  | "bg-cyan-50"
  | "bg-teal-50"
  | "bg-emerald-50"
  | "bg-green-50"
  | "bg-lime-50"
  | "bg-[#638840]"
  | "bg-[#1f3d1a]"
  | "bg-[#e8f0dc]"
  | "bg-yellow-50"
  | "bg-amber-50"
  | "bg-orange-50"
  | "bg-[#d87633]"
  | "bg-[#fff4e8]"
  | "bg-red-50"
  | "bg-rose-50"
  | "bg-pink-50"
  | "bg-fuchsia-50"
  | "bg-purple-50"
  | "bg-violet-50"
  | "bg-indigo-50"
  | "bg-slate-100"
  | "bg-stone-100"
  | "bg-gray-100"
  | "bg-[#f8efe6]"
  | "bg-white"
  | "bg-blue-100"
  | "bg-emerald-100"
  | "bg-rose-100";

export type MenuTextClass =
  | "text-blue-500"
  | "text-blue-700"
  | "text-sky-500"
  | "text-cyan-500"
  | "text-cyan-600"
  | "text-teal-600"
  | "text-emerald-500"
  | "text-emerald-700"
  | "text-green-600"
  | "text-lime-500"
  | "text-lime-600"
  | "text-[#638840]"
  | "text-[#1f3d1a]"
  | "text-yellow-600"
  | "text-amber-500"
  | "text-orange-500"
  | "text-[#d87633]"
  | "text-red-500"
  | "text-rose-500"
  | "text-rose-600"
  | "text-pink-500"
  | "text-fuchsia-500"
  | "text-purple-500"
  | "text-violet-500"
  | "text-indigo-500"
  | "text-slate-600"
  | "text-stone-600"
  | "text-gray-700"
  | "text-black"
  | "text-white";

export type MenuIconKey =
  | "report"
  | "statistik"
  | "block"
  | "dokumen"
  | "agenda"
  | "pengguna"
  | "notif"
  | "modul"
  | "pesan"
  | "pengumuman"
  | "keamanan"
  | "bantuan"
  | "peta"
  | "lokasi"
  | "daun"
  | "panen"
  | "grafik"
  | "gudang"
  | "truk"
  | "cuaca"
  | "kamera"
  | "folder"
  | "setelan"
  | "beranda"
  | "cari"
  | "bintang"
  | "jam"
  | "unduh"
  | "unggah"
  | "saring"
  | "lapisan"
  | "kompas";

export const MENU_BG_OPTIONS: {
  value: MenuBgClass;
  label: string;
}[] = [
  { value: "bg-blue-50", label: "Biru" },
  { value: "bg-blue-100", label: "Biru Lembut" },
  { value: "bg-sky-50", label: "Langit" },
  { value: "bg-cyan-50", label: "Cyan" },
  { value: "bg-teal-50", label: "Teal" },
  { value: "bg-emerald-50", label: "Hijau Emerald" },
  { value: "bg-emerald-100", label: "Hijau Lembut" },
  { value: "bg-green-50", label: "Hijau Segar" },
  { value: "bg-lime-50", label: "Hijau Muda" },
  { value: "bg-[#e8f0dc]", label: "Hijau Pucat" },
  { value: "bg-[#638840]", label: "Hijau Brand" },
  { value: "bg-[#1f3d1a]", label: "Hijau Gelap" },
  { value: "bg-yellow-50", label: "Kuning" },
  { value: "bg-amber-50", label: "Amber" },
  { value: "bg-orange-50", label: "Oranye" },
  { value: "bg-[#d87633]", label: "Oranye Brand" },
  { value: "bg-[#fff4e8]", label: "Persik" },
  { value: "bg-[#f8efe6]", label: "Krem" },
  { value: "bg-red-50", label: "Merah" },
  { value: "bg-rose-50", label: "Merah Muda" },
  { value: "bg-rose-100", label: "Merah Lembut" },
  { value: "bg-pink-50", label: "Pink" },
  { value: "bg-fuchsia-50", label: "Fuchsia" },
  { value: "bg-purple-50", label: "Ungu" },
  { value: "bg-violet-50", label: "Violet" },
  { value: "bg-indigo-50", label: "Indigo" },
  { value: "bg-slate-100", label: "Abu" },
  { value: "bg-stone-100", label: "Batu" },
  { value: "bg-gray-100", label: "Abu Muda" },
  { value: "bg-white", label: "Putih" },
];

export const MENU_TEXT_OPTIONS: {
  value: MenuTextClass;
  label: string;
  swatch: string;
}[] = [
  { value: "text-blue-500", label: "Biru", swatch: "bg-blue-500" },
  { value: "text-blue-700", label: "Biru Tua", swatch: "bg-blue-700" },
  { value: "text-sky-500", label: "Langit", swatch: "bg-sky-500" },
  { value: "text-cyan-500", label: "Cyan", swatch: "bg-cyan-500" },
  { value: "text-cyan-600", label: "Cyan Tua", swatch: "bg-cyan-600" },
  { value: "text-teal-600", label: "Teal", swatch: "bg-teal-600" },
  { value: "text-emerald-500", label: "Hijau Emerald", swatch: "bg-emerald-500" },
  { value: "text-emerald-700", label: "Hijau Tua", swatch: "bg-emerald-700" },
  { value: "text-green-600", label: "Hijau Segar", swatch: "bg-green-600" },
  { value: "text-lime-500", label: "Hijau Muda", swatch: "bg-lime-500" },
  { value: "text-lime-600", label: "Lime", swatch: "bg-lime-600" },
  { value: "text-[#638840]", label: "Hijau Brand", swatch: "bg-[#638840]" },
  { value: "text-[#1f3d1a]", label: "Hijau Gelap", swatch: "bg-[#1f3d1a]" },
  { value: "text-yellow-600", label: "Kuning", swatch: "bg-yellow-600" },
  { value: "text-amber-500", label: "Amber", swatch: "bg-amber-500" },
  { value: "text-orange-500", label: "Oranye", swatch: "bg-orange-500" },
  { value: "text-[#d87633]", label: "Oranye Brand", swatch: "bg-[#d87633]" },
  { value: "text-red-500", label: "Merah", swatch: "bg-red-500" },
  { value: "text-rose-500", label: "Merah Muda", swatch: "bg-rose-500" },
  { value: "text-rose-600", label: "Merah Tua", swatch: "bg-rose-600" },
  { value: "text-pink-500", label: "Pink", swatch: "bg-pink-500" },
  { value: "text-fuchsia-500", label: "Fuchsia", swatch: "bg-fuchsia-500" },
  { value: "text-purple-500", label: "Ungu", swatch: "bg-purple-500" },
  { value: "text-violet-500", label: "Violet", swatch: "bg-violet-500" },
  { value: "text-indigo-500", label: "Indigo", swatch: "bg-indigo-500" },
  { value: "text-slate-600", label: "Abu", swatch: "bg-slate-600" },
  { value: "text-stone-600", label: "Batu", swatch: "bg-stone-600" },
  { value: "text-gray-700", label: "Abu Tua", swatch: "bg-gray-700" },
  { value: "text-black", label: "Hitam", swatch: "bg-black" },
  { value: "text-white", label: "Putih", swatch: "bg-white border border-slate-200" },
];

export const MENU_ICON_OPTIONS: {
  value: MenuIconKey;
  label: string;
}[] = [
  { value: "report", label: "Report" },
  { value: "statistik", label: "Statistik" },
  { value: "block", label: "Block" },
  { value: "dokumen", label: "Dokumen" },
  { value: "agenda", label: "Agenda" },
  { value: "pengguna", label: "Pengguna" },
  { value: "notif", label: "Notifikasi" },
  { value: "modul", label: "Modul" },
  { value: "pesan", label: "Pesan" },
  { value: "pengumuman", label: "Pengumuman" },
  { value: "keamanan", label: "Keamanan" },
  { value: "bantuan", label: "Bantuan" },
  { value: "peta", label: "Peta" },
  { value: "lokasi", label: "Lokasi" },
  { value: "daun", label: "Daun" },
  { value: "panen", label: "Panen" },
  { value: "grafik", label: "Grafik" },
  { value: "gudang", label: "Gudang" },
  { value: "truk", label: "Truk" },
  { value: "cuaca", label: "Cuaca" },
  { value: "kamera", label: "Kamera" },
  { value: "folder", label: "Folder" },
  { value: "setelan", label: "Setelan" },
  { value: "beranda", label: "Beranda" },
  { value: "cari", label: "Cari" },
  { value: "bintang", label: "Bintang" },
  { value: "jam", label: "Jam" },
  { value: "unduh", label: "Unduh" },
  { value: "unggah", label: "Unggah" },
  { value: "saring", label: "Saring" },
  { value: "lapisan", label: "Lapisan" },
  { value: "kompas", label: "Kompas" },
];

export function menuIconPath(icon: string) {
  switch (icon) {
    case "report":
      return "M8 3a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h8.5a1 1 0 0 0 .707-.293l3.5-3.5A1 1 0 0 0 21 16.5V4a1 1 0 0 0-1-1H8Zm2 4h8M10 11h8M10 15h5";
    case "statistik":
      return "M4 18h3l3-6 3 4 4-8 3 2M4 6h16v12H4z";
    case "block":
      return "M4 8 12 4l8 4v8l-8 4-8-4V8Zm8-4v16M4 8l8 4 8-4";
    case "dokumen":
      return "M5 7a2 2 0 0 1 2-2h3l2 2h5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7Z";
    case "agenda":
      return "M7 3v3M17 3v3M4 8h16M6 6h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z";
    case "pengguna":
      return "M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0";
    case "notif":
      return "M10 21h4m-7-4h10l-1-2V11a5 5 0 1 0-10 0v4l-1 2Z";
    case "modul":
      return "M4 7h7v7H4V7Zm9 0h7v7h-7V7ZM4 16h7v5H4v-5Zm9 2h7";
    case "pesan":
      return "M4 6h16v10H7l-3 3V6Zm4 4h8";
    case "pengumuman":
      return "M4 12h3l8-4v8l-8-4H4Zm11 2v4a2 2 0 0 1-2 2";
    case "keamanan":
      return "M12 3 5 6v5c0 4.5 2.9 8.6 7 10 4.1-1.4 7-5.5 7-10V6l-7-3Zm0 6v4m0 4h.01";
    case "bantuan":
      return "M12 18h.01M9.1 9a3 3 0 1 1 5.8 1c-.5 1-1.7 1.5-2.4 2.1-.6.5-1 1.1-1 1.9";
    case "peta":
      return "M9 6.5v8.5m6-6.5v8.5M4.5 7.2 9 5l6 2.5 4.5-2.2v11.5L15 19l-6-2.5-4.5 2.2V7.2Z";
    case "lokasi":
      return "M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11Zm0-8.2a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4Z";
    case "daun":
      return "M5 19c8 0 14-6.2 14-14-8 0-14 6.2-14 14Zm0 0c2.2-4.2 5.4-7.2 9.2-9";
    case "panen":
      return "M7 8h10l-1.2 11H8.2L7 8Zm2.2 0V6.2a2.8 2.8 0 0 1 5.6 0V8";
    case "grafik":
      return "M4 19V5M4 19h16M8 16v-4m4 4V8m4 8v-6";
    case "gudang":
      return "M4 20V10L12 4l8 6v10H4Zm5 0v-6h6v6";
    case "truk":
      return "M3 7h11v8H3V7Zm11 2.5h4.2L21 13v2h-7V9.5ZM7 18.2a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2Zm10.2 0a1.6 1.6 0 1 0 0-3.2 1.6 1.6 0 0 0 0 3.2Z";
    case "cuaca":
      return "M12 3.5v2M12 18.5v2M4.8 4.8l1.4 1.4M17.8 17.8l1.4 1.4M19.2 4.8 17.8 6.2M6.2 17.8 4.8 19.2M3.5 12h2M18.5 12h2M12 16.2a4.2 4.2 0 1 0 0-8.4 4.2 4.2 0 0 0 0 8.4Z";
    case "kamera":
      return "M4 8h3.2L9 6h6l1.8 2H20v10H4V8Zm8 8.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z";
    case "folder":
      return "M3 7.5A2 2 0 0 1 5 5.5h4.2L11 7.5h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-10Z";
    case "setelan":
      return "M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4ZM19.4 13.2a1.5 1.5 0 0 0 .3 1.6l.1.1a1.8 1.8 0 1 1-2.5 2.5l-.1-.1a1.5 1.5 0 0 0-1.6-.3 1.5 1.5 0 0 0-.9 1.4v.2a1.8 1.8 0 1 1-3.6 0v-.2a1.5 1.5 0 0 0-1-1.4 1.5 1.5 0 0 0-1.6.3l-.1.1a1.8 1.8 0 1 1-2.5-2.5l.1-.1a1.5 1.5 0 0 0 .3-1.6 1.5 1.5 0 0 0-1.4-.9H4.6a1.8 1.8 0 1 1 0-3.6h.2a1.5 1.5 0 0 0 1.4-1 1.5 1.5 0 0 0-.3-1.6l-.1-.1a1.8 1.8 0 1 1 2.5-2.5l.1.1a1.5 1.5 0 0 0 1.6.3h.1a1.5 1.5 0 0 0 .9-1.4V4.4a1.8 1.8 0 1 1 3.6 0v.2a1.5 1.5 0 0 0 .9 1.4 1.5 1.5 0 0 0 1.6-.3l.1-.1a1.8 1.8 0 1 1 2.5 2.5l-.1.1a1.5 1.5 0 0 0-.3 1.6v.1a1.5 1.5 0 0 0 1.4.9h.2a1.8 1.8 0 1 1 0 3.6h-.2a1.5 1.5 0 0 0-1.4.9Z";
    case "beranda":
      return "M4 11.2 12 4l8 7.2M6 10.2V20h12V10.2M10 20v-5.5h4V20";
    case "cari":
      return "M11 18.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15ZM20.5 20.5 16.4 16.4";
    case "bintang":
      return "M12 3.4 14.5 8.6l5.7.8-4.1 4 1 5.6L12 16.4 6.9 19l1-5.6-4.1-4 5.7-.8L12 3.4Z";
    case "jam":
      return "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13.5V12l3.2 2";
    case "unduh":
      return "M12 4v10.2m0 0 3.8-3.8M12 14.2 8.2 10.4M5 19.5h14";
    case "unggah":
      return "M12 15.5V5.3m0 0L8.2 9.1M12 5.3l3.8 3.8M5 19.5h14";
    case "saring":
      return "M4 5h16l-6.2 7.2V19l-3.6-1.8v-5L4 5Z";
    case "lapisan":
      return "M12 3.5 3.5 8 12 12.5 20.5 8 12 3.5ZM3.5 12 12 16.5 20.5 12M3.5 16 12 20.5 20.5 16";
    case "kompas":
      return "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm2.6-11.6-1.5 4.1-4.1 1.5 1.5-4.1 4.1-1.5Z";
    default:
      return "";
  }
}
