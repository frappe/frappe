import frappeUIPreset from "frappe-ui/tailwind"

/** @type {import('tailwindcss').Config} */
export default {
	presets: [frappeUIPreset],
	// Tailwind v3 ignores `content` declared inside presets; frappe-ui and the
	// shared core are compiled by this app, so their globs live here.
	content: [
		"./index.html",
		"./src/**/*.{vue,js}",
		"../core/src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
		"./node_modules/frappe-ui/src/utils/**/*.ts",
		"../node_modules/frappe-ui/src/utils/**/*.ts",
	],
}
