<script setup lang="ts">
import { onMounted, onUnmounted, nextTick, ref } from "vue";
import type { ModuleItem } from "~/stores/dashboardStore";
import { preloadMapViewIfNeeded } from "~/utils/preloadMapView";

defineOptions({
  name: "MenuDashboardNav",
});

const props = withDefaults(
  defineProps<{
    items: ModuleItem[];
    loading?: boolean;
  }>(),
  {
    loading: false,
  },
);

type MenuColumn = {
  key: string;
  title: string;
  to: string;
  links: ModuleItem[];
};

const openKey = ref("");
const flipKeys = ref<Record<string, boolean>>({});
const panelTops = ref<Record<string, string>>({});
const itemEls = new Map<string, HTMLElement>();

function itemKey(item: ModuleItem, index: number) {
  return item.id || `${item.title}-${index}`;
}

function hasChildren(item: ModuleItem) {
  return Boolean(item.children?.length);
}

function columnsFor(item: ModuleItem): MenuColumn[] {
  const children = item.children ?? [];
  const groups = children.filter((child) => child.children?.length);
  const leaves = children.filter((child) => !child.children?.length);

  if (!groups.length) {
    return [{ key: `${item.id}-links`, title: "", to: "", links: leaves }];
  }

  const columns = groups.map((group) => ({
    key: group.id || group.title,
    title: group.title,
    to: group.to,
    links: group.children ?? [],
  }));

  if (leaves.length) {
    columns.unshift({
      key: `${item.id}-links`,
      title: "",
      to: "",
      links: leaves,
    });
  }

  return columns;
}

function setItemEl(key: string, el: unknown) {
  if (el instanceof HTMLElement) itemEls.set(key, el);
  else if (!el) itemEls.delete(key);
}

async function placePanel(key: string) {
  await nextTick();
  const itemEl = itemEls.get(key);
  const panel = itemEl?.querySelector<HTMLElement>(".menu-nav__panel");
  if (!itemEl || !panel) return;

  const itemRect = itemEl.getBoundingClientRect();
  const narrow = window.innerWidth <= 640;
  panelTops.value = {
    ...panelTops.value,
    [key]: `${Math.round(itemRect.bottom)}px`,
  };

  if (narrow) {
    flipKeys.value = { ...flipKeys.value, [key]: false };
    return;
  }

  flipKeys.value = { ...flipKeys.value, [key]: false };
  await nextTick();
  const rect = panel.getBoundingClientRect();
  flipKeys.value = {
    ...flipKeys.value,
    [key]: rect.right > window.innerWidth - 12,
  };
}

function openMenu(key: string) {
  const itemEl = itemEls.get(key);
  if (itemEl) {
    panelTops.value = {
      ...panelTops.value,
      [key]: `${Math.round(itemEl.getBoundingClientRect().bottom)}px`,
    };
  }
  openKey.value = key;
  void placePanel(key);
}

function closeMenu() {
  openKey.value = "";
}

function toggleMenu(key: string) {
  if (openKey.value === key) {
    closeMenu();
    return;
  }
  openMenu(key);
}

function prefersHover() {
  return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

function onTriggerClick(item: ModuleItem, key: string, event: MouseEvent) {
  if (!hasChildren(item)) return;
  if (prefersHover() && item.to) return;
  if (!prefersHover() && item.to && openKey.value === key) return;
  event.preventDefault();
  toggleMenu(key);
}

function onPointerEnter(key: string) {
  if (!prefersHover()) return;
  openMenu(key);
}

function onPointerLeave() {
  if (!prefersHover()) return;
  closeMenu();
}

function onDocumentClick(event: MouseEvent) {
  const target = event.target as Node | null;
  if (!target) return;
  for (const el of itemEls.values()) {
    if (el.contains(target)) return;
  }
  closeMenu();
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") closeMenu();
}

function onResize() {
  if (openKey.value) void placePanel(openKey.value);
}

function onScroll() {
  if (openKey.value) closeMenu();
}

onMounted(() => {
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onKeydown);
  window.addEventListener("resize", onResize);
  window.addEventListener("scroll", onScroll, true);
});

onUnmounted(() => {
  document.removeEventListener("click", onDocumentClick);
  document.removeEventListener("keydown", onKeydown);
  window.removeEventListener("resize", onResize);
  window.removeEventListener("scroll", onScroll, true);
});
</script>

