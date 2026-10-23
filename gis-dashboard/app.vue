<script setup lang="ts">
import { MENU_ROUTE_CHECKING_KEY, MENU_ROUTE_UNLOCKED_KEY } from "~/utils/menuRouteAccess";

const route = useRoute();
const menuRouteUnlocked = useState(MENU_ROUTE_UNLOCKED_KEY, () => false);
const menuRouteChecking = useState(MENU_ROUTE_CHECKING_KEY, () => false);

const isShell = computed(() => {
  const path = route.path.replace(/\/+$/, "") || "/";
  return path === "/" || path === "/login" || path === "/dashboard";
});

const showPage = computed(() => isShell.value || (menuRouteUnlocked.value && !menuRouteChecking.value));
const showGate = computed(() => menuRouteChecking.value || !showPage.value);
</script>

<template>
  <NuxtPage v-if="showPage" />
  <div v-if="showGate" class="menu-route-gate" role="status" aria-live="polite">
    <span class="menu-route-gate__spinner" aria-hidden="true" />
    <p>Memeriksa akses menu...</p>
  </div>
</template>

<style scoped>
.menu-route-gate {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: #f4f7f1;
  color: #4b5563;
  font-size: 14px;
}

.menu-route-gate p {
  margin: 0;
}

.menu-route-gate__spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgb(99 136 64 / 20%);
  border-top-color: #638840;
  border-radius: 999px;
  animation: menu-route-spin 0.8s linear infinite;
}

@keyframes menu-route-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
