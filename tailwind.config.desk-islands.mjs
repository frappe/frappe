/**
 * Tailwind config for Frappe Desk islands (frappe-ui-based Vue pages).
 *
 * Consumed by the Vite islands PostCSS pipeline (esbuild/build-islands.mjs) to
 * generate the utility classes and design tokens used by:
 *   • frappe-ui source components compiled from `./frappe-ui/src/**`
 *   • App-local Vue components under `./frappe/public/js/**`
 *
 * Isolation strategy (full design in PLAN-FRAPPE-UI-DESK.md): islands mount in a
 * Shadow DOM, which encapsulates CSS both ways. So there is NO CSS-war here —
 * this is plain frappe-ui Tailwind with its normal preflight. The only Desk
 * adaptation lives in the PostCSS chain, not this config: `postcss-root-to-host`
 * rewrites the frappe-ui preset's `:root` design tokens to `:host` so they apply
 * inside the shadow tree. The frappe-ui preset (imported below) supplies the
 * tokens, colour palette, typography scale, shadows, and lucide-* icon plugin.
 */

import frappeUIPreset from "frappe-ui/tailwind";
import { fileURLToPath } from "node:url";
import path from "node:path";

// Use absolute paths (anchored to this file) because the build may be invoked
// from the bench root, not from `apps/frappe/`. Relative `./frappe/public/js`
// content globs would point at the wrong directory and Tailwind would scan
// nothing (or, for `./frappe/public/js`, scandir would ENOENT).
const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('tailwindcss').Config} */
export default {
  presets: [frappeUIPreset],
  darkMode: ["selector", '[data-theme="dark"]'],
  // SHADOW DOM SPIKE: the CSS-war (important scoping + disabled preflight) is
  // gone. The shadow root encapsulates styles both ways, so we ship frappe-ui's
  // normal full Tailwind + preflight. Tokens get rewritten `:root` → `:host` by
  // the postcss-root-to-host plugin (see build-islands.mjs).
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
