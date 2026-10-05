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
	theme: {
		extend: {
			// Chat-scale type ramp (design: 15px body). Same override the Flow
			// panel uses, so shared components render identically there.
			fontSize: {
				"2xs": ["12px", { lineHeight: "1.15", letterSpacing: "0.01em", fontWeight: "420" }],
				xs: ["13px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				sm: ["14px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				base: ["15px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				lg: ["17px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "400" }],
			},
		},
	},
}
