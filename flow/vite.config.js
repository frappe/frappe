import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import { defineConfig } from "vite";

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

// The page is built from frontend/ into the app's public folder; its entry lands in
// www/flow/index.html, where Frappe renders the boot data into it. In dev, frappe-ui's
// proxy forwards API and asset paths to the bench (port 8000 → Vite on 8080).
export default defineConfig({
	root: here("./frontend"),
	plugins: [
		frappeui({
			frappeProxy: true,
			lucideIcons: true,
			jinjaBootData: true,
			buildConfig: {
				outDir: here("./flow/public/frontend"),
				emptyOutDir: true,
				indexHtmlPath: here("./flow/www/flow/index.html"),
				baseUrl: "/assets/flow/frontend/",
			},
		}),
		vue(),
	],
	resolve: {
		// frappe-ui's `exports` map hides its source; the core components import it by path
		alias: [{ find: "frappe-ui/src", replacement: here("./node_modules/frappe-ui/src") }],
		// @flow/ui-core is linked from harness/ui, which has its own node_modules: one Vue
		dedupe: ["vue", "vue-router", "frappe-ui"],
	},
	// keep one @codemirror/state for the code editor
	optimizeDeps: {
		exclude: [
			"frappe-ui",
			"@flow/ui-core",
			"@codemirror/lang-json",
			"@codemirror/lang-python",
			"@codemirror/lint",
		],
	},
	server: { fs: { allow: [here("."), here("./harness/ui/core")] } },
});
