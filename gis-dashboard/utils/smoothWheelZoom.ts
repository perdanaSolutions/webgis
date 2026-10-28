/**
 * Zoom roda/trackpad halus ala Google Maps untuk Leaflet (pengganti `scrollWheelZoom` bawaan).
 *
 * Bawaan Leaflet: event wheel ditampung 40 ms (wheelDebounceTime) lalu satu animasi zoom 250 ms per kumpulan
 * -> terasa tersendat di trackpad. Di sini setiap event wheel langsung menggeser "target zoom", dan peta
 * mengejar target itu tiap frame (rAF) dengan titik di bawah kursor tetap diam. zoomstart/movestart sekali di
 * awal, zoomend/moveend sekali setelah gerakan berhenti (pekerjaan berat cukup sekali).
 *
 * - Mouse wheel (delta besar / deltaMode baris): ±0,5 level per notch.
 * - Trackpad 2 jari (delta kecil): sebanding dengan delta.
 * - Pinch trackpad Mac / Ctrl+wheel (ctrlKey): zoom peta, bukan zoom halaman browser.
 * Listener non-passive + preventDefault -> halaman/induk tidak ikut scroll saat kursor di atas peta.
 */
import type { Map as LMap, LatLng, Point } from "leaflet";

/** Perubahan zoom (level) untuk satu event wheel. Diekspor untuk unit test. */
export function wheelZoomDelta(e: { deltaY: number; deltaMode: number; ctrlKey: boolean }, pageHeight = 800) {
  let d = e.deltaY;
  if (e.deltaMode === 1) d *= 16;
  else if (e.deltaMode === 2) d *= pageHeight;
  const perLevel = e.ctrlKey ? 100 : 200; // pinch lebih responsif
  const z = -d / perLevel;
  return Math.max(-1, Math.min(1, z)); // satu event tidak boleh lompat > 1 level
}

export function installSmoothWheelZoom(map: LMap, L: typeof import("leaflet")) {
  const el = map.getContainer();
  map.scrollWheelZoom.disable();
  let goal: number | null = null;
  let anchorPt: Point | null = null;
  let anchorLL: LatLng | null = null;
  let raf = 0;
  let endTimer: ReturnType<typeof setTimeout> | null = null;
  let moving = false;

  const finish = () => {
    endTimer = null;
    if (raf) return; // masih mengejar target
    if (!moving) return;
    moving = false;
    goal = null;
    (map as any)._moveEnd(true);
  };

  const frame = () => {
    raf = 0;
    if (goal === null || !anchorPt || !anchorLL) return;
    const cur = map.getZoom();
    const diff = goal - cur;
    const z = Math.abs(diff) < 0.002 ? goal : cur + diff * 0.35;
    const size = map.getSize();
    const center = map.unproject(map.project(anchorLL, z).subtract(anchorPt.subtract(size.divideBy(2))), z);
    (map as any)._move(center, z);
    if (z !== goal) raf = requestAnimationFrame(frame);
    else if (!endTimer) endTimer = setTimeout(finish, 90);
  };

  const onWheel = (e: WheelEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!(map as any)._loaded) return;
    const dz = wheelZoomDelta(e, window.innerHeight);
    if (!dz) return;
    const rect = el.getBoundingClientRect();
    const pt = L.point(e.clientX - rect.left, e.clientY - rect.top);
    if (!moving) {
      (map as any)._stop?.();
      moving = true;
      goal = map.getZoom();
      (map as any)._moveStart(true, false);
    }
    if (!anchorPt || anchorPt.distanceTo(pt) > 2) {
      anchorPt = pt;
      anchorLL = map.containerPointToLatLng(pt);
    }
    goal = Math.max(map.getMinZoom(), Math.min(map.getMaxZoom(), (goal ?? map.getZoom()) + dz));
    if (endTimer) { clearTimeout(endTimer); endTimer = null; }
    if (!raf) raf = requestAnimationFrame(frame);
  };

  el.addEventListener("wheel", onWheel, { passive: false });
  return () => {
    el.removeEventListener("wheel", onWheel);
    if (raf) cancelAnimationFrame(raf);
    if (endTimer) clearTimeout(endTimer);
  };
}
