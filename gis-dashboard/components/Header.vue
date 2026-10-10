<script setup lang="ts">
import { onMounted, computed, reactive, ref, onUnmounted } from 'vue'
import logoImage from '~/assets/image/logo-1.png'
import { useAuthStore } from '~/stores/authStore'
import { dashboardStore } from '~/stores/dashboardStore'
import { useManagePengumumanStore, type PengumumanItem } from '~/stores/managePengumumanStore'
import { preloadMapViewIfNeeded } from '~/utils/preloadMapView'

const authStore = useAuthStore()
const dashboardService = dashboardStore()
const pengumumanStore = useManagePengumumanStore()

onMounted(async () => {
  const session = await authStore.ensureSession()
  if (!session) {
    window.location.replace('/login')
    return
  }
  if (!dashboardService.moduleItems.length) {
    dashboardService.initDataMenu()
  }
  pengumumanStore.fetchActivePengumuman()
})

const isMenuOpen = ref(false)
const isFavoriteOpen = ref(false)
const isAnnouncementOpen = ref(false)
const openAnnouncementId = ref('')
const isQuickMenuOpen = ref(false)
const isSidebarOpen = ref(false)
const showProfileModal = ref(false)
const showOldPassword = ref(false)
const showNewPassword = ref(false)
const passwordError = ref('')
const passwordSuccess = ref('')
const passwordForm = reactive({
  password_lama: '',
  password_baru: '',
})

function resetPasswordForm() {
  passwordForm.password_lama = ''
  passwordForm.password_baru = ''
  showOldPassword.value = false
  showNewPassword.value = false
  passwordError.value = ''
  passwordSuccess.value = ''
}

async function openProfileModal() {
  resetPasswordForm()
  showProfileModal.value = true
  await authStore.validateToken({ redirect: false })
}

function closeProfileModal() {
  showProfileModal.value = false
  resetPasswordForm()
}

async function submitPassword() {
  passwordError.value = ''
  passwordSuccess.value = ''
  if (passwordForm.password_baru.length < 8) {
    passwordError.value = 'Password baru minimal 8 karakter.'
    return
  }
  if (passwordForm.password_lama === passwordForm.password_baru) {
    passwordError.value = 'Password baru harus berbeda dari password lama.'
    return
  }

  try {
    await authStore.changePassword(passwordForm.password_lama, passwordForm.password_baru)
    passwordSuccess.value = 'Password berhasil diperbarui.'
    passwordForm.password_lama = ''
    passwordForm.password_baru = ''
    showOldPassword.value = false
    showNewPassword.value = false
  } catch {
    passwordError.value = authStore.errorMessage || 'Gagal memperbarui password.'
  }
}

const menuItems = ref([
  { label: 'Profil Saya', info: 'Lihat detail akun', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z', action: () => { void openProfileModal() } },
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
  if (props.profileRole) return props.profileRole
  const names = (authStore.user?.roles ?? []).filter(Boolean)
  if (names.length) return names.join(', ')
  return authStore?.user?.role || 'Operator'
})


const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
  if (isMenuOpen.value) {
    isFavoriteOpen.value = false
    isAnnouncementOpen.value = false
  }
}

const closeMenu = () => {
  isMenuOpen.value = false
}

const toggleFavoriteMenu = () => {
  isFavoriteOpen.value = !isFavoriteOpen.value
  if (isFavoriteOpen.value) {
    isMenuOpen.value = false
    isAnnouncementOpen.value = false
  }
}

const closeFavoriteMenu = () => {
  isFavoriteOpen.value = false
}

const toggleAnnouncementMenu = () => {
  isAnnouncementOpen.value = !isAnnouncementOpen.value
  if (isAnnouncementOpen.value) {
    isMenuOpen.value = false
    isFavoriteOpen.value = false
    openAnnouncementId.value = ''
    pengumumanStore.fetchActivePengumuman()
  }
}

const closeAnnouncementMenu = () => {
  isAnnouncementOpen.value = false
  openAnnouncementId.value = ''
}

const toggleAnnouncementItem = (id: string) => {
  openAnnouncementId.value = openAnnouncementId.value === id ? '' : id
}

const announcementDate = (item: PengumumanItem) => {
  const source = item.tanggal_mulai || item.created_at
  if (!source) return { day: '–', month: '' }
  const date = new Date(source)
  if (Number.isNaN(date.getTime())) return { day: '–', month: '' }
  return {
    day: String(date.getDate()),
    month: date.toLocaleString('id-ID', { month: 'short' }),
  }
}

