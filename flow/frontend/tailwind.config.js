import frappeUIPreset from "frappe-ui/tailwind";

/** @type {import('tailwindcss').Config} */
export default {
	presets: [frappeUIPreset],
	// Desk's bootstrap defines the same utility names (.py-3, .mb-2, …) with
	// !important; flow's must be !important too so the #flow-root prefix can win.
	important: true,
	// Tailwind v3 ignores `content` declared inside presets, so the frappe-ui
	// source globs must be listed here for its component classes to be emitted.
	content: [
		"./index.html",
		"./src/**/*.{vue,js}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts}",
		"./node_modules/frappe-ui/src/composables/**/*.{vue,js,ts}",
		"./node_modules/frappe-ui/src/utils/**/*.{vue,js,ts}",
	],
	theme: {
		extend: {
			fontSize: {
				"2xs": [
					"12px",
					{ lineHeight: "1.15", letterSpacing: "0.01em", fontWeight: "420" },
				],
				xs: ["13px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				sm: ["14px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				base: ["15px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "420" }],
				lg: ["17px", { lineHeight: "1.15", letterSpacing: "0.02em", fontWeight: "400" }],
				xl: ["19px", { lineHeight: "1.15", letterSpacing: "0.01em", fontWeight: "400" }],
				"2xl": [
					"21px",
					{ lineHeight: "1.15", letterSpacing: "0.01em", fontWeight: "400" },
				],
				"3xl": [
					"25px",
					{ lineHeight: "1.15", letterSpacing: "0.005em", fontWeight: "400" },
				],
			},
		},
	},
	plugins: [],
};
