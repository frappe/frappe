import frappeUIPreset from "frappe-ui/tailwind";

/** @type {import('tailwindcss').Config} */
export default {
	presets: [frappeUIPreset],
	// Tailwind v3 ignores `content` declared inside presets, so the frappe-ui
	// source globs must be listed here for its component classes to be emitted.
	content: [
		"./index.html",
		"./src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
		"./node_modules/frappe-ui/src/composables/**/*.{vue,js,ts}",
		"./node_modules/frappe-ui/src/utils/**/*.{vue,js,ts}",
	],
	theme: { extend: {} },
	plugins: [],
};
