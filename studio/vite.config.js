import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import path from "path"
import { defineConfig } from "vite"
import { getViteDevServerPort } from "./vite/utils"
import sharedDependencyResolver from "./vite/sharedDependencyResolver"

const viteDevServerPort = getViteDevServerPort()

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
		origin: `http://127.0.0.1:${viteDevServerPort}`,
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
		sharedDependencyResolver(path.resolve(__dirname, "..")),
	],
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
		},
	},
	build: {
		rolldownOptions: {
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
