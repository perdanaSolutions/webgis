<script setup lang="ts">
defineOptions({
  name: 'DashboardPage',
})

type QuickAccessItem = {
  title: string
  bgClass: string
  iconClass: string
  to: string
  icon: 'report' | 'statistik' | 'block' | 'dokumen' | 'agenda'
}

type AnnouncementItem = {
  date: string
  month: string
  title: string
  description: string
}

type ModuleItem = {
  title: string
  description: string
  bgClass: string
  iconClass: string
  arrowClass: string
  to: string
  icon: 'report' | 'statistik' | 'block' | 'dokumen' | 'agenda' | 'pengguna' | 'notif' | 'modul' | 'pesan' | 'pengumuman' | 'keamanan' | 'bantuan'
}

const dashboardConfig = {
  brandTitle: 'Dashboard',
  brandSubtitle: 'Sistem Informasi Surveyor Tanah',
  greetingTop: 'Selamat Datang Kembali,',
  greetingName: 'Bruno Fernandes 👋',
  greetingDesc: 'Kelola sistem dan akses semua modul dengan mudah dan cepat.',
  quickAccessTitle: 'Akses Cepat',
  quickAccessDesc: 'Modul yang sering Anda gunakan',
  announcementTitle: 'Pengumuman Terbaru',
  announcementSeeAll: 'Lihat Semua',
  moduleTitle: 'Menu Modul',
  profileName: 'Bruno Fernandes',
  profileRole: 'Super Admin',
  searchPlaceholder: 'Cari modul yang ingin diakses...',
  searchButtonLabel: 'Cari',
}

const quickAccessItems: QuickAccessItem[] = [
  { title: 'Report Area', bgClass: 'bg-blue-50', iconClass: 'text-blue-500', to: '/dashboard', icon: 'report' },
  { title: 'Statistik', bgClass: 'bg-orange-50', iconClass: 'text-orange-500', to: '/dashboard', icon: 'statistik' },
  { title: 'Block Profile', bgClass: 'bg-lime-50', iconClass: 'text-lime-500', to: '/map', icon: 'block' },
  { title: 'Dokumen', bgClass: 'bg-violet-50', iconClass: 'text-violet-500', to: '/dashboard', icon: 'dokumen' },
  { title: 'Agenda', bgClass: 'bg-cyan-50', iconClass: 'text-cyan-500', to: '/dashboard', icon: 'agenda' },
]

const announcements: AnnouncementItem[] = [
  {
    date: '30',
    month: 'May',
    title: 'Pemeliharaan Sistem',
    description: 'Sistem akan mengalami pemeliharaan pada 23 Mei 2026 pukul 00.00 - 02.00 WIB.',
  },
  {
    date: '12',
    month: 'May',
    title: 'Pembaruan Fitur',
    description: 'Fitur baru pada modul Laporan telah tersedia. Silahkan cek dan gunakan fitur tersebut.',
  },
]

const moduleItems: ModuleItem[] = [
  {
    title: 'Report Area',
    description: 'Kelola data report area dan hak akses sistem lainnya',
    bgClass: 'bg-blue-50',
    iconClass: 'text-blue-500',
    arrowClass: 'text-blue-500',
    to: '/dashboard',
    icon: 'report',
  },
  {
    title: 'Block Profile',
    description: 'Kelola data block profile dan hak aksesnya',
    bgClass: 'bg-lime-50',
    iconClass: 'text-lime-500',
    arrowClass: 'text-lime-500',
    to: '/map',
    icon: 'block',
  },
  {
    title: 'Dokumen',
    description: 'Kelola dokumen dan file penting',
    bgClass: 'bg-violet-50',
    iconClass: 'text-violet-500',
    arrowClass: 'text-violet-500',
    to: '/dashboard',
    icon: 'dokumen',
  },
  {
    title: 'Statistik',
    description: 'Lihat data statistik dan data ringkasan sistem',
    bgClass: 'bg-orange-50',
    iconClass: 'text-orange-500',
    arrowClass: 'text-orange-500',
    to: '/dashboard',
    icon: 'statistik',
  },
  {
    title: 'Agenda',
    description: 'Kelola agenda dan jadwal kegiatan',
    bgClass: 'bg-cyan-50',
    iconClass: 'text-cyan-500',
    arrowClass: 'text-cyan-500',
    to: '/dashboard',
    icon: 'agenda',
  },
  {
    title: 'Pengguna',
    description: 'Kelola data pengguna dan hak akses sistem',
    bgClass: 'bg-rose-50',
    iconClass: 'text-rose-500',
    arrowClass: 'text-rose-500',
    to: '/dashboard',
    icon: 'pengguna',
  },
  {
    title: 'Notifikasi',
    description: 'Kelola dan lihat notifikasi sistem',
    bgClass: 'bg-blue-50',
    iconClass: 'text-blue-500',
    arrowClass: 'text-blue-500',
    to: '/dashboard',
    icon: 'notif',
  },
  {
    title: 'Modul',
    description: 'Kelola modul aplikasi dan konfigurasi',
    bgClass: 'bg-green-50',
    iconClass: 'text-green-500',
    arrowClass: 'text-green-500',
    to: '/dashboard',
    icon: 'modul',
  },
  {
    title: 'Pesan',
    description: 'Kelola pesan masuk dan keluar',
    bgClass: 'bg-amber-50',
    iconClass: 'text-amber-500',
    arrowClass: 'text-amber-500',
    to: '/dashboard',
    icon: 'pesan',
  },
  {
    title: 'Pengumuman',
    description: 'Kelola informasi dan pengumuman',
    bgClass: 'bg-purple-50',
    iconClass: 'text-purple-500',
    arrowClass: 'text-purple-500',
    to: '/dashboard',
    icon: 'pengumuman',
  },
  {
    title: 'Keamanan',
    description: 'Kelola keamanan dan aktivitas sistem',
    bgClass: 'bg-cyan-50',
    iconClass: 'text-cyan-500',
    arrowClass: 'text-cyan-500',
    to: '/dashboard',
    icon: 'keamanan',
  },
  {
    title: 'Bantuan',
    description: 'Pusat bantuan dan panduan penggunaan',
    bgClass: 'bg-slate-100',
    iconClass: 'text-slate-500',
    arrowClass: 'text-slate-500',
    to: '/dashboard',
    icon: 'bantuan',
  },
]

