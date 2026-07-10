<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '~/stores/authStore'
import Header from '~/components/Header.vue'
import { dashboardStore } from '~/stores/dashboardStore'


const authStore = useAuthStore()
const dashboardService = dashboardStore()

defineOptions({
  name: 'DashboardPage',
})

onMounted(async () => {
  if (!authStore.token) {
    await navigateTo('/login')
  }
  dashboardService.initDataMenu()
})

</script>

<template>
  <main class="min-h-screen bg-[#FBFAF8] text-[14px] text-[#2E1F18]">
    <Header :brand-title="dashboardService.dashboardConfig.brandTitle"
      :brand-subtitle="dashboardService.dashboardConfig.brandSubtitle" />
    <div class="mx-auto max-w-[1400px] px-6 py-6 lg:px-10">
      <section class="grid grid-cols-1 items-center gap-4 lg:grid-cols-[1fr_2fr]">
        <div>
          <p class="text-[14px] text-[#8A817A]">
            {{ dashboardService.dashboardConfig.greetingTop }}
          </p>
          <h2 class="text-[20px] font-bold leading-tight">
            {{ authStore.user?.nama_lengkap }}
          </h2>
          <p class="text-[14px] text-[#8A817A]">
            {{ dashboardService.dashboardConfig.greetingDesc }}
          </p>
        </div>

        <div class="flex items-center gap-3 rounded-full border border-[#EEE6DE] bg-white p-3 shadow-sm">
          <input type="text" :placeholder="dashboardService.dashboardConfig.searchPlaceholder"
            class="h-11 flex-1 rounded-full px-5 text-[14px] outline-none placeholder:text-[#A6A29D]">
          <button class="rounded-full bg-[#4D392A] px-8 py-3 text-[14px] font-semibold text-white">
            {{ dashboardService.dashboardConfig.searchButtonLabel }}
          </button>
        </div>
      </section>

      <section class="mt-6 grid grid-cols-1 gap-6">
        <!-- xl:grid-cols-[1.1fr_1.4fr] -->
        <!-- <div class="rounded-2xl border border-[#EEE6DE] bg-white p-5">
          <h3 class="text-[16px] font-bold">
            {{ dashboardService.dashboardConfig.quickAccessTitle }}
          </h3>
          <p class="text-[14px] text-[#8A817A]">
            {{ dashboardService.dashboardConfig.quickAccessDesc }}
          </p>

          <div class="mt-5 grid grid-cols-3 gap-4 sm:grid-cols-5">
            <NuxtLink v-for="item in dashboardService.quickAccessItems" :key="`quick-${item.title}`" :to="item.to"
              class="flex flex-col items-center gap-2">
              <div class="flex h-16 w-16 items-center justify-center rounded-2xl" :class="item.bgClass">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor" :class="item.iconClass">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                    :d="dashboardService.iconPath(item.icon)" />
                </svg>
              </div>
              <span class="text-center text-[14px] font-semibold">{{ item.title }}</span>
            </NuxtLink>
          </div>
        </div> -->

        <div class="rounded-2xl bg-[#4D392A] p-5 text-white">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-[16px] font-bold">
              {{ dashboardService.dashboardConfig.announcementTitle }}
            </h3>
            <button class="text-[14px] font-semibold">
              {{ dashboardService.dashboardConfig.announcementSeeAll }}
            </button>
          </div>

          <div class="space-y-3 rounded-xl bg-white p-4 text-[#2E1F18]">
            <div v-for="(item, index) in dashboardService.announcements" :key="`announcement-${item.title}`"
              class="flex items-center gap-4 py-2"
              :class="{ 'border-b border-[#EFE8E1]': index < dashboardService.announcements.length - 1 }">
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
            {{ dashboardService.dashboardConfig.moduleTitle }}
          </h3>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <NuxtLink v-for="item in dashboardService.moduleItems" :key="`module-${item.title}`" :to="item.to"
            class="flex items-center gap-4 rounded-2xl border border-[#EEE6DE] bg-white p-4 transition hover:shadow-sm">
            <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl" :class="item.bgClass">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"
                  :d="dashboardService.iconPath(item.icon)" />
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
