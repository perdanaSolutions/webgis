export type MenuBgClass =
  | "bg-blue-50"
  | "bg-orange-50"
  | "bg-lime-50"
  | "bg-violet-50"
  | "bg-cyan-50"
  | "bg-rose-50"
  | "bg-amber-50"
  | "bg-emerald-50"
  | "bg-indigo-50"
  | "bg-fuchsia-50"
  | "bg-slate-100"
  | "bg-[#4D392A]";

export type MenuTextClass =
  | "text-blue-500"
  | "text-orange-500"
  | "text-lime-500"
  | "text-violet-500"
  | "text-cyan-500"
  | "text-rose-500"
  | "text-amber-500"
  | "text-emerald-500"
  | "text-indigo-500"
  | "text-fuchsia-500"
  | "text-slate-600"
  | "text-white"
  | "text-[#4D392A]";

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
  | "bantuan";

export const MENU_BG_OPTIONS: {
  value: MenuBgClass;
  label: string;
  ring: string;
}[] = [
  { value: "bg-blue-50", label: "Biru", ring: "ring-blue-300" },
  { value: "bg-orange-50", label: "Oranye", ring: "ring-orange-300" },
  { value: "bg-lime-50", label: "Hijau Muda", ring: "ring-lime-300" },
  { value: "bg-violet-50", label: "Ungu", ring: "ring-violet-300" },
  { value: "bg-cyan-50", label: "Cyan", ring: "ring-cyan-300" },
  { value: "bg-rose-50", label: "Merah Muda", ring: "ring-rose-300" },
  { value: "bg-amber-50", label: "Kuning", ring: "ring-amber-300" },
  { value: "bg-emerald-50", label: "Hijau", ring: "ring-emerald-300" },
  { value: "bg-indigo-50", label: "Indigo", ring: "ring-indigo-300" },
  { value: "bg-fuchsia-50", label: "Fuchsia", ring: "ring-fuchsia-300" },
  { value: "bg-slate-100", label: "Abu", ring: "ring-slate-300" },
  { value: "bg-[#4D392A]", label: "Coklat", ring: "ring-[#A68B7A]" },
];

export const MENU_TEXT_OPTIONS: {
  value: MenuTextClass;
  label: string;
  swatch: string;
  ring: string;
}[] = [
  { value: "text-blue-500", label: "Biru", swatch: "bg-blue-500", ring: "ring-blue-300" },
  { value: "text-orange-500", label: "Oranye", swatch: "bg-orange-500", ring: "ring-orange-300" },
  { value: "text-lime-500", label: "Hijau Muda", swatch: "bg-lime-500", ring: "ring-lime-300" },
  { value: "text-violet-500", label: "Ungu", swatch: "bg-violet-500", ring: "ring-violet-300" },
  { value: "text-cyan-500", label: "Cyan", swatch: "bg-cyan-500", ring: "ring-cyan-300" },
  { value: "text-rose-500", label: "Merah Muda", swatch: "bg-rose-500", ring: "ring-rose-300" },
  { value: "text-amber-500", label: "Kuning", swatch: "bg-amber-500", ring: "ring-amber-300" },
  { value: "text-emerald-500", label: "Hijau", swatch: "bg-emerald-500", ring: "ring-emerald-300" },
  { value: "text-indigo-500", label: "Indigo", swatch: "bg-indigo-500", ring: "ring-indigo-300" },
  { value: "text-fuchsia-500", label: "Fuchsia", swatch: "bg-fuchsia-500", ring: "ring-fuchsia-300" },
  { value: "text-slate-600", label: "Abu", swatch: "bg-slate-600", ring: "ring-slate-300" },
  { value: "text-white", label: "Putih", swatch: "bg-white border border-slate-200", ring: "ring-slate-300" },
  { value: "text-[#4D392A]", label: "Coklat", swatch: "bg-[#4D392A]", ring: "ring-[#A68B7A]" },
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
    default:
      return "";
  }
}
