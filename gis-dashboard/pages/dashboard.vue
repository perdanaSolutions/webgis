<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import palmImage from '~/assets/image/Palm.jpeg'
import { useAuthStore } from '~/stores/authStore'
import Header from '~/components/Header.vue'
import BannerCharts from '~/components/dashboard/BannerCharts.vue'
import { dashboardStore, type ModuleItem } from '~/stores/dashboardStore'

const authStore = useAuthStore()
const dashboardService = dashboardStore()

const menuKeyword = ref('')

function menuMatches(item: ModuleItem, keyword: string) {
  return [item.title, item.description, item.to]
    .join(' ')
    .toLowerCase()
    .includes(keyword)
}

function filterMenus(items: ModuleItem[], keyword: string): ModuleItem[] {
  return items.flatMap((item) => {
    const children = filterMenus(item.children ?? [], keyword)
    if (!menuMatches(item, keyword) && !children.length) return []
    return [{
      ...item,
      children: menuMatches(item, keyword) ? item.children : children,
    }]
  })
}

const appliedKeyword = computed(() => menuKeyword.value.trim().toLowerCase())

const visibleMenus = computed(() => {
  if (!appliedKeyword.value) return dashboardService.moduleItems
  return filterMenus(dashboardService.moduleItems, appliedKeyword.value)
})

function searchMenus() {
  document.getElementById('menu-modul')?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

defineOptions({
  name: 'DashboardPage',
})

onMounted(async () => {
  const session = await authStore.ensureSession()
  if (!session) {
    window.location.replace('/login')
    return
  }
  dashboardService.initDataMenu()
})
</script>

<template>
  <main class="flex min-h-screen flex-col bg-page text-14 text-content">
    <Header :brand-title="dashboardService.dashboardConfig.brandTitle"
      :brand-subtitle="dashboardService.dashboardConfig.brandSubtitle" />
    <MenuDashboardNav id="menu-modul" :items="visibleMenus" :loading="dashboardService.loading" />
    <section class="palm-banner" aria-label="Every Palm Matters">
      <img :src="palmImage" alt="" class="palm-banner__photo">
      <div class="palm-banner__veil" aria-hidden="true" />
      <div class="palm-banner__stage">
        <BannerCharts />
        <div class="palm-banner__card">
          <p class="palm-banner__kicker">When</p>
          <h2 class="palm-banner__title">EVERY PALM MATTERS</h2>
          <p class="palm-banner__lead">
            <span>Optimalisasi produktivitas</span>
            <span>dan sumber daya dengan pendekatan</span>
            <span>teknologi dan ilmu pengetahuan terkini</span>
            <span>yang terhubung dengan tata kelola dan teknis</span>
            <span>budidaya perkebunan sawit terbaik dan berkelanjutan.</span>
          </p>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.palm-banner {
  position: relative;
  display: flex;
  flex: 1 0 auto;
  width: 100%;
  min-height: calc(100dvh - 7.5rem);
  overflow: hidden;
}

.palm-banner__photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 42%;
}

.palm-banner__veil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgb(18 36 10 / 18%) 0%, rgb(18 36 10 / 4%) 34%, rgb(12 24 8 / 22%) 100%);
}

.palm-banner__stage {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1;
  flex-direction: column;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.15rem 1.25rem 1.15rem;
}

.palm-banner__card {
  width: min(500px, 100%);
  border-radius: 14px;
  background: rgb(255 255 255 / 94%);
  padding: 0.65rem 0.85rem 0.7rem;
  text-align: left;
  box-shadow:
    0 14px 32px rgb(16 32 8 / 18%),
    0 0 0 1px rgb(255 255 255 / 70%);
  backdrop-filter: blur(10px);
}

.palm-banner__kicker {
  margin: 0;
  color: #3a9a32;
  font-size: clamp(0.78rem, 1vw, 0.95rem);
  font-style: italic;
  font-weight: 700;
  line-height: 1;
}

.palm-banner__title {
  margin: 0.08rem 0 0;
  color: #111111;
  font-size: clamp(1.05rem, 1.8vw, 1.55rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.05;
  text-transform: uppercase;
  text-wrap: balance;
}

.palm-banner__lead {
  margin: 0.4rem auto 0;
  max-width: 26rem;
  color: #161616;
  font-size: clamp(0.62rem, 0.8vw, 0.72rem);
  font-weight: 600;
  line-height: 1.35;
  text-align: center;
}

.palm-banner__lead span {
  display: block;
}

@media (max-width: 640px) {
  .palm-banner__card {
    padding: 0.6rem 0.75rem 0.65rem;
    border-radius: 12px;
  }

  .palm-banner__lead span {
    display: inline;
  }

  .palm-banner__lead span:not(:last-child)::after {
    content: " ";
  }
}
</style>
