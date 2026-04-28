import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import path from "path"
import { defineConfig } from "vite"

const STUDIO_ROOT = path.resolve(__dirname, "..")

/**
 * Vite plugin to redirect shared dependency imports from custom Vue components
 * (files outside the Studio project) to Studio's own installations.
 *
 * These are singleton deps (vue, vue-router, frappe-ui) that must resolve from
 * Studio to avoid duplicate instances. App-specific deps
 * resolve normally from the app's own node_modules.
 */
const STUDIO_SHARED_DEPS = ["vue", "vue-router", "frappe-ui"]

function studioDepsResolver() {
	return {
		name: "studio-deps-resolver",
		enforce: "pre",
		async resolveId(source, importer, options) {
			// Only intercept shared deps
			if (!STUDIO_SHARED_DEPS.some((dep) => source === dep || source.startsWith(dep + "/"))) return null
			// Only intercept if the importer is outside Studio's project
			if (!importer || importer.startsWith(STUDIO_ROOT)) return null

			// Re-resolve from Studio's project root so Vite finds the right copy
			const resolved = await this.resolve(source, path.join(STUDIO_ROOT, "frontend", "_virtual.js"), {
				...options,
				skipSelf: true,
			})
			return resolved
		},
	}
}

// https://vitejs.dev/config/
export default defineConfig({
	define: {
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
		__VUE_PROD_DEVTOOLS__: true,
	},
	server: {
		// explicitly set origin of generated assets (images, fonts, etc) during development.
		// Required for the app renderer running on webserver port
		// https://vite.dev/guide/backend-integration
		origin: "http://127.0.0.1:8086",
		allowedHosts: true,
		// Allow cross-origin requests from the renderer running on webserver port to Vite dev server.
		cors: true,
		fs: {
			// Allow serving files from other apps in the bench (for custom Vue components)
			allow: [path.resolve(__dirname, ".."), path.resolve(__dirname, "../../../")],
		},
		watch: {
			// unplugin-vue-components generates this file which causes HMR while building other studio apps
			ignored: ["**/components.d.ts", "**/auto-imports.d.ts"],
		},
	},
	plugins: [
		frappeui({
			frappeProxy: true,
			lucideIcons: true,
			buildConfig: false,
			jinjaBootData: false,
		}),
		vue(),
		// Redirect frappe-ui imports from custom Vue components (outside Studio's project)
		// to Studio's copy, so they don't resolve to a different/incomplete installation.
		studioDepsResolver(),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
		},
	},
	build: {
		rollupOptions: {
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
})
