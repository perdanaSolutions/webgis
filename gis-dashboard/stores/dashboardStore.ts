import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";

type QuickAccessItem = {
  title: string;
  bgClass: string;
  iconClass: string;
  to: string;
  icon: "report" | "statistik" | "block" | "dokumen" | "agenda";
};

type AnnouncementItem = {
  date: string;
  month: string;
  title: string;
  description: string;
};

type ModuleItem = {
  title: string;
  description: string;
  bgClass: string;
  iconClass: string;
  arrowClass: string;
  to: string;
  icon:
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
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const dashboardStore = defineStore("dashboard", () => {
  const { $api } = useNuxtApp();

  const dashboardConfig = {
    brandTitle: "Dashboard",
    brandSubtitle: "Sistem Informasi Surveyor Tanah",
    greetingTop: "Selamat Datang Kembali,",
    greetingName: "Bruno Fernandes 👋",
    greetingDesc: "Kelola sistem dan akses semua modul dengan mudah dan cepat.",
    quickAccessTitle: "Akses Cepat",
    quickAccessDesc: "Modul yang sering Anda gunakan",
    announcementTitle: "Pengumuman Terbaru",
    announcementSeeAll: "Lihat Semua",
    moduleTitle: "Menu Modul",
    profileName: "Bruno Fernandes",
    profileRole: "Super Admin",
    searchPlaceholder: "Cari modul yang ingin diakses...",
    searchButtonLabel: "Cari",
  };

  const quickAccessItems: QuickAccessItem[] = [
    {
      title: "Report Area",
      bgClass: "bg-blue-50",
      iconClass: "text-blue-500",
      to: "/dashboard",
      icon: "report",
    },
    {
      title: "Statistik",
      bgClass: "bg-orange-50",
      iconClass: "text-orange-500",
      to: "/dashboard",
      icon: "statistik",
    },
    {
      title: "Block Profile",
      bgClass: "bg-lime-50",
      iconClass: "text-lime-500",
      to: "/map",
      icon: "block",
    },
    {
      title: "Dokumen",
      bgClass: "bg-violet-50",
      iconClass: "text-violet-500",
      to: "/dashboard",
      icon: "dokumen",
    },
    {
      title: "Agenda",
      bgClass: "bg-cyan-50",
      iconClass: "text-cyan-500",
      to: "/dashboard",
      icon: "agenda",
    },
  ];

  const announcements: AnnouncementItem[] = [
    {
      date: "30",
      month: "May",
      title: "Pemeliharaan Sistem",
      description:
        "Sistem akan mengalami pemeliharaan pada 23 Mei 2026 pukul 00.00 - 02.00 WIB.",
    },
    {
      date: "12",
      month: "May",
      title: "Pembaruan Fitur",
      description:
        "Fitur baru pada modul Laporan telah tersedia. Silahkan cek dan gunakan fitur tersebut.",
    },
  ];

  const loading = ref(false);
  const errorMessage = ref("");
  const moduleItems = ref<ModuleItem[]>([]);

  async function initDataMenu() {
    loading.value = true;
    errorMessage.value = "";
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api<ModuleItem[]>(`${baseUrl}/v1/menus/`, {
        method: "GET",
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
      });

      moduleItems.value = response;

      return response;
    } catch (error: any) {
      errorMessage.value = getErrorMessage(
        error,
        "Terjadi kesalahan saat memuat data menu. Silakan coba lagi.",
      );
      throw error;
    } finally {
      loading.value = false;
    }
  }

  function iconPath(icon: QuickAccessItem["icon"] | ModuleItem["icon"]) {
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

  return {
    dashboardConfig,
    quickAccessItems,
    announcements,
    loading,
    errorMessage,
    moduleItems,
    initDataMenu,
    iconPath,
  };
});