function iconPath(icon: QuickAccessItem['icon'] | ModuleItem['icon']) {
  switch (icon) {
    case 'report':
      return 'M8 3a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h8.5a1 1 0 0 0 .707-.293l3.5-3.5A1 1 0 0 0 21 16.5V4a1 1 0 0 0-1-1H8Zm2 4h8M10 11h8M10 15h5'
    case 'statistik':
      return 'M4 18h3l3-6 3 4 4-8 3 2M4 6h16v12H4z'
    case 'block':
      return 'M4 8 12 4l8 4v8l-8 4-8-4V8Zm8-4v16M4 8l8 4 8-4'
    case 'dokumen':
      return 'M5 7a2 2 0 0 1 2-2h3l2 2h5a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7Z'
    case 'agenda':
      return 'M7 3v3M17 3v3M4 8h16M6 6h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z'
    case 'pengguna':
      return 'M12 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0'
    case 'notif':
      return 'M10 21h4m-7-4h10l-1-2V11a5 5 0 1 0-10 0v4l-1 2Z'
    case 'modul':
      return 'M4 7h7v7H4V7Zm9 0h7v7h-7V7ZM4 16h7v5H4v-5Zm9 2h7'
    case 'pesan':
      return 'M4 6h16v10H7l-3 3V6Zm4 4h8'
    case 'pengumuman':
      return 'M4 12h3l8-4v8l-8-4H4Zm11 2v4a2 2 0 0 1-2 2'
    case 'keamanan':
      return 'M12 3 5 6v5c0 4.5 2.9 8.6 7 10 4.1-1.4 7-5.5 7-10V6l-7-3Zm0 6v4m0 4h.01'
    case 'bantuan':
      return 'M12 18h.01M9.1 9a3 3 0 1 1 5.8 1c-.5 1-1.7 1.5-2.4 2.1-.6.5-1 1.1-1 1.9'
    default:
      return ''
  }
}
</script>

