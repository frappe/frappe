import frappeUIPreset from "frappe-ui/src/tailwind/preset"
import plugin from "tailwindcss/plugin"

export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
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
