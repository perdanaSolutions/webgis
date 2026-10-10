import { preloadMapViewWhenIdle } from "~/utils/preloadMapView"

export default defineNuxtPlugin(() => {
  const route = useRoute()
  if (route.path === "/login") return
  preloadMapViewWhenIdle()
})