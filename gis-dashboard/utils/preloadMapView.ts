let pending: Promise<unknown> | null = null

/** Mulai unduh halaman peta sebelum diklik, supaya perpindahan rute tidak menunggu Leaflet. */
export function preloadMapView() {
  if (!import.meta.client) return
  pending ??= import("~/components/blok-profile/BlokProfileView.vue")
}

export function preloadMapViewWhenIdle() {
  if (!import.meta.client) return
  const start = () => preloadMapView()
  if (typeof requestIdleCallback === "function") requestIdleCallback(start, { timeout: 1500 })
  else setTimeout(start, 400)
}

export function preloadMapViewIfNeeded(to: string) {
  if (to === "/map" || to.startsWith("/map/")) preloadMapView()
}