<template>
  <main class="min-h-screen bg-[#FBFAF8] text-[14px] text-[#2E1F18]">
    <header class="border-b border-[#ECE8E3] bg-white">
      <div class="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-4 lg:px-10">
        <div class="flex items-center gap-3">
          <div class="flex h-14 w-14 items-center justify-center rounded-full border border-[#E8DFD5]">
            <div class="h-10 w-10 rounded-full border-4 border-[#D99B47] border-t-[#4A7B3F]" />
          </div>
          <div>
            <h1 class="text-[20px] font-bold leading-tight">
              {{ dashboardConfig.brandTitle }}
            </h1>
            <p class="text-[14px] text-[#8E8A86]">
              {{ dashboardConfig.brandSubtitle }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button class="flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF1E9] text-[#4D392A]">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
                d="M10 21h4m-7-4h10l-1-2V11a5 5 0 1 0-10 0v4l-1 2Z" />
            </svg>
          </button>

          <button class="flex items-center gap-3 rounded-2xl border border-[#EEE6DE] bg-[#FFF8F2] px-3 py-2">
            <div class="h-11 w-11 overflow-hidden rounded-lg bg-[#D0B59A]" />
            <div class="text-left">
              <p class="text-[16px] font-bold leading-tight">
                {{ dashboardConfig.profileName }}
              </p>
              <p class="text-[14px] text-[#6F645B]">
                {{ dashboardConfig.profileRole }}
              </p>
            </div>
          </button>
        </div>
      </div>
    </header>

    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <section class="grid grid-cols-1 items-center gap-4 lg:grid-cols-[1fr_2fr]">
        <div>
          <p class="text-[14px] text-[#8A817A]">
            {{ dashboardConfig.greetingTop }}
          </p>
          <h2 class="text-[20px] font-bold leading-tight">
            {{ dashboardConfig.greetingName }}
          </h2>
          <p class="text-[14px] text-[#8A817A]">
            {{ dashboardConfig.greetingDesc }}
          </p>
        </div>

        <div class="flex items-center gap-3 rounded-full border border-[#EEE6DE] bg-white p-3 shadow-sm">
          <input type="text" :placeholder="dashboardConfig.searchPlaceholder"
            class="h-11 flex-1 rounded-full px-5 text-[14px] outline-none placeholder:text-[#A6A29D]">
          <button class="rounded-full bg-[#4D392A] px-8 py-3 text-[14px] font-semibold text-white">
            {{ dashboardConfig.searchButtonLabel }}
          </button>
        </div>
      </section>

      <section class="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_1.4fr]">
        <div class="rounded-2xl border border-[#EEE6DE] bg-white p-5">
          <h3 class="text-[16px] font-bold">
            {{ dashboardConfig.quickAccessTitle }}
          </h3>
          <p class="text-[14px] text-[#8A817A]">
            {{ dashboardConfig.quickAccessDesc }}
          </p>

          <div class="mt-5 grid grid-cols-3 gap-4 sm:grid-cols-5">
            <NuxtLink v-for="item in quickAccessItems" :key="`quick-${item.title}`" :to="item.to"
              class="flex flex-col items-center gap-2">
              <div class="flex h-16 w-16 items-center justify-center rounded-2xl" :class="item.bgClass">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor" :class="item.iconClass">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" :d="iconPath(item.icon)" />
                </svg>
              </div>
              <span class="text-center text-[14px] font-semibold">{{ item.title }}</span>
            </NuxtLink>
          </div>
        </div>

        <div class="rounded-2xl bg-[#4D392A] p-5 text-white">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-[16px] font-bold">
              {{ dashboardConfig.announcementTitle }}
            </h3>
            <button class="text-[14px] font-semibold">
              {{ dashboardConfig.announcementSeeAll }}
            </button>
          </div>

          <div class="space-y-3 rounded-xl bg-white p-4 text-[#2E1F18]">
            <div v-for="(item, index) in announcements" :key="`announcement-${item.title}`"
              class="flex items-center gap-4 py-2"
              :class="{ 'border-b border-[#EFE8E1]': index < announcements.length - 1 }">
              <div class="w-14 rounded-xl bg-[#F7F2EC] py-2 text-center">
                <p class="text-[16px] font-bold leading-none">
                  {{ item.date }}
                </p>
                <p class="text-[14px] text-[#8A817A]">
                  {{ item.month }}
                </p>
              </div>
              <div class="flex-1">
                <p class="text-[16px] font-bold">
                  {{ item.title }}
                </p>
                <p class="text-[14px] text-[#7D756E]">
                  {{ item.description }}
                </p>
              </div>
              <span class="text-[16px] text-[#9A928B]">›</span>
            </div>
          </div>
        </div>
      </section>

      <section class="mt-7">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-[20px] font-bold">
            {{ dashboardConfig.moduleTitle }}
          </h3>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <NuxtLink v-for="item in moduleItems" :key="`module-${item.title}`" :to="item.to"
            class="flex items-center gap-4 rounded-2xl border border-[#EEE6DE] bg-white p-4 transition hover:shadow-sm">
            <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl" :class="item.bgClass">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24"
                stroke="currentColor" :class="item.iconClass">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" :d="iconPath(item.icon)" />
              </svg>
            </div>

            <div class="min-w-0 flex-1">
              <p class="truncate text-[16px] font-bold leading-tight">
                {{ item.title }}
              </p>
              <p class="mt-1 line-clamp-2 text-[14px] leading-snug text-[#8A817A]">
                {{ item.description }}
              </p>
            </div>

            <span class="text-[16px] font-bold" :class="item.arrowClass">→</span>
          </NuxtLink>
        </div>
      </section>
    </div>
  </main>
</template>
