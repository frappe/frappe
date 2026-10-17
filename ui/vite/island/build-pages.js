#!/usr/bin/env node
// The framework page-island build: one build for every Frappe UI page on the
// bench.
//
//     node ui/vite/island/build-pages.js [--production] [--watch]
//
// It is one build and not one per app, so every page island on the bench shares
// a chunk for vue and a chunk for frappe-ui, and the Tailwind discovery pass
// runs once instead of once per app. See
// ../../island/decisions/0013-framework-builds-page-islands.md.
//
// The vite root is `island-toolchain/` beside `ui/`, which exists only to hold
// the build's own dependencies. A page island therefore compiles against
// framework's frappe-ui and nothing of the app's. An island that needs the
// app's own code has outgrown this build and belongs in the app's frontend, as
// a normal island.

import fs from "node:fs";

import { benchPaths, findBenchRoot, loadFrappeBuildUtils, writeIslandAssets } from "./assets.js";
import { buildIslands } from "./index.js";
import { PAGE_ISLAND_SUBDIR, discoverPageIslands } from "./pages.js";
import { TOOLCHAIN_ROOT as root, installToolchain, toolchainResolver } from "./toolchain.js";

const benchRoot = findBenchRoot(root);

const utils = loadFrappeBuildUtils(benchRoot);
if (!utils) {
	console.error(`[island] no frappe at ${benchRoot}/apps/frappe, so no apps to read pages from`);
	process.exit(1);
}

const { entries, dirs } = discoverPageIslands(benchRoot, utils.app_list);

if (!Object.keys(entries).length) {
	// Nothing to build, but the last page may have just been deleted. This build
	// owns its output directory and every assets.json key pointing into it, so it
	// empties both here. Vite does that on a build, and there is no build to run.
	const paths = benchPaths(benchRoot, "frappe", PAGE_ISLAND_SUBDIR);
	await writeIslandAssets(paths, {});
	fs.rmSync(paths.distDir, { recursive: true, force: true });
	console.log("[island] no Frappe UI pages on this bench");
	process.exit(0);
}

installToolchain();

await buildIslands({
	// The output belongs to framework, which runs the build, and not to any one
	// app whose pages it happens to hold.
	app: "frappe",
	root,
	subdir: PAGE_ISLAND_SUBDIR,
	entries,
	plugins: [toolchainResolver(dirs)],
	production: process.argv.includes("--production"),
	watch: process.argv.includes("--watch"),
});
