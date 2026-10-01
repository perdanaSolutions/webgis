import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { getErrorMessage } from "~/utils/getErrorMessage";
import { menuIconPath } from "~/utils/menuThemeOptions";
import { flattenMenuTree } from "~/utils/menuTree";
import { useAuthStore } from "./authStore";

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

export type ModuleItem = {
  id: string;
  title: string;
  description: string;
  bgClass: string;
  iconClass: string;
  arrowClass: string;
  to: string;
  icon: string;
  level: number;
  parentId: string | null;
  orderPosition: number;
  isFavorite: boolean;
  children: ModuleItem[];
};

function getApiBaseUrl() {
  const config = useRuntimeConfig();
  return config.public.apiBaseUrlPython;
}

export const dashboardStore = defineStore("dashboard", () => {
  const { $api } = useNuxtApp();

  const authStore = useAuthStore();

  const dashboardConfig = {
    brandTitle: "Home",
    brandSubtitle: "Teladan Productivity Technology Science",
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
  const flatModuleItems = computed(() => flattenMenuTree(moduleItems.value));
  const favoriteMenus = computed(() => {
    const user = authStore.user;
    const isSuperAdmin = authStore.isSuperAdmin;
    const allowedIds = isSuperAdmin
      ? null
      : new Set(Array.isArray(user?.akses_menu) ? user.akses_menu : []);

    return flatModuleItems.value
      .filter((item) => {
        if (!item.isFavorite || !item.to) return false;
        if (!allowedIds) return true;
        return allowedIds.has(item.id);
      })
      .slice()
      .sort((a, b) => {
        if (a.orderPosition !== b.orderPosition) {
          return a.orderPosition - b.orderPosition;
        }
        return a.title.localeCompare(b.title);
      });
  });

  function normalizeModule(raw: any): ModuleItem {
    const children = Array.isArray(raw?.children)
      ? raw.children.map(normalizeModule)
      : [];
    return {
      id: String(raw?.id ?? ""),
      title: String(raw?.title ?? ""),
      description: String(raw?.description ?? ""),
      bgClass: String(raw?.bgClass ?? raw?.bg_class ?? "bg-blue-50"),
      iconClass: String(raw?.iconClass ?? raw?.icon_class ?? "text-blue-500"),
      arrowClass: String(
        raw?.arrowClass ?? raw?.arrow_class ?? "text-blue-500",
      ),
      to: String(raw?.to ?? ""),
      icon: String(raw?.icon ?? "report"),
      level: Number(raw?.level ?? 1),
      parentId: raw?.parentId ?? raw?.parent_id ?? null,
      orderPosition: Number(raw?.order_position ?? raw?.orderPosition ?? 0),
      isFavorite: Boolean(raw?.isFavorite ?? raw?.is_favorite ?? false),
      children,
    };
  }

  function filterMenuTree(
    items: ModuleItem[],
    allowedIds: Set<string> | null,
  ): ModuleItem[] {
    return items.flatMap((item) => {
      const children = filterMenuTree(item.children ?? [], allowedIds);
      const selfAllowed = !allowedIds || allowedIds.has(item.id);
      if (!selfAllowed && !children.length) return [];
      return [
        {
          ...item,
          to: selfAllowed ? item.to : "",
          children,
        },
      ];
    });
  }

  async function initDataMenu() {
    loading.value = true;
    errorMessage.value = "";
    try {
      const baseUrl = getApiBaseUrl();

      const response = await $api<any[]>(`${baseUrl}/v1/menus/`, {
        method: "GET",
        headers: {
          accept: "application/json",
          "Content-Type": "application/json",
        },
      });
      const informasiUser = authStore.user;
      const menuTree = Array.isArray(response)
        ? response.map(normalizeModule)
        : [];

      if (authStore.isSuperAdmin) {
        moduleItems.value = menuTree;
      } else if (informasiUser && Array.isArray(informasiUser.akses_menu)) {
        moduleItems.value = filterMenuTree(
          menuTree,
          new Set(informasiUser.akses_menu),
        );
      } else {
        moduleItems.value = [];
      }
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

  function iconPath(icon: string) {
    return menuIconPath(icon);
  }

  return {
    dashboardConfig,
    quickAccessItems,
    announcements,
    loading,
    errorMessage,
    moduleItems,
    flatModuleItems,
    favoriteMenus,
    initDataMenu,
    iconPath,
  };
});
