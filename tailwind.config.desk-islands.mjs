/**
 * Tailwind config for Frappe desk-island Vue components.
 *
 * Used by the esbuild PostCSS pipeline when a bundle CSS file includes
 * `@tailwind utilities;`.  Generates scoped utility classes for any Vue
 * component under `frappe/public/js/` that is part of a desk island.
 *
 * Key design decisions:
 *   - `presets: [frappeUIPreset]`  → inherits the full frappe-ui color
 *     palette, font-size scale, shadows, etc., so custom utilities like
 *     `text-ink-gray-9`, `text-p-sm`, `border-outline-gray-1` are generated.
 *   - `important: '[data-frappe-ui]'` → every utility is emitted as
 *     `[data-frappe-ui] .p-6 { … }` (specificity 0,2,0) so desk-island
 *     styles don't leak to Bootstrap DOM.
 *   - `preflight: false` + `container: false` → a full scoped preflight
 *     is already baked into `frappe-ui/dist/desk/style.css`; the container
 *     plugin lives in @tailwind components which is not invoked here.
 *   - `content` scans only the Frappe app's public/js Vue components so
 *     the generated CSS stays minimal.
 */

import frappeUIPreset from "frappe-ui/tailwind";

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
    // All Vue/JS desk-island components inside the Frappe app.
    // Resolved relative to this config file's directory (apps/frappe/).
    "./frappe/public/js/**/*.{vue,js,ts,tsx}",
  ],
  theme: {
    extend: {},
  },
};
