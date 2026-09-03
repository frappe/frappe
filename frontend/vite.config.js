// The framework's one vite config; no app has another.

import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import contributions from "./plugin/contributions.js";
import oneTree from "./plugin/oneTree.js";
import { readManifest, readAllSourceDirs } from "./plugin/manifest.js";

// Assembled by Python, which also enforces singletons before vite is spawned.
const manifest = readManifest();
const allSourceDirs = readAllSourceDirs();

export default defineConfig(({ command }) => ({
	// One asset root for the bench: `/assets/frappe/` is a symlink to `frappe/public/`.
	// Build only; in dev the vite server serves the document itself.
	base: command === "build" ? "/assets/frappe/frontend/" : "/",

	plugins: [
		// `jinjaBootData`, `buildConfig` and `frontendRoute` stay off; see CLAUDE.md.
		...frappeui({
			lucideIcons: true,
			frappeProxy: true,
			jinjaBootData: false,
			buildConfig: false,
		}),
		vue(),
		contributions(manifest, allSourceDirs),
		oneTree(manifest),
	],
	resolve: {
		alias: {
			"@": fileURLToPath(new URL("./src", import.meta.url)),
			// The surface a contributed file imports from; another app's repo cannot use `@/`.
			"@shell": fileURLToPath(new URL("./src/public.ts", import.meta.url)),
		},
		// The framework's tree is the one tree: a symlinked package resolves its imports here.
		// Not `resolve.dedupe` and not an alias; see CLAUDE.md.
		preserveSymlinks: true,
	},
	build: {
		// One root for the bench; app identity rides in the chunk name.
		outDir: fileURLToPath(new URL("../frappe/public/frontend", import.meta.url)),
		// `bench build` overrides both, building to a staging directory and swapping it in;
		// these are the safe answer for a bare `yarn build`.
		emptyOutDir: false,
		sourcemap: true,
	},
	server: {
		// Every app's source is outside this root.
		fs: {
			allow: [
				fileURLToPath(new URL("..", import.meta.url)),
				...manifest.map((app) => app.source_dir),
			],
		},
	},
}));
