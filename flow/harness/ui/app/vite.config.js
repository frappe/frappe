import { existsSync } from "node:fs"
import { fileURLToPath, URL } from "node:url"

import vue from "@vitejs/plugin-vue"
import { lucideIcons } from "frappe-ui/vite"
import { defineConfig } from "vite"

// frappe-ui's `exports` map hides its source; alias it so individual
// components can be imported without dragging in the whole index (tiptap,
// echarts, …). Workspaces hoist to ui/node_modules; check both spots.
function frappeUISrc() {
	for (const candidate of ["./node_modules/frappe-ui/src", "../node_modules/frappe-ui/src"]) {
		const path = fileURLToPath(new URL(candidate, import.meta.url))
		if (existsSync(path)) return path
	}
	throw new Error("frappe-ui not installed")
}

// The daemon has no CORS middleware; in dev, Vite proxies API paths to it so
// the app talks same-origin. FLOW_DAEMON_URL overrides the target.
const daemon = process.env.FLOW_DAEMON_URL ?? "http://127.0.0.1:8787"
const proxy = Object.fromEntries(
	["/healthz", "/models", "/sessions", "/providers", "/fs"].map((path) => [
		path,
		{ target: daemon, changeOrigin: true },
	]),
)

export default defineConfig({
	// lucideIcons resolves frappe-ui's `~icons/lucide/*` imports (dialogs, pickers)
	plugins: [vue(), lucideIcons()],
	resolve: {
		alias: [{ find: "frappe-ui/src", replacement: frappeUISrc() }],
	},
	server: { host: "127.0.0.1", proxy },
	build: {
		// `flow web` serves this from inside the package, same-origin with the API
		outDir: fileURLToPath(new URL("../../src/flow/server/webui", import.meta.url)),
		emptyOutDir: true,
	},
})
