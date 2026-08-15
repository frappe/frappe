import frappeUIPreset from "frappe-ui/tailwind"
import plugin from "tailwindcss/plugin"

export default {
	presets: [frappeUIPreset],
	// TextBlock sets its size via a dynamic `:class="[fontSize]"` binding
	// Sync with `fontSize` union in src/types/studio_components/TextBlock.ts.
	safelist: [
		"text-2xs",
		"text-xs",
		"text-sm",
		"text-base",
		"text-md",
		"text-lg",
		"text-xl",
		"text-2xl",
		"text-3xl",
		"text-4xl",
		"text-5xl",
		"text-6xl",
		"text-7xl",
		"text-8xl",
		"text-9xl",
		"text-10xl",
		"text-11xl",
		"text-12xl",
		"text-p-xs",
		"text-p-sm",
		"text-p-base",
		"text-p-md",
		"text-p-lg",
		"text-p-xl",
		"text-p-2xl",
		"text-p-3xl",
		"text-p-4xl",
	],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/molecules/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/molecules/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/experimental/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/experimental/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/frappe/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/frappe/**/*.{vue,js,ts,jsx,tsx}",
		"../../frappe/ui/src/**/*.{vue,js,ts,jsx,tsx}",
		"../../*/studio/**/*.{vue,js,ts,jsx,tsx,json}",
		"!../../*/studio/**/node_modules/**",
	],
	theme: {
		extend: {},
	},
	plugins: [
		plugin(function ({ addUtilities }) {
			addUtilities({
				".hide-scrollbar": {
					/* IE and Edge */
					"-ms-overflow-style": "none",

					/* Firefox */
					"scrollbar-width": "none",

					/* Webkit */
					"&::-webkit-scrollbar": {
						display: "none",
					},
				},
			})
		}),
	],
}
