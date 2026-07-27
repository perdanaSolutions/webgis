<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '~/stores/authStore'

defineOptions({
  name: 'IndexPage',
})

const authStore = useAuthStore()

onMounted(async () => {
  const me = await authStore.validateToken()
  if (me) {
    await navigateTo('/dashboard')
  }
})
</script>

<template>
  <main
    class="fixed inset-0 z-50 flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-[#FCFBFA]">
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-[#4D392A]/10 blur-3xl" />
      <div class="absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-[#5B432F]/15 blur-3xl" />
      <div
        class="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#4D392A]/10" />
      <div
        class="absolute left-1/2 top-1/2 h-[420px] w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#4D392A]/5" />
    </div>

    <div class="relative flex flex-col items-center px-6 text-center">
      <div class="relative mb-10 flex h-28 w-28 items-center justify-center">
        <span class="absolute inset-0 rounded-full border-2 border-[#4D392A]/15" />
        <span
          class="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-[#4D392A] border-r-[#5B432F]/60" />
        <span class="absolute inset-3 animate-pulse rounded-full bg-[#4D392A]/10" />
        <div
          class="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-[#4D392A] text-white shadow-lg shadow-[#4D392A]/25">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-9 w-9 animate-pulse" fill="none" viewBox="0 0 24 24"
            stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M9 6.75V15m6-6v8.25m.513 3.17C17.07 17.98 14.7 17 12 17s-5.07.98-6.437 2.83M14.25 9.75c0 .414-.336.75-.75.75h-3a.75.75 0 01-.75-.75V4.875C12 3.84 12.84 3 13.875 3h.375c.621 0 1.125.504 1.125 1.125v5.625Z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 19.5h15" />
          </svg>
        </div>
      </div>

      <h1 class="text-xl font-bold tracking-tight text-[#2C1F1A] sm:text-2xl">
        GIS PWA
      </h1>
      <p class="mt-2 text-sm text-[#8E8E93]">
        Memverifikasi sesi Anda
      </p>

      <div class="mt-8 flex items-center gap-2">
        <span class="h-2 w-2 animate-bounce rounded-full bg-[#4D392A] [animation-delay:0ms]" />
        <span class="h-2 w-2 animate-bounce rounded-full bg-[#5B432F] [animation-delay:150ms]" />
        <span class="h-2 w-2 animate-bounce rounded-full bg-[#4D392A] [animation-delay:300ms]" />
      </div>

      <div class="mt-10 h-1 w-48 overflow-hidden rounded-full bg-[#E8E4E1]">
        <div
          class="h-full w-1/2 animate-[loading-bar_1.4s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-[#4D392A] to-[#5B432F]" />
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
