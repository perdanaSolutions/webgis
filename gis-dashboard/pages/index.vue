<script setup lang="ts">
import logoImage from '~/assets/image/logo-1.png'
import { useAuthStore } from '~/stores/authStore'
import { isAccessTokenExpired } from '~/utils/authSession'

defineOptions({
  name: 'IndexPage',
})

definePageMeta({
  middleware: [
    function () {
      const authStore = useAuthStore()
      if (!authStore.token || isAccessTokenExpired(authStore.token)) {
        authStore.clearAuthData()
        return navigateTo('/login', { replace: true })
      }
      return navigateTo('/dashboard')
    },
  ],
})
</script>

<template>
  <main
    class="fixed inset-0 z-50 flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-splash">
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-brand-10 blur-3xl" />
      <div class="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-brand-secondary-15 blur-3xl" />
      <div
        class="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-brand-10" />
      <div
        class="absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-brand-5" />
    </div>

    <div class="relative flex flex-col items-center px-6 text-center">
      <div class="relative mb-10 flex h-40 w-44 items-center justify-center">
        <span class="absolute h-36 w-36 rounded-full border-2 border-brand-10" />
        <span
          class="absolute h-36 w-36 animate-spin rounded-full border-2 border-transparent border-t-brand border-r-brand-secondary-60" />
        <img :src="logoImage" alt="TLDN Productivity Technology Science"
          class="relative z-10 h-[4.5rem] w-auto object-contain">
      </div>

      <!-- <h1 class="text-size-xl font-bold tracking-tight text-content-dark sm:text-size-2xl">
        GIS PWA
      </h1> -->
      <p class="mt-2 text-size-sm text-muted-ios">
        Memverifikasi sesi Anda
      </p>

      <div class="mt-8 flex items-center gap-2">
        <span class="h-2 w-2 animate-bounce rounded-full bg-brand [animation-delay:0ms]" />
        <span class="h-2 w-2 animate-bounce rounded-full bg-brand-secondary [animation-delay:150ms]" />
        <span class="h-2 w-2 animate-bounce rounded-full bg-brand [animation-delay:300ms]" />
      </div>

      <div class="mt-10 h-1 w-48 overflow-hidden rounded-full bg-progress-track">
        <div
          class="h-full w-1/2 animate-[loading-bar_1.4s_ease-in-out_infinite] rounded-full bg-gradient-to-r gradient-brand" />
      </div>
    </div>
  </main>
</template>

<style scoped>
@keyframes loading-bar {
  0% {
    transform: translateX(-100%);
  }

  50% {
    transform: translateX(80%);
  }

  100% {
    transform: translateX(220%);
  }
}
</style>
