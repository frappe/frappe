import vue from "@vitejs/plugin-vue"
import frappeui from "frappe-ui/vite"
import path from "path"
import { defineConfig } from "vite"

// https://vitejs.dev/config/
export default defineConfig({
	define: {
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
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
				renderer: path.resolve(__dirname, "renderer.html"),
			},
			output: {
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
