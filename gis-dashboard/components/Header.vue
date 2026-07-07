<script setup lang="ts">
import { onMounted, computed, ref, onUnmounted } from 'vue'
import { useAuthStore } from '~/stores/authStore'

const authStore = useAuthStore()

onMounted(async () => {
  if (!authStore.token) {
    await navigateTo('/login')
  }
})

const isMenuOpen = ref(false)
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
}

onMounted(() => {
  window.addEventListener('click', clickOutsideHandler)
})

onUnmounted(() => {
  window.removeEventListener('click', clickOutsideHandler)
})


</script>

<template>
  <header class="border-b border-[#ECE8E3] bg-white">
    <div class="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-4 lg:px-10">
      <div class="flex items-center gap-3">
        <div class="flex h-14 w-14 items-center justify-center rounded-full border border-[#E8DFD5]">
          <div class="h-10 w-10 rounded-full border-4 border-[#D99B47] border-t-[#4A7B3F]" />
        </div>
        <div>
          <h1 class="text-[20px] font-bold leading-tight">
            {{ props.brandTitle }}
          </h1>
          <p class="text-[14px] text-[#8E8A86]">
            {{ props.brandSubtitle }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button class="flex h-12 w-12 items-center justify-center rounded-full bg-[#FFF1E9] text-[#4D392A]">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"
              d="M10 21h4m-7-4h10l-1-2V11a5 5 0 1 0-10 0v4l-1 2Z" />
          </svg>
        </button>

        <div class="profile-dropdown-container relative">
          <button @click="toggleMenu"
            class="flex items-center gap-3 rounded-2xl border border-[#EEE6DE] bg-[#FFF8F2] px-3 py-2 transition-all hover:bg-[#FDF3E7] focus:outline-none">
            <div class="h-11 w-11 overflow-hidden rounded-lg bg-[#D0B59A]" />
            <div class="text-left">
              <p class="text-[16px] font-bold leading-tight text-[#4D392A]">
                {{ displayProfileName }}
              </p>
              <p class="text-[14px] text-[#6F645B]">
                {{ displayProfileRole }}
              </p>
            </div>
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-[#6F645B] transition-transform duration-200"
              :class="{ 'rotate-180': isMenuOpen }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <div v-if="isMenuOpen"
            class="absolute right-0 mt-2 w-64 origin-top-right rounded-2xl border border-[#EEE6DE] bg-white p-2 shadow-xl z-50 animate-fade-in">
            <button v-for="(item, index) in menuItems" :key="index" @click="item.action(); closeMenu();"
              class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-[#FFF8F2] group">
              <div
                class="flex h-9 w-9 items-center justify-center rounded-lg bg-[#FFF1E9] text-[#4D392A] group-hover:bg-[#D99B47] group-hover:text-white transition-colors">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" :d="item.icon" />
                </svg>
              </div>
              <div>
                <p class="text-[14px] font-bold text-[#4D392A] group-hover:text-[#D99B47]">
                  {{ item.label }}
                </p>
                <p class="text-[12px] text-[#8E8A86]">
                  {{ item.info }}
                </p>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
