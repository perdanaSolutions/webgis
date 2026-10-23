import type { Config } from "tailwindcss";

/** Dynamic map/chart color classes (see nuxt.config safelist history). */
const colorNames = [
  "slate",
  "gray",
  "zinc",
  "neutral",
  "stone",
  "red",
  "orange",
  "amber",
  "yellow",
  "lime",
  "green",
  "emerald",
  "teal",
  "cyan",
  "sky",
  "blue",
  "indigo",
  "violet",
  "purple",
  "fuchsia",
  "pink",
  "rose",
] as const;

const safelist = colorNames.flatMap((name) => [
  `bg-${name}-500`,
  `text-${name}-500`,
]);

export default {
  content: [],
  safelist,
} satisfies Config;
