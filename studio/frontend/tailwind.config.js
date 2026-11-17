import path from "node:path"
import { fileURLToPath } from "node:url"
import frappeUIPreset, { content as frappeUIContent } from "frappe-ui/tailwind"
import plugin from "tailwindcss/plugin"
import { cssVariables } from "frappe-ui/tailwind/tokens"
import { findStudioAppFolders } from "./vite/studioApps.js"

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
		// app builds replace this with only the icons their pages use (src/scripts/build.js)
		{ pattern: /^lucide-/ },
	],
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
