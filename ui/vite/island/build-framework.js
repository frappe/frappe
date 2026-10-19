#!/usr/bin/env node
// The framework island build: the islands desk draws by default, such as
// `frappe.chart`.
//
//     node ui/vite/island/build-framework.js [--production] [--watch]
//
// Framework builds them like any app builds its own islands, into
// `dist/island/`, and apart from the page-island build. A broken page island
// cannot take these down with it. See
// ../../island/decisions/0015-framework-builds-its-own-islands.md.

import path from "node:path";

import { ISLAND_DIST_SUBDIR } from "./assets.js";
import { frameworkIslands } from "./framework.js";
import { buildIslands } from "./index.js";
import { TOOLCHAIN_ROOT as root, installToolchain, toolchainResolver } from "./toolchain.js";

const { entries, dirs } = frameworkIslands(path.dirname(root));

if (!Object.keys(entries).length) {
	console.log("[island] framework has no islands to build");
	process.exit(0);
}

installToolchain();

await buildIslands({
	app: "frappe",
	root,
	subdir: ISLAND_DIST_SUBDIR,
	entries,
	plugins: [toolchainResolver(dirs)],
	production: process.argv.includes("--production"),
	watch: process.argv.includes("--watch"),
});
