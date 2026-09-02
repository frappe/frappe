// The runner for the record-page engine's unit tests.
//
// Deliberately NOT `vite.config.js`. That config reads `manifest.json`, which Python
// generates during `bench build` and .gitignore excludes -- so on a fresh clone, and on
// CI, it does not exist. This config takes only what the tests need, and states the
// manifest inline rather than reading one.
//
// The engine's tests used to run through `crm/frontend2`'s vitest, because that was the
// only place `frappe-ui` was installed. Now that the engine lives here, the runner and
// the tests are in the same package and the suite finally runs against the frappe-ui
// version the shell actually ships.
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import contributions from "./plugin/contributions.js";

// The contributions plugin IS wanted here, and it is not the reason this config is
// separate. What it must not do is read `manifest.json`, which `bench build` generates and
// .gitignore excludes -- so the manifest is written out here instead, with the one app the
// tests need: frappe's own eight navigation item renderers are contributions like any
// other (#42420), and a test that mocked the virtual module would exercise the mock rather
// than the door the whole design rests on.
const manifest = [
	{ app: "frappe", source_dir: fileURLToPath(new URL("../frappe", import.meta.url)) },
];

export default defineConfig({
	plugins: [
		// Only for `~icons/*`: frappe-ui's own components import the lucide virtual
		// modules, so without this any test that reaches a real field component fails
		// to resolve them. Every other option this plugin has belongs to the build.
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
			// The surface a CONTRIBUTED file imports from, and the framework's own renderers
			// are contributed files. Aliased in `vite.config.js` since #42068 and never here,
			// because until now nothing under test reached one.
			"@shell": fileURLToPath(new URL("./src/public.ts", import.meta.url)),
		},
		// Same reason as the build: `@framework/ui` is linked in as raw source and must
		// resolve its imports in this tree rather than beside its own.
		preserveSymlinks: true,
	},
	test: {
		globals: true,
		environment: "happy-dom",
		include: ["src/**/tests/*.test.ts"],
		server: {
			deps: {
				// frappe-ui's sources import extensionless (`from './resources'`). Vitest
				// externalizes node_modules by default and loads them as native Node ESM,
				// which requires exact extensions, so the import fails even though the
				// file is right there. Inlining hands it to vite's resolver, which does
				// extension resolution.
				inline: ["frappe-ui"],
			},
		},
	},
	server: {
		// `@framework/ui` is a sibling of this directory, outside the vite root.
		fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
	},
});
