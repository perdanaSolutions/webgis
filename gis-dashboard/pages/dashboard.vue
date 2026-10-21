<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import skyImage from '~/assets/image/3.png'
import sloganImage from '~/assets/image/slogan-palm.png'
import handsImage from '~/assets/image/hands-tldn.png'
import estateImage from '~/assets/image/4.png'
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
    <section class="dash-home" aria-label="Ringkasan perkebunan">
      <img :src="skyImage" alt="" class="dash-home__sky">
      <div class="dash-home__panel">
        <BannerCharts />
      </div>
      <div class="dash-home__hero">
        <img :src="estateImage" alt="" class="dash-home__estate">
        <div class="dash-home__story">
          <img :src="sloganImage" alt="When Every Palm Matters" class="dash-home__slogan">
          <p class="dash-home__lead">
            Optimalisasi produktivitas dan sumber daya
            dengan pendekatan teknologi dan ilmu pengetahuan terkini
            yang terhubung dengan tata kelola dan teknis budidaya
            perkebunan kelapa sawit terbaik dan berkelanjutan.
          </p>
        </div>
        <img :src="handsImage" alt="Teknologi perkebunan di atas telapak tangan" class="dash-home__hands">
      </div>
    </section>
  </main>
</template>

<style scoped>
.dash-home {
  display: flex;
  flex: 1 0 auto;
  flex-direction: column;
  background: #fff;
}

.dash-home__sky {
  display: block;
  width: 100%;
  height: auto;
}

.dash-home__panel {
  padding: 0.85rem 1.15rem 0.35rem;
}

.dash-home__hero {
  position: relative;
  height: clamp(460px, 52vw, 680px);
  margin-top: 0.55rem;
  overflow: hidden;
}

.dash-home__estate {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 78%;
}

.dash-home__story {
  position: absolute;
  z-index: 1;
  top: 34%;
  left: 4.5%;
  display: flex;
  width: min(34rem, 40%);
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.dash-home__slogan {
  display: block;
  width: 100%;
  height: auto;
  filter: drop-shadow(0 6px 16px rgb(255 255 255 / 28%));
}

.dash-home__lead {
  margin: 0.45rem 0 0;
  max-width: 34rem;
  color: #f4e7a4;
  font-size: clamp(0.72rem, 1.05vw, 0.98rem);
  font-weight: 600;
  line-height: 1.45;
  text-shadow: 0 1px 2px rgb(20 40 8 / 35%);
}

.dash-home__hands {
  position: absolute;
  z-index: 1;
  right: 1%;
  bottom: 0;
  width: auto;
  max-width: 46%;
  height: 92%;
  object-fit: contain;
  object-position: right bottom;
  pointer-events: none;
  user-select: none;
}

@media (max-width: 900px) {
  .dash-home__panel {
    padding: 0.75rem 0.75rem 0.2rem;
  }

  .dash-home__hero {
    display: flex;
    height: auto;
    min-height: 520px;
    flex-direction: column;
    justify-content: flex-end;
  }

  .dash-home__estate {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .dash-home__story {
    position: relative;
    top: auto;
    left: auto;
    width: min(100% - 1.5rem, 28rem);
    margin: 0 auto 0.5rem;
    padding-top: 4.5rem;
  }

  .dash-home__hands {
    position: relative;
    right: auto;
    bottom: auto;
    width: min(100%, 420px);
    max-width: 100%;
    height: auto;
    margin: 0 auto;
  }
}
</style>
