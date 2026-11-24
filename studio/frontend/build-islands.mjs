// Builds frappe.studio.component, the island that renders a global Studio component on desk.
// Output: sites/assets/frappe/dist/studio/, registered in assets.json.
import path from "node:path"

import { buildIslands } from "@framework/ui/vite/island"

import frameworkUIAlias from "./vite/frameworkUIAlias.js"
import lucideStaticAlias from "./vite/lucideStaticAlias.js"
import sharedDependencyResolver from "./vite/sharedDependencyResolver.js"

const root = import.meta.dirname
const appsDir = path.resolve(root, "../../../")

const aliases = {
	name: "studio-aliases",
	config: () => ({
		resolve: {
			alias: [
				// the mount contract is outside the `src` that frameworkUIAlias maps
				{
					find: /^@framework\/ui\/island$/,
					replacement: path.resolve(appsDir, "frappe/ui/island/index.js"),
				},
				...frameworkUIAlias(appsDir),
				lucideStaticAlias(root),
				{ find: "@", replacement: path.resolve(root, "src") },
			],
		},
	}),
}

await buildIslands({
	app: "frappe",
	root,
	// framework's own islands own frappe/dist/island
	subdir: "studio",
	entries: { "frappe.studio.component": "src/desk/component.island.ts" },
	// The island holds every block that a component can use, so that a site with no build
	// renders a component that a user makes there. It also holds every lucide icon class.
	budget: 4.5 * 1024 * 1024,
	plugins: [aliases, sharedDependencyResolver(root)],
	tailwindPlugins: [path.resolve(root, "tailwind/blockClassesPlugin.js")],
	production: process.argv.includes("--production"),
	watch: process.argv.includes("--watch"),
})
