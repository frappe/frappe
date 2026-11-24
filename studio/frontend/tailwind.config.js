import path from "node:path"
import { fileURLToPath } from "node:url"
import frappeUIPreset, { content as frappeUIContent } from "frappe-ui/tailwind"
import plugin from "tailwindcss/plugin"
import { cssVariables } from "frappe-ui/tailwind/tokens"
import { findStudioAppFolders } from "./vite/studioApps.js"
import blockClasses from "./tailwind/blockClasses.js"

const appsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../")
// Every exported studio app on the bench, minus the node_modules a shared folder may carry.
// Listed per app (not `*/studio/**`) since this editor, its node_modules and frappe-ui's
// sources included, sits under frappe's studio/ folder too.
const exportedAppContent = findStudioAppFolders(appsDir).flatMap((folder) => [
	`${folder}/**/*.{vue,js,ts,jsx,tsx,json}`,
	`!${folder}/**/node_modules/**`,
])

export default {
	presets: [frappeUIPreset],
	safelist: blockClasses,
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		...frappeUIContent,
		"../../../frappe/ui/src/**/*.{vue,js,ts,jsx,tsx}",
		...exportedAppContent,
	],
	theme: {
		extend: {},
	},
	plugins: [
		plugin(function ({ addBase, addUtilities }) {
			// the canvas has its own theme, so a light frame can sit inside the dark editor
			addBase({
				"[data-theme]": { color: "CanvasText" },
				'[data-theme="dark"] [data-theme="light"]': { ...cssVariables.light, colorScheme: "light" },
			})
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
