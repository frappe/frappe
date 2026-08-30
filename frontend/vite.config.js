// The framework's ONE vite config. There is no other in any app.
//
// It is worth reading beside `crm/frontend2/vite.config.js`, because everything that
// file works around exists only because it was one of N hosts: the __SOCKETIO_PORT__
// define reading common_site_config.json, the '@framework/ui' alias into a sibling
// repo, the optimizeDeps include/exclude fixing dual-instance prosemirror. In one
// module graph none of them has a cause.

import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import contributions from "./plugin/contributions.js";
import oneTree from "./plugin/oneTree.js";
import { readManifest, readAllSourceDirs } from "./plugin/manifest.js";

// Assembled by Python, because `app_prefix` is Python-only truth and a prefix cannot
// be globbed for. Singleton enforcement happens there too, at assembly, so a version
// conflict fails before vite is even spawned (#42069).
const manifest = readManifest();
const allSourceDirs = readAllSourceDirs();

export default defineConfig(({ command }) => ({
	// ONE asset root for the whole bench. `/assets/frappe/` is a symlink to
	// `frappe/public/`, so the built tree at `frappe/public/frontend/` is served from
	// here. Per-app asset URLs are lost and app identity rides in the chunk name
	// instead (#42069).
	//
	// Build only: in dev the framework's vite server serves the document itself, and a
	// prefixed base would make it ask for its own modules under a path it does not own.
	base: command === "build" ? "/assets/frappe/frontend/" : "/",

	plugins: [
		// frappe-ui's plugin, and WHICH options are off is the interesting part:
		//   - jinjaBootData: false -- the document carries no boot island. Boot is
		//     fetched in both environments, so an injected one would be a second producer
		//     that only ever ran in prod (#42070).
		//   - buildConfig: false -- it writes an app's outDir and index.html into a
		//     sibling app's `www/`. The framework owns its output now (#42069).
		//   - no frontendRoute -- `__FRONTEND_ROUTE__` is removed, not deprecated. One
		//     bundle, one router, and the prefix asked for at runtime (#42065).
		// What survives is icons, and the dev proxy.
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
			// The public surface for CONTRIBUTED files, which live in other apps' repos
			// and cannot use `@/…`. One module, `src/public.ts`, publishing the address
			// builders and nothing else -- see the header there for why a builder had to
			// be published at all.
			"@shell": fileURLToPath(new URL("./src/public.ts", import.meta.url)),
		},
		// The framework's tree is the ONE tree, so a package reached through a symlink
		// must resolve its imports here rather than beside its own source. `@framework/ui`
		// is raw source with no build step of its own, linked in and compiled in the same
		// module graph as the shell -- so "no build step" stops being a property of the
		// package and becomes a property of the bundle (#42071).
		//
		// Deliberately NOT `resolve.dedupe`, and not a per-package alias either. Dedupe
		// silently picks a winner, and aliasing a package to a directory bypasses its
		// `exports` map, which breaks every subpath import (`frappe-ui/code-editor`).
		// By the time vite runs, `enforce_singletons` has already established there is
		// one version of each shared library; this is what makes everything find it.
		preserveSymlinks: true,
	},
	build: {
		// ONE root, /assets/frappe/frontend/. Per-app asset URLs are lost; app identity
		// rides in the chunk name instead (#42069).
		outDir: fileURLToPath(new URL("../frappe/public/frontend", import.meta.url)),
		// `bench build` overrides both of these: it points --outDir at a staging
		// directory and passes --emptyOutDir, then swaps the result in only on success.
		// That is what gets BOTH properties at once -- a failed build leaves the served
		// assets untouched (crm/frontend2 does exactly the wrong thing here today), and a
		// successful one leaves no orphaned chunks behind, which plain `emptyOutDir: false`
		// does not: content hashes change every build and nothing ever removes the old
		// ones. These values are the safe answer for a bare `yarn build` run by hand.
		emptyOutDir: false,
		sourcemap: true,
	},
	server: {
		// Every app's source is outside this root, so all of them must be readable. This
		// generalises the single escape hatch crm/frontend2 already needs for one
		// sibling repo.
		fs: {
			allow: [
				fileURLToPath(new URL("..", import.meta.url)),
				...manifest.map((app) => app.source_dir),
			],
		},
	},
}));
