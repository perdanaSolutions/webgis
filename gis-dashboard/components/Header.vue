<script setup lang="ts">
import { onMounted, computed, ref, onUnmounted } from 'vue'
import { useAuthStore } from '~/stores/authStore'
import { dashboardStore } from '~/stores/dashboardStore'

const authStore = useAuthStore()
const dashboardService = dashboardStore()
const informasiUser = computed(() => authStore.user)

onMounted(async () => {
  if (!authStore.token) {
    await navigateTo('/login')
  }
  if (!dashboardService.moduleItems.length) {
    dashboardService.initDataMenu()
  }
})

const isMenuOpen = ref(false)
const isQuickMenuOpen = ref(false)
const isSidebarOpen = ref(false)
const menuItems = ref([
  { label: 'Profil Saya', info: 'Lihat detail akun', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z', action: () => navigateTo('/profile') },
  // { label: 'Pengaturan', info: 'Konfigurasi sistem', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z', action: () => navigateTo('/settings') },
  { label: 'Keluar', info: 'Log out dari aplikasi', icon: 'M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1', action: () => logout() },
])


// 1. Definisikan interface untuk Props
interface HeaderProps {
  brandTitle?: string
  brandSubtitle?: string
  profileName?: string
  profileRole?: string
}

// 2. Gunakan withDefaults untuk memberikan nilai default jika props tidak diisi oleh parent
const props = withDefaults(defineProps<HeaderProps>(), {
  brandTitle: 'Plantation Admin',
  brandSubtitle: 'Sistem Informasi Kelapa Sawit',
  profileName: '',
  profileRole: '',
})

// 3. Gunakan Computed untuk menggabungkan Props dengan Data Store secara reaktif
const displayProfileName = computed(() => {
  return props.profileName || authStore?.user?.nama_lengkap || 'Guest User'
})

const displayProfileRole = computed(() => {
  return props.profileRole || authStore?.user?.role || 'Operator'
})


const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}

const closeMenu = () => {
  isMenuOpen.value = false
}

const toggleQuickMenu = () => {
  isQuickMenuOpen.value = !isQuickMenuOpen.value
}

const closeQuickMenu = () => {
  isQuickMenuOpen.value = false
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const closeSidebar = () => {
  isSidebarOpen.value = false
}

const logout = async () => {
  // contoh fungsi logout kamu
  authStore.clearAuthData()
  await navigateTo('/login')
}

// Opsional: Menutup dropdown jika user mengklik di luar area menu
const clickOutsideHandler = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (!target.closest('.profile-dropdown-container')) {
    closeMenu()
  }
  if (!target.closest('.quick-menu-container')) {
    closeQuickMenu()
  }
}

onMounted(() => {
  window.addEventListener('click', clickOutsideHandler)
})

onUnmounted(() => {
  window.removeEventListener('click', clickOutsideHandler)
})


</script>