<template>
  <nav class="menu-nav" aria-label="Menu modul">
    <p v-if="props.loading && !props.items.length" class="menu-nav__empty">Memuat menu...</p>
    <p v-else-if="!props.items.length" class="menu-nav__empty">Menu belum tersedia.</p>
    <ul v-else class="menu-nav__list">
      <li v-for="(item, index) in props.items" :key="itemKey(item, index)"
        :ref="(el) => setItemEl(itemKey(item, index), el)" class="menu-nav__item"
        :class="{ 'is-open': openKey === itemKey(item, index) }" @mouseenter="onPointerEnter(itemKey(item, index))"
        @mouseleave="onPointerLeave">
        <div class="menu-nav__trigger">
          <NuxtLink v-if="item.to" :to="item.to" class="menu-nav__label"
            @pointerenter="preloadMapViewIfNeeded(item.to)"
            @click="onTriggerClick(item, itemKey(item, index), $event)">
            {{ item.title }}
          </NuxtLink>
          <button v-else type="button" class="menu-nav__label"
            :aria-expanded="hasChildren(item) ? openKey === itemKey(item, index) : undefined"
            @click="onTriggerClick(item, itemKey(item, index), $event)">
            {{ item.title }}
          </button>
          <button v-if="hasChildren(item)" type="button" class="menu-nav__caret"
            :aria-expanded="openKey === itemKey(item, index)" :aria-label="`Buka submenu ${item.title}`"
            @click.stop="toggleMenu(itemKey(item, index))">
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M5 7.5 10 12.5 15 7.5" fill="none" stroke="currentColor" stroke-width="1.8"
                stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>

        <div v-if="hasChildren(item)" class="menu-nav__panel"
          :style="{ '--menu-panel-top': panelTops[itemKey(item, index)] || '0px' }" :class="{
            'is-flip': flipKeys[itemKey(item, index)],
            'is-single': columnsFor(item).length === 1 && !columnsFor(item)[0]?.title,
          }">
          <div class="menu-nav__columns">
            <section v-for="column in columnsFor(item)" :key="column.key" class="menu-nav__column">
              <h3 v-if="column.title" class="menu-nav__heading">
                <NuxtLink v-if="column.to" :to="column.to" @pointerenter="preloadMapViewIfNeeded(column.to)" @click="closeMenu">
                  {{ column.title }}
                </NuxtLink>
                <span v-else>{{ column.title }}</span>
              </h3>
              <ul class="menu-nav__links">
                <li v-for="link in column.links" :key="link.id || link.title">
                  <NuxtLink v-if="link.to" :to="link.to" class="menu-nav__link" @pointerenter="preloadMapViewIfNeeded(link.to)" @click="closeMenu">
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M7.5 4.5 13 10l-5.5 5.5" fill="none" stroke="currentColor" stroke-width="1.7"
                        stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <span>{{ link.title }}</span>
                  </NuxtLink>
                  <span v-else class="menu-nav__link is-static">
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M7.5 4.5 13 10l-5.5 5.5" fill="none" stroke="currentColor" stroke-width="1.7"
                        stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <span>{{ link.title }}</span>
                  </span>
                  <ul v-if="link.children?.length" class="menu-nav__nested">
                    <li v-for="nested in link.children" :key="nested.id || nested.title">
                      <NuxtLink v-if="nested.to" :to="nested.to" class="menu-nav__link" @pointerenter="preloadMapViewIfNeeded(nested.to)" @click="closeMenu">
                        <svg viewBox="0 0 20 20" aria-hidden="true">
                          <path d="M7.5 4.5 13 10l-5.5 5.5" fill="none" stroke="currentColor" stroke-width="1.7"
                            stroke-linecap="round" stroke-linejoin="round" />
                        </svg>
                        <span>{{ nested.title }}</span>
                      </NuxtLink>
                      <span v-else class="menu-nav__link is-static">
                        <span>{{ nested.title }}</span>
                      </span>
                    </li>
                  </ul>
                </li>
              </ul>
            </section>
          </div>
        </div>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.menu-nav {
  position: relative;
  background: var(--color-brand);
  color: #f7f8f9;
  box-shadow: 0 10px 24px rgb(63 87 40 / 16%);
}

.menu-nav__empty {
  margin: 0;
  padding: 0.9rem 1.25rem;
  font-size: 0.92rem;
  color: rgb(247 248 249 / 80%);
  text-align: center;
}

