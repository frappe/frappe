import frappeUIPreset from "frappe-ui/tailwind";

/** @type {import('tailwindcss').Config} */
export default {
	presets: [frappeUIPreset],
	// Tailwind v3 ignores `content` in presets; frappe-ui and the shared core are
	// compiled by this app, so their globs live here.
	content: [
		"./frontend/index.html",
		"./frontend/src/**/*.{vue,js}",
		"./harness/ui/core/src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
		"./node_modules/frappe-ui/src/utils/**/*.ts",
	],
	theme: {
		extend: {
			// Chat-scale type ramp, the same override the harness web app uses, so the
			// shared components render identically in both shells.
			fontSize: {
				"2xs": [
					"12px",
					{ lineHeight: "1.15", letterSpacing: "0.01em", fontWeight: "420" },
				],
				xs: ["13px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				sm: ["14px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				base: ["15px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				lg: ["17px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "400" }],
			},
		},
	},
};
