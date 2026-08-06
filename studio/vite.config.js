import fs from "fs"
import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import path from "path"
import { defineConfig } from "vite"
import { getViteDevServerPort } from "./vite/utils"
import sharedDependencyResolver from "./vite/sharedDependencyResolver"
import studioFolderWatcher from "./vite/studioFolderWatcher"
import studioRootAlias from "./vite/studioRootAlias"
import frameworkUIAlias from "./vite/frameworkUIAlias"

const viteDevServerPort = getViteDevServerPort()
const appsDir = path.resolve(__dirname, "../../")

// @framework/ui (apps/frappe/ui) only exists on newer frappe (develop). On older
// frappe it's absent, so its vite plugin, aliases, and component imports must be
// skipped or the studio build breaks. This flag gates all of them.
const frameworkUIAvailable = fs.existsSync(path.resolve(appsDir, "frappe", "ui", "package.json"))
// Each exported studio app carries a tsconfig.json (for the @app/ alias). Ignore changes to these files to avoid unnecessary HMR reloads.
const isStudioAppTsconfig = (file) =>
	/^[^/]+\/studio\/[^/]+\/tsconfig\.json$/.test(path.relative(appsDir, file).replace(/\\/g, "/"))

// https://vitejs.dev/config/
export default defineConfig(async () => {
	// Only pull in @framework/ui's vite plugin + source aliases when it exists.
	const frameworkUIPlugins = frameworkUIAvailable ? [(await import("@framework/ui/vite")).default()] : []
	// When absent, alias @framework/ui/* to a stub so the dev server can resolve the
	// (dead-branch) imports in globals.ts. Production builds DCE them; the dev server
	// doesn't, so without this it errors "Failed to resolve import @framework/ui/...".
	const frameworkUIAliases = frameworkUIAvailable
		? frameworkUIAlias(appsDir)
		: [{ find: /^@framework\/ui(\/.*)?$/, replacement: path.resolve(__dirname, "src/stubs/frameworkUI.ts") }]

	return {
		define: {
			__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
			__VUE_PROD_DEVTOOLS__: true,
			__FRAMEWORK_UI_AVAILABLE__: JSON.stringify(frameworkUIAvailable),
		},
		server: {
			// explicitly set origin of generated assets (images, fonts, etc) during development.
			// Required for the app renderer running on webserver port
			// https://vite.dev/guide/backend-integration
			origin: `http://127.0.0.1:${viteDevServerPort}`,
			allowedHosts: true,
			// Allow cross-origin requests from the renderer running on webserver port to Vite dev server.
			cors: true,
			fs: {
				// Allow serving files from anywhere in the bench (for custom Vue components).
				// Bench root, not apps/: apps checked out as git worktrees (bench/.worktrees/<name>)
				// resolve outside apps/ and must still be importable.
				allow: [path.resolve(__dirname, "../../../")],
			},
			watch: {
				// unplugin-vue-components generates this file which causes HMR while building other studio apps
				ignored: ["**/components.d.ts", "**/auto-imports.d.ts", isStudioAppTsconfig],
			},
		},
		plugins: [
			vue(),
			frappeui({
				frappeProxy: true,
				lucideIcons: true,
				buildConfig: false,
				jinjaBootData: false,
			}),
			...frameworkUIPlugins,
			studioRootAlias(),
			sharedDependencyResolver(path.resolve(__dirname, "..")),
			studioFolderWatcher(appsDir),
		],
		resolve: {
			alias: [...frameworkUIAliases, { find: "@", replacement: path.resolve(__dirname, "src") }],
		},
		build: {
			rolldownOptions: {
				onwarn(warning, warn) {
					if (warning.code === "INVALID_ANNOTATION") return
					warn(warning)
				},
				input: {
					studio: path.resolve(__dirname, "index.html"),
					renderer: path.resolve(__dirname, "renderer.html"),
				},
			},
			outDir: `../studio/public/frontend`,
			emptyOutDir: true,
			target: "es2015",
			sourcemap: true,
			chunkSizeWarningLimit: 1000,
		},
		optimizeDeps: {
			include: [
				"feather-icons",
				"showdown",
				"engine.io-client",
				"highlight.js/lib/core",
				"interactjs",
				"debug",
			],
		},
	}
})