const openFavoriteMenu = (to: string) => {
  closeFavoriteMenu()
  if (!to) return
  preloadMapViewIfNeeded(to)
  void navigateTo(to)
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
  if (!target.closest('.favorite-menu-container')) {
    closeFavoriteMenu()
  }
  if (!target.closest('.announcement-menu-container')) {
    closeAnnouncementMenu()
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
    <div class="mx-auto flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 sm:px-5 sm:py-2 lg:px-8">
      <div class="min-w-0 flex items-center gap-2">
        <button @click.stop="toggleSidebar"
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-header-soft bg-surface text-brand transition hover-bg-cream"
          aria-label="Buka Sidebar">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <img :src="logoImage" alt="TLDN Productivity Technology Science"
          class="h-8 w-auto shrink-0 object-contain sm:h-9">
        <div class="min-w-0">
          <h1 class="truncate text-14 font-bold leading-none sm:text-16">
            {{ props.brandTitle }}
          </h1>
          <p class="mt-0.5 truncate text-11 leading-none text-muted-light sm:text-12">
            {{ props.brandSubtitle }}
          </p>
        </div>
      </div>

      <div class="ml-auto flex items-center gap-1.5 sm:gap-2">
        <div v-if="dashboardService.favoriteMenus.length" class="favorite-menu-container relative">
          <button type="button" @click="toggleFavoriteMenu"
            class="flex h-8 w-8 items-center justify-center rounded-full border border-header-soft bg-surface text-brand transition hover-bg-cream"
            :aria-expanded="isFavoriteOpen" aria-label="Menu favorit">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
                d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.563.563 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.563.563 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" />
            </svg>
          </button>

          <div v-if="isFavoriteOpen"
            class="absolute right-0 z-[1500] mt-2 w-72 origin-top-right rounded-2xl border border-default bg-surface p-2 shadow-xl">
            <p class="px-3 py-2 text-12 font-semibold uppercase tracking-wide text-label">
              Menu favorit
            </p>
            <button v-for="item in dashboardService.favoriteMenus" :key="`favorite-menu-${item.id}`" type="button"
              class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover-bg-cream"
              @pointerenter="preloadMapViewIfNeeded(item.to)"
              @click="openFavoriteMenu(item.to)">
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="item.bgClass">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" :class="item.iconClass" fill="none"
                  viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                    :d="dashboardService.iconPath(item.icon)" />
                </svg>
              </span>
              <span class="min-w-0">
                <span class="block truncate text-14 font-bold text-brand">{{ item.title }}</span>
                <span class="block truncate text-12 text-muted-light">{{ item.description || item.to }}</span>
              </span>
            </button>
          </div>
        </div>

        <div class="announcement-menu-container relative">
          <button type="button" @click="toggleAnnouncementMenu"
            class="flex h-8 w-8 items-center justify-center rounded-full bg-peach text-brand transition hover-bg-peach-hover"
            :aria-expanded="isAnnouncementOpen" aria-label="Pengumuman">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24"
              stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
                d="M10 21h4m-7-4h10l-1-2V11a5 5 0 1 0-10 0v4l-1 2Z" />
            </svg>
          </button>

          <div v-if="isAnnouncementOpen"
            class="absolute right-0 z-[1500] mt-2 w-80 origin-top-right rounded-2xl border border-default bg-surface p-2 shadow-xl sm:w-96">
            <p class="px-3 py-2 text-12 font-semibold uppercase tracking-wide text-label">
              Pengumuman
            </p>

            <p v-if="pengumumanStore.loadingActive" class="px-3 py-4 text-12 text-muted">
              Memuat pengumuman...
            </p>
            <p v-else-if="!pengumumanStore.activeItems.length" class="px-3 py-4 text-12 text-muted">
              Belum ada pengumuman aktif.
            </p>

            <div v-else class="max-h-[min(70vh,24rem)] overflow-y-auto">
              <button v-for="item in pengumumanStore.activeItems" :key="`announcement-${item.id}`" type="button"
                class="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover-bg-cream"
                @click="toggleAnnouncementItem(item.id)">
                <span class="w-12 shrink-0 rounded-xl bg-sidebar-hover py-2 text-center">
                  <span class="block text-14 font-bold leading-none text-brand">{{ announcementDate(item).day }}</span>
                  <span class="mt-1 block text-11 leading-none text-muted">{{ announcementDate(item).month }}</span>
                </span>
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-14 font-bold text-brand">{{ item.judul }}</span>
                  <span v-if="openAnnouncementId === item.id"
                    class="mt-1 block whitespace-pre-line text-12 text-muted">{{ item.isi }}</span>
                  <span v-else class="mt-0.5 block line-clamp-2 text-12 text-muted-light">{{ item.isi }}</span>
                </span>
              </button>
            </div>
          </div>
        </div>

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
            class="flex items-center gap-2 rounded-xl border border-default bg-cream px-1.5 py-1 transition-all hover-bg-cream-hover focus:outline-none sm:px-2">
            <div class="h-7 w-7 overflow-hidden rounded-md bg-avatar" />
            <div class="hidden text-left sm:block">
              <p class="text-13 font-bold leading-none text-brand">
                {{ displayProfileName }}
              </p>
              <p class="mt-0.5 text-11 leading-none text-label">
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
          <div class="flex min-w-0 items-center gap-2.5">
            <img :src="logoImage" alt="TLDN Productivity Technology Science"
              class="h-[68px] w-[94px] shrink-0 object-contain">
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

      <div class="flex-1 overflow-y-auto px-3 py-4">
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
                Home
              </p>
              <p class="line-clamp-1 text-11 text-muted-light">
                Halaman utama
              </p>
            </div>
          </button>

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

          <MenuSidebarNode v-else-if="dashboardService.moduleItems.length" :items="dashboardService.moduleItems"
            @navigate="closeSidebar" />

          <p v-else class="rounded-xl bg-surface-warm px-3 py-4 text-center text-12 text-muted">
            Belum ada menu yang tersedia.
          </p>
        </div>
      </div>
    </aside>

    <div v-if="showProfileModal" class="fixed inset-0 z-[1700] flex items-center justify-center bg-overlay p-4"
      @click.self="closeProfileModal">
      <div class="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-surface p-5">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 class="text-18 font-bold">Profil Saya</h3>
            <p class="text-12 text-muted">Informasi akun yang sedang digunakan</p>
          </div>
          <button type="button" class="text-muted" aria-label="Tutup" @click="closeProfileModal">✕</button>
        </div>

        <div class="rounded-2xl bg-surface-warm p-4">
          <div class="flex items-center gap-3">
            <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-peach text-brand">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div class="min-w-0">
              <p class="truncate text-16 font-bold text-brand">{{ displayProfileName }}</p>
              <p class="truncate text-13 text-muted">{{ displayProfileRole }}</p>
            </div>
          </div>

          <dl class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <dt class="text-12 text-label">Username</dt>
              <dd class="font-semibold">{{ authStore.user?.username || '-' }}</dd>
            </div>
            <div>
              <dt class="text-12 text-label">Email</dt>
              <dd class="break-all font-semibold">{{ authStore.user?.email || '-' }}</dd>
            </div>
            <div>
              <dt class="text-12 text-label">Role</dt>
              <dd class="font-semibold">{{ displayProfileRole }}</dd>
            </div>
            <div>
              <dt class="text-12 text-label">Status</dt>
              <dd>
                <span class="rounded-full px-3 py-1 text-size-xs font-semibold" :class="authStore.user?.is_active === false
                  ? 'bg-slate-muted text-slate-muted'
                  : 'bg-success-lighter text-success'">
                  {{ authStore.user?.is_active === false ? 'Nonaktif' : 'Aktif' }}
                </span>
              </dd>
            </div>
          </dl>
        </div>

        <form class="mt-5 border-t border-default pt-5" @submit.prevent="submitPassword">
          <h4 class="text-16 font-bold">Ubah Password</h4>
          <p class="mb-3 text-12 text-muted">Masukkan password lama, lalu password baru minimal 8 karakter.</p>

          <div class="space-y-3">
            <div>
              <label for="password-lama" class="mb-1 block text-label">Password Lama</label>
              <div class="relative">
                <input id="password-lama" v-model="passwordForm.password_lama" required
                  :type="showOldPassword ? 'text' : 'password'" autocomplete="current-password"
                  class="h-11 w-full rounded-xl border border-default px-3 pr-24 outline-none">
                <button type="button" class="absolute inset-y-0 right-3 my-auto text-12 font-semibold text-brand"
                  @click="showOldPassword = !showOldPassword">
                  {{ showOldPassword ? 'Sembunyi' : 'Lihat' }}
                </button>
              </div>
            </div>

            <div>
              <label for="password-baru" class="mb-1 block text-label">Password Baru</label>
              <div class="relative">
                <input id="password-baru" v-model="passwordForm.password_baru" required minlength="8"
                  :type="showNewPassword ? 'text' : 'password'" autocomplete="new-password"
                  class="h-11 w-full rounded-xl border border-default px-3 pr-24 outline-none">
                <button type="button" class="absolute inset-y-0 right-3 my-auto text-12 font-semibold text-brand"
                  @click="showNewPassword = !showNewPassword">
                  {{ showNewPassword ? 'Sembunyi' : 'Lihat' }}
                </button>
              </div>
            </div>
          </div>

          <p v-if="passwordError" class="mt-3 rounded-xl bg-error-light px-4 py-3 text-error">
            {{ passwordError }}
          </p>
          <p v-if="passwordSuccess" class="mt-3 rounded-xl bg-success-lighter px-4 py-3 text-success">
            {{ passwordSuccess }}
          </p>

          <div class="mt-4 flex justify-end gap-2">
            <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
              @click="closeProfileModal">
              Tutup
            </button>
            <button type="submit"
              class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
              :disabled="authStore.loading">
              {{ authStore.loading ? 'Menyimpan...' : 'Simpan Password' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </header>
</template>
