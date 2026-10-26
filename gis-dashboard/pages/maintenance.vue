<script setup lang="ts">
import bannerImage from '~/assets/image/banner-login.png'
import logoImage from '~/assets/image/logo-1.svg'
import { MAINTENANCE_DEFAULT_MESSAGE, MAINTENANCE_STATE_KEY, type MaintenanceStatus } from '~/utils/maintenance'

defineOptions({ name: 'MaintenancePage' })
useHead({ title: 'Website Sedang Dalam Perbaikan' })

const state = useState<MaintenanceStatus | null>(MAINTENANCE_STATE_KEY, () => null)
const message = computed(() => state.value?.message || MAINTENANCE_DEFAULT_MESSAGE)

function reload() {
  window.location.replace('/')
}
</script>

<template>
  <main class="login-page relative min-h-screen w-full overflow-hidden text-14">
    <img :src="bannerImage" alt="" class="pointer-events-none absolute inset-0 h-full w-full object-cover object-center">
    <div class="relative z-10 flex min-h-screen items-center justify-center px-4 py-6 sm:px-6 sm:py-8">
      <section class="w-full max-w-[480px] rounded-3xl border border-white-soft bg-surface px-5 py-8 text-center sm:px-8 sm:py-10">
        <img :src="logoImage" alt="Logo" class="mx-auto h-16 w-auto object-contain sm:h-[72px]">
        <div class="mx-auto mt-6 flex h-16 w-16 items-center justify-center rounded-full bg-[#638840]/10 text-[32px]" aria-hidden="true">
          🛠️
        </div>
        <h1 class="mt-4 text-20 font-bold leading-tight tracking-tight text-content-dark">
          Website Sedang Dalam Perbaikan
        </h1>
        <p class="mt-3 text-14 leading-relaxed text-[#3d4a34]">{{ message }}</p>
        <p class="mt-2 text-13 text-[#6b7563]">
          Halaman ini akan kembali otomatis setelah perbaikan selesai. Terima kasih atas kesabaran Anda.
        </p>
        <button
          type="button"
          class="mt-6 rounded-xl bg-[#638840] px-5 py-2.5 text-13 font-semibold text-white"
          @click="reload"
        >
          Coba Lagi
        </button>
      </section>
    </div>
  </main>
</template>