<template>
  <header class="border-b border-header bg-surface">
    <div
      class="mx-auto flex flex-wrap items-start justify-between gap-3 px-4 py-3 sm:items-center sm:px-6 sm:py-4 lg:px-10">
      <div class="min-w-0 flex items-center gap-2 sm:gap-3">
        <button @click.stop="toggleSidebar"
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-header-soft bg-surface text-brand transition hover-bg-cream sm:h-11 sm:w-11"
          aria-label="Buka Sidebar">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24"
            stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div
          class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-header-soft sm:h-14 sm:w-14">
          <div class="h-8 w-8 rounded-full border-4 border-gold border-t-green-accent sm:h-10 sm:w-10" />
        </div>
        <div class="min-w-0">
          <h1 class="truncate text-16 font-bold leading-tight sm:text-20">
            {{ props.brandTitle }}
          </h1>
          <p class="truncate text-12 text-muted-light sm:text-14">
            {{ props.brandSubtitle }}
          </p>
        </div>
      </div>

      <div class="ml-auto flex items-center gap-2 sm:gap-3">
        <button
          class="flex h-10 w-10 items-center justify-center rounded-full bg-peach text-brand sm:h-12 sm:w-12">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24"
            stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
              d="M10 21h4m-7-4h10l-1-2V11a5 5 0 1 0-10 0v4l-1 2Z" />
          </svg>
        </button>

        <!-- <div class="quick-menu-container relative">
          <button @click.stop="toggleQuickMenu"
            class="flex h-10 w-10 items-center justify-center rounded-full bg-peach text-brand transition hover-bg-peach-hover sm:h-12 sm:w-12"
            aria-label="Quick Menu">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 sm:h-6 sm:w-6" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div v-if="isQuickMenuOpen"
            class="fixed inset-x-4 top-30 z-[1500] rounded-2xl border border-default bg-surface p-3 shadow-xl sm:absolute sm:inset-auto sm:right-0 sm:top-full sm:mt-2 sm:w-[500px] sm:max-w-[90vw]">
            <p class="mb-3 px-2 text-14 font-bold text-brand">
              Quick Menu
            </p>

            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button v-for="item in dashboardService.moduleItems" :key="`quick-menu-${item.title}`"
                @click="navigateTo(item.to); closeQuickMenu()"
                class="flex items-center gap-3 rounded-xl border border-menu px-3 py-2.5 text-left transition hover-bg-cream">
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" :class="item.bgClass">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-on-brand" fill="none" viewBox="0 0 24 24"
                    stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                      :d="dashboardService.iconPath(item.icon)" />
                  </svg>
                </div>
                <div class="min-w-0">
                  <p class="truncate text-13 font-bold text-brand">
                    {{ item.title }}
                  </p>
                  <p class="line-clamp-1 text-12 text-muted-light">
                    {{ item.description }}
                  </p>
                </div>
              </button>
            </div>
          </div>
        </div> -->

        <div class="profile-dropdown-container relative">
          <button @click="toggleMenu"
            class="flex items-center gap-2 rounded-2xl border border-default bg-cream px-2.5 py-2 transition-all hover-bg-cream-hover focus:outline-none sm:gap-3 sm:px-3">
            <div class="h-9 w-9 overflow-hidden rounded-lg bg-avatar sm:h-11 sm:w-11" />
            <div class="hidden text-left sm:block">
              <p class="text-16 font-bold leading-tight text-brand">
                {{ displayProfileName }}
              </p>
              <p class="text-14 text-label">
                {{ displayProfileRole }}
              </p>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-label transition-transform duration-200"
              :class="{ 'rotate-180': isMenuOpen }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <div v-if="isMenuOpen"
            class="absolute right-0 mt-2 w-64 origin-top-right rounded-2xl border border-default bg-surface p-2 shadow-xl z-[1500] animate-fade-in">
            <button v-for="(item, index) in menuItems" :key="index" @click="item.action(); closeMenu();"
              class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover-bg-cream group">
              <div
                class="flex h-9 w-9 items-center justify-center rounded-lg bg-peach text-brand group-hover-bg-gold group-hover-text-on-brand transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" :d="item.icon" />
                </svg>
              </div>
              <div>
                <p class="text-14 font-bold text-brand group-hover-text-gold">
                  {{ item.label }}
                </p>
                <p class="text-12 text-muted-light">
                  {{ item.info }}
                </p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
    <div v-if="isSidebarOpen" class="fixed inset-0 z-[1590] bg-overlay" @click="closeSidebar" />

    <aside
      class="fixed left-0 top-0 z-[1600] flex h-full w-[320px] max-w-[88vw] transform flex-col border-r border-default bg-surface shadow-2xl transition-transform duration-300"
      :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full'">
      <div class="border-b border-menu bg-surface-warm px-4 py-4">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="text-11 font-semibold uppercase tracking-wide text-label">
              Navigasi
            </p>
            <h3 class="truncate text-16 font-bold text-brand">
              Menu Modul
            </h3>
          </div>
          <button @click="closeSidebar"
            class="flex h-9 w-9 items-center justify-center rounded-full border border-menu bg-surface text-label transition hover-bg-cream"
            aria-label="Tutup Sidebar">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto px-3 py-4">
        <section>
          <p class="mb-2 px-2 text-11 font-semibold uppercase tracking-wide text-label">
            Pintasan
          </p>
          <div class="space-y-1">
            <button @click="navigateTo('/dashboard'); closeSidebar()"
              class="flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors duration-200 hover-bg-cream">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-on-brand" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                    d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1v-10.5Z" />
                </svg>
              </div>
              <div class="min-w-0">
                <p class="truncate text-13 font-bold text-brand">
                  Dashboard
                </p>
                <p class="line-clamp-1 text-11 text-muted-light">
                  Halaman utama
                </p>
              </div>
            </button>

            <button v-if="informasiUser?.role === 'superadmin'" @click="navigateTo('/menus'); closeSidebar()"
              class="flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors duration-200 hover-bg-cream">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-menu-blue-light">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-menu-blue" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                    d="M4 7h7v7H4V7Zm9 0h7v7h-7V7ZM4 16h7v5H4v-5Zm9 2h7" />
                </svg>
              </div>
              <div class="min-w-0">
                <p class="truncate text-13 font-bold text-brand">
                  Management Menu
                </p>
                <p class="line-clamp-1 text-11 text-muted-light">
                  Kelola struktur menu
                </p>
              </div>
            </button>
          </div>
        </section>

        <section>
          <div class="mb-2 flex items-center justify-between px-2">
            <p class="text-11 font-semibold uppercase tracking-wide text-label">
              Modul
            </p>
            <span class="rounded-full bg-surface-warm px-2 py-0.5 text-11 font-semibold text-label">
              {{ dashboardService.moduleItems.length }}
            </span>
          </div>

          <div v-if="dashboardService.loading" class="space-y-2 px-1">
            <div v-for="i in 4" :key="`sidebar-skel-${i}`"
              class="flex items-center gap-3 rounded-xl px-2.5 py-2.5 animate-pulse">
              <div class="h-9 w-9 rounded-lg bg-slate-muted" />
              <div class="min-w-0 flex-1 space-y-2">
                <div class="h-3 w-2/3 rounded bg-slate-muted" />
                <div class="h-2.5 w-full rounded bg-slate-muted" />
              </div>
            </div>
          </div>

          <MenuSidebarNode v-else-if="dashboardService.moduleItems.length"
            :items="dashboardService.moduleItems" @navigate="closeSidebar" />

          <p v-else class="rounded-xl bg-surface-warm px-3 py-4 text-center text-12 text-muted">
            Belum ada modul yang tersedia.
          </p>
        </section>
      </div>
    </aside>
  </header>
</template>
