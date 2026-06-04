/**
 * Tailwind config for Frappe Desk islands (frappe-ui-based Vue pages).
 *
 * This config is used by the esbuild PostCSS pipeline whenever a bundle CSS
 * file contains `@tailwind utilities;` (or `@tailwind components;` /
 * `@tailwind base;`). It generates utility classes and design tokens needed
 * by both:
 *   • frappe-ui source components compiled from `./frappe-ui/src/**`
 *   • App-local Vue components under `./frappe/public/js/**`
 *
 * Isolation strategy (full design in PLAN-FRAPPE-UI-DESK.md):
 *   1. `important: '[data-frappe-ui]'` wraps every utility rule in that
 *      ancestor selector, so utilities only fire inside an island AND beat
 *      Bootstrap's plain-element rules on specificity (0,2,0 vs 0,0,1).
 *   2. `preflight: false` disables the global browser reset — we ship a
 *      hand-rolled `[data-frappe-ui]`-scoped equivalent in
 *      `frappe/public/css/frappe-ui-scoped-preflight.css`, imported once
 *      per bundle.
 *   3. `container: false` because the `container` plugin emits an unscoped
 *      `.container` rule that the `important` selector doesn't reach
 *      (`important` only covers utilities, not components), and that rule
 *      would collide with Bootstrap's `.container`.
 *   4. The frappe-ui preset (imported below) supplies the design tokens,
 *      colour palette, typography scale, shadows, and lucide-* icon class
 *      plugin. The PostCSS `frappe-ui-important` plugin then stamps
 *      `!important` on every emitted declaration inside `[data-frappe-ui]`
 *      so the rules win against Bootstrap's `!important` utilities like
 *      `.pt-5 { padding-top: 42px !important }`.
 */

import frappeUIPreset from "frappe-ui/tailwind";
import { fileURLToPath } from "node:url";
import path from "node:path";

// Use absolute paths because esbuild is normally invoked from the bench
// root, not from `apps/frappe/`. Relative `./frappe/public/js` content
// globs would point at the wrong directory and Tailwind would scan
// nothing (or, in the case of `./frappe/public/js`, scandir would ENOENT).
const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('tailwindcss').Config} */
export default {
  presets: [frappeUIPreset],
  darkMode: ["selector", '[data-theme="dark"]'],
  important: "[data-frappe-ui]",
  corePlugins: {
    preflight: false,
    container: false,
  },
  content: [
    // App-local Vue/JS islands.
    path.join(__dirname, "frappe/public/js/**/*.{vue,js,ts,tsx}"),
    // frappe-ui source. Scanned directly from the linked clone (./frappe-ui)
    // rather than node_modules/frappe-ui — the latter is a symlink and Tailwind
    // content globs are more reliable against the real path.
    path.join(__dirname, "frappe-ui/src/**/*.{vue,js,ts,tsx}"),
  ],
  theme: {
    extend: {},
  },
};