.menu-nav__list {
  display: flex;
  flex-wrap: wrap;
  justify-content: safe center;
  align-items: stretch;
  gap: 0;
  margin: 0;
  padding: 0 0.75rem;
  list-style: none;
}

.menu-nav__item {
  position: relative;
}

.menu-nav__trigger {
  display: flex;
  align-items: stretch;
  min-height: 48px;
}

.menu-nav__label,
.menu-nav__caret {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.menu-nav__label {
  display: flex;
  align-items: center;
  padding: 0.75rem 0.35rem 0.75rem 0.95rem;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.2;
  text-decoration: none;
  white-space: nowrap;
}

.menu-nav__caret {
  display: flex;
  align-items: center;
  padding: 0 0.85rem 0 0.2rem;
}

.menu-nav__caret svg {
  width: 0.85rem;
  height: 0.85rem;
}

.menu-nav__item:hover > .menu-nav__trigger,
.menu-nav__item:focus-within > .menu-nav__trigger,
.menu-nav__item.is-open > .menu-nav__trigger {
  background: var(--color-brand-hover);
}

.menu-nav__panel {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 30;
  min-width: 280px;
  max-width: min(920px, calc(100vw - 1.5rem));
  padding: 1.15rem 1.35rem 1.25rem;
  background: var(--color-brand);
  border-radius: 0 0 12px 12px;
  box-shadow: 0 18px 36px rgb(63 87 40 / 28%);
  visibility: hidden;
  opacity: 0;
  pointer-events: none;
}

.menu-nav__panel.is-single {
  min-width: 260px;
  padding: 0.7rem 0.55rem;
}

.menu-nav__panel.is-flip {
  left: auto;
  right: 0;
  border-radius: 0 0 12px 12px;
}

.menu-nav__item.is-open > .menu-nav__panel,
.menu-nav__item:focus-within > .menu-nav__panel {
  visibility: visible;
  opacity: 1;
  pointer-events: auto;
}

@media (hover: hover) and (pointer: fine) {
  .menu-nav__item:hover > .menu-nav__panel {
    visibility: visible;
    opacity: 1;
    pointer-events: auto;
  }
}

.menu-nav__columns {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 1.25rem 2.75rem;
}

.menu-nav__column {
  min-width: 220px;
  flex: 1 1 220px;
}

.menu-nav__panel.is-single .menu-nav__column {
  min-width: 0;
  flex-basis: auto;
}

.menu-nav__heading {
  margin: 0 0 0.75rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px solid rgb(255 255 255 / 42%);
  font-size: 1.02rem;
  font-weight: 600;
  line-height: 1.3;
}

.menu-nav__heading a {
  color: inherit;
  text-decoration: none;
}

.menu-nav__heading a:hover {
  color: #ffffff;
}

.menu-nav__links,
.menu-nav__nested {
  margin: 0;
  padding: 0;
  list-style: none;
}

.menu-nav__nested {
  margin: 0.15rem 0 0.35rem 1.35rem;
}

.menu-nav__link {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  border-radius: 8px;
  padding: 0.42rem 0.45rem;
  color: rgb(247 248 249 / 94%);
  font-size: 0.94rem;
  font-weight: 500;
  line-height: 1.35;
  text-decoration: none;
}

.menu-nav__link svg {
  width: 0.85rem;
  height: 0.85rem;
  flex: 0 0 auto;
  opacity: 0.9;
}

.menu-nav__link:hover {
  background: rgb(255 255 255 / 10%);
  color: #ffffff;
}

.menu-nav__link.is-static {
  cursor: default;
}

.menu-nav__link.is-static:hover {
  background: transparent;
}

@media (min-width: 640px) {
  .menu-nav__list {
    padding-inline: 1.25rem;
  }
}

@media (min-width: 1024px) {
  .menu-nav__list {
    padding-inline: 2rem;
  }
}

@media (max-width: 640px) {
  .menu-nav__list {
    flex-wrap: nowrap;
    justify-content: safe center;
    overflow-x: auto;
  }

  .menu-nav__label {
    padding-left: 0.75rem;
    font-size: 0.9rem;
  }

  .menu-nav__panel,
  .menu-nav__panel.is-flip {
    position: fixed;
    top: var(--menu-panel-top, 0px);
    right: 0.75rem;
    left: 0.75rem;
    max-width: none;
  }
}
</style>
