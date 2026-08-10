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
// Apps can be symlinked into apps/ from elsewhere (e.g. git worktrees under bench/.worktrees).
// For those, allow only the checkout's studio/ folder
const appSymlinkedSources = fs.readdirSync(appsDir).flatMap((entry) => {
	try {
		const realPath = fs.realpathSync(path.join(appsDir, entry))
		if (realPath.startsWith(appsDir + path.sep)) return []
		const studioDir = path.join(realPath, "studio")
		return fs.existsSync(studioDir) ? [studioDir] : []
	} catch {
		return []
	}
})

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
				// Allow serving custom Vue components and page scripts from any app, including ones
				// symlinked from outside apps/
				allow: [appsDir, ...appSymlinkedSources],
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
			// Pre-bundling frappe-ui splits its module-level state in two: toast()/dialog.*, so imperative toasts/dialogs never show in dev.
			exclude: ["frappe-ui"],
			include: [
				// CommonJS dep reached through the now-unbundled frappe-ui (tailwind/colorPalette.js)
				"tailwindcss/colors",
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
