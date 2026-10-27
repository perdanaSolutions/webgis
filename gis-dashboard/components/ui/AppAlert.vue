<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useAlert, useAlertState } from "~/composables/useAlert";

/** Popup global ala SweetAlert. Dipasang sekali di app.vue (di dalam <ClientOnly>). */
const alert = useAlert();
const current = useAlertState();
const panelRef = ref<HTMLElement | null>(null);
const confirmRef = ref<HTMLButtonElement | null>(null);
let lastFocused: HTMLElement | null = null;

function confirm() {
  alert.close(true);
}
function cancel() {
  alert.close(false);
}
function onBackdrop() {
  if (current.value?.dismissible) cancel();
}

function onKeydown(e: KeyboardEvent) {
  if (!current.value) return;
  if (e.key === "Escape" && current.value.dismissible) {
    e.preventDefault();
    cancel();
    return;
  }
  if (e.key === "Tab" && panelRef.value) {
    const items = Array.from(panelRef.value.querySelectorAll<HTMLElement>("button"));
    if (!items.length) return;
    const first = items[0]!;
    const last = items[items.length - 1]!;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

watch(current, async (item, prev) => {
  if (item && !prev) lastFocused = document.activeElement as HTMLElement | null;
  if (item) {
    await nextTick();
    confirmRef.value?.focus();
  } else {
    lastFocused?.focus?.();
    lastFocused = null;
  }
});

onMounted(() => document.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
</script>

<template>
  <AppModalTeleport>
    <Transition name="app-alert">
      <div v-if="current" :key="current.id" class="app-alert-backdrop" @click.self="onBackdrop">
        <div
          ref="panelRef"
          class="app-alert-panel"
          role="alertdialog"
          aria-modal="true"
          :aria-labelledby="`app-alert-title-${current.id}`"
          :aria-describedby="current.text ? `app-alert-text-${current.id}` : undefined"
        >
          <div class="app-alert-icon" :class="`app-alert-icon--${current.icon}`" aria-hidden="true">
            <svg v-if="current.icon === 'success'" viewBox="0 0 52 52">
              <circle class="ring" cx="26" cy="26" r="24" />
              <path class="mark" d="M15 27 l8 8 l15 -16" />
            </svg>
            <svg v-else-if="current.icon === 'error'" viewBox="0 0 52 52">
              <circle class="ring" cx="26" cy="26" r="24" />
              <path class="mark" d="M17 17 L35 35" />
              <path class="mark mark--2" d="M35 17 L17 35" />
            </svg>
            <svg v-else-if="current.icon === 'warning'" viewBox="0 0 52 52">
              <circle class="ring" cx="26" cy="26" r="24" />
              <path class="mark" d="M26 13 V30" />
              <circle class="dot" cx="26" cy="38" r="2.4" />
            </svg>
            <svg v-else-if="current.icon === 'question'" viewBox="0 0 52 52">
              <circle class="ring" cx="26" cy="26" r="24" />
              <path class="mark" d="M20 20 a6 6 0 1 1 8 5.6 c-1.4 .6 -2 1.6 -2 3.2 V31" />
              <circle class="dot" cx="26" cy="38" r="2.4" />
            </svg>
            <svg v-else viewBox="0 0 52 52">
              <circle class="ring" cx="26" cy="26" r="24" />
              <circle class="dot" cx="26" cy="15" r="2.4" />
              <path class="mark" d="M26 22 V38" />
            </svg>
          </div>

          <h2 :id="`app-alert-title-${current.id}`" class="app-alert-title">{{ current.title }}</h2>
          <p v-if="current.text" :id="`app-alert-text-${current.id}`" class="app-alert-text">{{ current.text }}</p>

          <div class="app-alert-actions">
            <button v-if="current.showCancel" type="button" class="app-alert-btn app-alert-btn--cancel" @click="cancel">
              {{ current.cancelText }}
            </button>
            <button ref="confirmRef" type="button" class="app-alert-btn app-alert-btn--confirm" @click="confirm">
              {{ current.confirmText }}
            </button>
          </div>

          <div v-if="current.timer" class="app-alert-timer" :style="{ animationDuration: `${current.timer}ms` }" />
        </div>
      </div>
    </Transition>
  </AppModalTeleport>
</template>

<style scoped>
.app-alert-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgb(31 42 24 / 45%);
}
.app-alert-panel {
  position: relative;
  width: 100%;
  max-width: 400px;
  overflow: hidden;
  border-radius: 20px;
  background: #fff;
  padding: 28px 24px 22px;
  text-align: center;
  box-shadow: 0 24px 48px rgb(0 0 0 / 20%);
}
.app-alert-title {
  margin: 14px 0 0;
  font-size: 18px;
  font-weight: 700;
  color: #1f2a18;
}
.app-alert-text {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: #3d4a34;
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.app-alert-actions {
  margin-top: 22px;
  display: flex;
  justify-content: center;
  gap: 10px;
}
.app-alert-btn {
  min-width: 96px;
  border-radius: 12px;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 600;
  transition: background-color 0.15s;
}
.app-alert-btn:focus-visible {
  outline: 3px solid rgb(99 136 64 / 40%);
  outline-offset: 2px;
}
.app-alert-btn--confirm {
  background: #638840;
  color: #fff;
}
.app-alert-btn--confirm:hover {
  background: #4f6d33;
}
.app-alert-btn--cancel {
  background: #eef2ea;
  color: #3d4a34;
}
.app-alert-btn--cancel:hover {
  background: #dfe6d8;
}
.app-alert-timer {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 4px;
  width: 100%;
  background: rgb(99 136 64 / 50%);
  transform-origin: left;
  animation: app-alert-timer linear forwards;
}

/* Ikon beranimasi ala SweetAlert */
.app-alert-icon {
  margin: 0 auto;
  width: 76px;
  height: 76px;
}
.app-alert-icon svg {
  width: 100%;
  height: 100%;
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.app-alert-icon .ring {
  stroke-dasharray: 151;
  stroke-dashoffset: 151;
  animation: app-alert-draw 0.5s ease-out forwards;
}
.app-alert-icon .mark {
  stroke-width: 4;
  stroke-dasharray: 60;
  stroke-dashoffset: 60;
  animation: app-alert-draw 0.35s 0.4s ease-out forwards;
}
.app-alert-icon .mark--2 {
  animation-delay: 0.6s;
}
.app-alert-icon .dot {
  stroke: none;
  opacity: 0;
  animation: app-alert-fade 0.2s 0.6s forwards;
}
.app-alert-icon--success { stroke: #4f9a3a; color: #4f9a3a; }
.app-alert-icon--error { stroke: #d64545; color: #d64545; animation: app-alert-shake 0.4s 0.75s; }
.app-alert-icon--warning { stroke: #e0a326; color: #e0a326; animation: app-alert-pulse 0.6s 0.6s; }
.app-alert-icon--info { stroke: #3b82c4; color: #3b82c4; }
.app-alert-icon--question { stroke: #638840; color: #638840; }
.app-alert-icon .dot { fill: currentColor; }

.app-alert-enter-active { transition: opacity 0.18s ease; }
.app-alert-enter-active .app-alert-panel { animation: app-alert-pop 0.3s cubic-bezier(0.2, 1.4, 0.4, 1); }
.app-alert-leave-active { transition: opacity 0.12s ease; }
.app-alert-enter-from,
.app-alert-leave-to { opacity: 0; }

@keyframes app-alert-draw { to { stroke-dashoffset: 0; } }
@keyframes app-alert-fade { to { opacity: 1; } }
@keyframes app-alert-pop { 0% { transform: scale(0.7); } 100% { transform: scale(1); } }
@keyframes app-alert-shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  75% { transform: translateX(5px); }
}
@keyframes app-alert-pulse { 50% { transform: scale(1.08); } }
@keyframes app-alert-timer { from { transform: scaleX(1); } to { transform: scaleX(0); } }

@media (max-width: 480px) {
  .app-alert-panel { padding: 24px 18px 18px; border-radius: 16px; }
  .app-alert-actions { flex-direction: column-reverse; }
  .app-alert-btn { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .app-alert-icon *, .app-alert-icon, .app-alert-panel { animation-duration: 0.01ms !important; animation-delay: 0s !important; }
}
</style>
