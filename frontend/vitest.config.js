// The test runner. Separate from `vite.config.js`, which reads the `manifest.json` that
// `bench build` generates and a clean clone lacks.
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import contributions from "./plugin/contributions.js";

// The manifest is stated inline: frappe's own item renderers are contributions, and a
// test that mocked the virtual module would exercise the mock.
const manifest = [
	{ app: "frappe", source_dir: fileURLToPath(new URL("../frappe", import.meta.url)) },
];

export default defineConfig({
	plugins: [
		// Only for `~icons/*`; frappe-ui's own components import the lucide virtual modules.
		...frappeui({ lucideIcons: true }),
		vue(),
		contributions(
			manifest,
			manifest.map((entry) => entry.source_dir)
		),
	],
	resolve: {
		alias: {
			"@": fileURLToPath(new URL("./src", import.meta.url)),
			// The surface a contributed file imports from; the framework's renderers are contributed files.
			"@shell": fileURLToPath(new URL("./src/public.ts", import.meta.url)),
		},
		// `@framework/ui` is linked in as raw source and must resolve its imports in this tree.
		preserveSymlinks: true,
	},
	// No postcss: `tailwind.config.js` reads `manifest.json` at module scope, and a frappe-ui
	// `<style>` block would reach it through `vite:css`. An empty object overrides, not merges.
	css: { postcss: {} },
	test: {
		globals: true,
		environment: "happy-dom",
		include: ["src/**/tests/*.test.ts"],
		server: {
			deps: {
				// frappe-ui imports extensionless; externalised as native Node ESM that fails, and
				// inlining hands it to vite's resolver.
				inline: ["frappe-ui"],
			},
		},
	},
	server: {
		// `@framework/ui` is a sibling of this directory, outside the vite root.
		fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
	},
});
