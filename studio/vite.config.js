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
	},
	plugins: [frappeui({ source: "^/(app|login|api|assets|files|pages)" }), vue()],
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
				// overwrite default .html entry for app renderer. Renderer file used from the frappe backend: /templates/generators/renderer.html
				renderer: path.resolve(__dirname, "src/renderer.ts"),
			},
			output: {
				// needed to access renderer.js in renderer.html script tag
				entryFileNames: "[name].js",
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
