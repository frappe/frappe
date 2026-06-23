import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// Builds the AI panel as a single self-contained IIFE bundle + one CSS file,
// emitted into the app's public dir so the desk can load it directly via
// `app_include_js` / `app_include_css` (see flow/hooks.py). Real frappe-ui
// components are pulled from source (`frappe-ui/src/...`) and tree-shaken.
export default defineConfig({
	define: {
		"process.env.NODE_ENV": JSON.stringify("production"),
		__VUE_OPTIONS_API__: "true",
		__VUE_PROD_DEVTOOLS__: "false",
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: "false",
	},
	plugins: [vue()],
	resolve: {
		alias: [
			{ find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
			// frappe-ui's package `exports` map hides its source; alias it so we can import
			// individual components without dragging in the whole index (tiptap, echarts, …).
			{
				find: "frappe-ui/src",
				replacement: fileURLToPath(
					new URL("./node_modules/frappe-ui/src", import.meta.url)
				),
			},
		],
	},
	build: {
		outDir: fileURLToPath(new URL("../flow/public/flow_panel", import.meta.url)),
		emptyOutDir: true,
		cssCodeSplit: false,
		sourcemap: false,
		target: "es2017",
		lib: {
			entry: fileURLToPath(new URL("./src/main.js", import.meta.url)),
			formats: ["iife"],
			name: "FlowPanel",
			fileName: () => "flow_panel.js",
		},
		rollupOptions: {
			output: { assetFileNames: "flow_panel.[ext]" },
		},
	},
});
