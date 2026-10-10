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
// The vite root is `toolchain/`, which exists only to hold the build's own
// dependencies. A page island therefore compiles against framework's frappe-ui
// and nothing of the app's. An island that needs the app's own code has
// outgrown this build and belongs in the app's frontend, as a normal island.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { benchPaths, findBenchRoot, loadFrappeBuildUtils, writeIslandAssets } from "./assets.js";
import { buildIslands } from "./index.js";
import { PAGE_ISLAND_SUBDIR, discoverPageIslands, pageIslandResolver } from "./pages.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "toolchain");
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

// The toolchain's dependencies are pinned in its own package.json and lockfile.
// Nothing else installs them, so the first build on a bench does, or every
// Frappe UI page would show its unbuilt state. They are all devDependencies, which
// yarn skips under NODE_ENV=production unless told otherwise.
if (!fs.existsSync(path.join(root, "node_modules"))) {
	console.log(`[island] installing the page-island toolchain at ${root}`);
	const install = spawnSync(
		"yarn",
		["install", "--frozen-lockfile", "--production=false", "--cwd", root],
		{ stdio: "inherit" }
	);
	if (install.status !== 0) {
		console.error(
			`[island] could not install the page-island toolchain at ${root}.\n` +
				`Run it once for this bench:\n\n    yarn install --cwd ${root}\n`
		);
		process.exit(1);
	}
}

await buildIslands({
	// The output belongs to framework, which runs the build, and not to any one
	// app whose pages it happens to hold.
	app: "frappe",
	root,
	subdir: PAGE_ISLAND_SUBDIR,
	entries,
	plugins: [pageIslandResolver(dirs)],
	production: process.argv.includes("--production"),
	watch: process.argv.includes("--watch"),
});
