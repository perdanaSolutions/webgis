import { defineStore } from "pinia";
import { ref, shallowRef } from "vue";

type FullscreenDocument = Document & {
  webkitFullscreenElement?: Element | null;
  webkitExitFullscreen?: () => Promise<void> | void;
};

type FullscreenHost = HTMLElement & {
  webkitRequestFullscreen?: () => Promise<void> | void;
};

export const useAppFullscreenStore = defineStore("appFullscreen", () => {
  const hostEl = shallowRef<HTMLElement | null>(null);
  const isFullscreen = ref(false);
  const pseudoFullscreen = ref(false);
  let listenersBound = false;

  function nativeFullscreenElement() {
    const doc = document as FullscreenDocument;
    return document.fullscreenElement ?? doc.webkitFullscreenElement ?? null;
  }

  function onFullscreenChange() {
    const native = hostEl.value != null && nativeFullscreenElement() === hostEl.value;
    if (!native) pseudoFullscreen.value = false;
    isFullscreen.value = native || pseudoFullscreen.value;
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    // Native fullscreen: browser keluar sendiri; state diselaraskan via fullscreenchange.
    // Pseudo fullscreen: Esc harus kita tangani agar tetap aktif di semua halaman.
    if (!pseudoFullscreen.value) return;
    event.preventDefault();
    void exitFullscreen();
  }

  function ensureListeners() {
    if (listenersBound || typeof document === "undefined") return;
    listenersBound = true;
    document.addEventListener("fullscreenchange", onFullscreenChange);
    document.addEventListener("webkitfullscreenchange", onFullscreenChange);
    window.addEventListener("keydown", onKeydown);
  }

  function registerHost(el: HTMLElement | null) {
    hostEl.value = el;
    if (el) ensureListeners();
  }

  async function enterFullscreen() {
    const el = hostEl.value as FullscreenHost | null;
    if (!el) return;
    ensureListeners();
    try {
      if (typeof el.requestFullscreen === "function") {
        await el.requestFullscreen();
        return;
      }
      if (typeof el.webkitRequestFullscreen === "function") {
        await el.webkitRequestFullscreen();
        return;
      }
    } catch {
      /* API ditolak browser — pakai mode cadangan fixed viewport */
    }
    pseudoFullscreen.value = true;
    isFullscreen.value = true;
  }

  async function exitFullscreen() {
    pseudoFullscreen.value = false;
    const doc = document as FullscreenDocument;
    try {
      if (nativeFullscreenElement()) {
        if (document.exitFullscreen) await document.exitFullscreen();
        else await doc.webkitExitFullscreen?.();
        return;
      }
    } catch {
      /* lanjut menutup mode cadangan */
    }
    isFullscreen.value = false;
  }

  async function toggleFullscreen() {
    if (isFullscreen.value) await exitFullscreen();
    else await enterFullscreen();
  }

  return {
    isFullscreen,
    pseudoFullscreen,
    registerHost,
    enterFullscreen,
    exitFullscreen,
    toggleFullscreen,
  };
});
