import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import path from "path"
import { defineConfig } from "vite"

// https://vitejs.dev/config/
export default defineConfig({
	define: {
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
	},
	server: {
		// explicitly set origin of generated assets (images, fonts, etc) during development.
		// Required for the app renderer running on webserver port
		// https://vite.dev/guide/backend-integration
		origin: "http://127.0.0.1:8080",
		allowedHosts: true,
		watch: {
			// unplugin-vue-components generates this file which causes HMR while building other studio apps
			ignored: ["**/components.d.ts"],
		},
	},
	plugins: [
		frappeui({
			frappeProxy: true,
			lucideIcons: true,
		}),
		vue(),
	],
	resolve: {
		alias: {
			vue: "vue/dist/vue.esm-bundler.js",
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
		include: ["frappe-ui > feather-icons", "showdown", "engine.io-client"],
	},
})
