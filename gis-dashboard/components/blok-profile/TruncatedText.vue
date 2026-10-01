<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";

/**
 * Teks satu baris. Label mengambang hanya muncul saat elemen benar-benar terpotong
 * (scroll melebihi lebar), misalnya karena kolom menyempit.
 */
defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<{ text: string; tag?: string }>(), { tag: "span" });

const root = ref<HTMLElement | null>(null);
const open = ref(false);
const tipStyle = ref<Record<string, string>>({});

function overflows(el: HTMLElement) {
  return el.scrollWidth - el.clientWidth > 1;
}

function place(el: HTMLElement) {
  const rect = el.getBoundingClientRect();
  const margin = 8;
  const maxWidth = Math.min(320, window.innerWidth - margin * 2);
  let left = rect.left;
  if (left + maxWidth > window.innerWidth - margin) left = window.innerWidth - margin - maxWidth;
  if (left < margin) left = margin;
  const above = rect.top > 64;
  tipStyle.value = {
    left: `${left}px`,
    top: above ? `${rect.top - 6}px` : `${rect.bottom + 6}px`,
    maxWidth: `${maxWidth}px`,
    transform: above ? "translateY(-100%)" : "none",
  };
}

function show() {
  const el = root.value;
  if (!el || !props.text || !overflows(el)) {
    hide();
    return;
  }
  place(el);
  open.value = true;
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
}

function hide() {
  open.value = false;
  if (typeof window === "undefined") return;
  window.removeEventListener("scroll", hide, true);
  window.removeEventListener("resize", hide);
}

onBeforeUnmount(hide);
</script>

<template>
  <component :is="tag" ref="root" v-bind="$attrs" class="block min-w-0 max-w-full truncate" @mouseenter="show" @mouseleave="hide" @focus="show" @blur="hide">
    <slot>{{ text }}</slot>
  </component>
  <Teleport to="body">
    <div v-if="open" role="tooltip"
      class="pointer-events-none fixed z-[4000] whitespace-normal break-words rounded-lg border border-[#d5dcc8] bg-white px-2.5 py-1.5 text-13 font-medium leading-snug text-[#1f2a18] shadow-lg"
      :style="tipStyle">
      {{ text }}
    </div>
  </Teleport>
</template>
