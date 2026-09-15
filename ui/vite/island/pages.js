// Page islands: what the framework build compiles, and how it names it.
//
// A `Page` of type "Frappe UI" is drawn by an island whose source sits beside
// the page's own json, in the app's python tree:
//
//     apps/<app>/<app>/<module>/page/<page>/<page>.json
//     apps/<app>/<app>/<module>/page/<page>/<page>.island.js
//     apps/<app>/<app>/<module>/page/<page>/<page>.vue
//
// Discovery reads the json rather than guessing from the folder. The folder is
// the scrubbed page name, `sales_dashboard`, and scrubbing is not reversible:
// the page could be `sales-dashboard` or `sales_dashboard`. The json carries
// the name the route uses, and the type that says the page is an island's.
//
// The name derived here has to equal `page_island_name` in
// frappe/utils/island.py. The build and the registry never meet, and a name
// they disagree on shows the reader an empty page with nothing to explain it.

import fs from "node:fs";
import path from "node:path";

/** The `Page.type` that means "an island draws this page". */
export const PAGE_ISLAND_TYPE = "Frappe UI";

/** Sits between the app and the page name. See frappe/utils/island.py. */
export const PAGE_ISLAND_INFIX = "page";

/**
 * The output directory, under the app's dist. Page islands are built by
 * framework and an app's own islands by the app, and a build owns every
 * assets.json key pointing into its output directory. Two directories, so the
 * two builds cannot drop each other's keys.
 */
export const PAGE_ISLAND_SUBDIR = "page-island";

/** The one name a page island is known by, on both sides of the build. */
export function pageIslandName(app, page) {
	return `${app}.${PAGE_ISLAND_INFIX}.${page}`;
}

/**
 * Every Frappe UI page on the bench.
 *
 * @param {string} benchRoot   the directory holding `apps/` and `sites/`
 * @param {string[]} apps      app names, as `sites/apps.txt` lists them
 * @returns {{entries: Object<string,string>, dirs: string[]}}
 *          entry name -> entry file, and the page folders they came from
 */
export function discoverPageIslands(benchRoot, apps) {
	const entries = {};
	const dirs = [];
	const claimed = new Map();

	for (const app of apps) {
		for (const page of appPages(path.join(benchRoot, "apps", app, app))) {
			const name = pageIslandName(app, page.name);

			// One build now takes every app's pages, so two apps can reach the
			// same key. Last one wins would swap one page's island for another.
			const other = claimed.get(name);
			if (other)
				throw new Error(
					`island: two pages both claim "${name}":\n  ${other}\n  ${page.dir}\n` +
						"An island name is one bench-wide namespace. Rename one of the pages."
				);
			claimed.set(name, page.dir);

			entries[name] = page.entry;
			dirs.push(page.dir);
		}
	}

	return { entries, dirs };
}

/** The Frappe UI pages of one app, found by walking its module folders. */
function appPages(appPath) {
	const pages = [];

	for (const module of subdirectories(appPath)) {
		const pageRoot = path.join(module, "page");
		if (!isDirectory(pageRoot)) continue;

		for (const dir of subdirectories(pageRoot)) {
			const page = readPage(dir);
			if (page) pages.push(page);
		}
	}

	return pages;
}

/**
 * One page folder, if a Frappe UI page lives in it.
 *
 * A page of any other type is not this build's, and a folder with no json at
 * all is not a page. A Frappe UI page with no entry beside it is an error: the
 * page is registered and its route would show an unbuilt island.
 */
function readPage(dir) {
	const base = path.basename(dir);
	const json = path.join(dir, `${base}.json`);
	if (!fs.existsSync(json)) return null;

	let doc;
	try {
		doc = JSON.parse(fs.readFileSync(json, "utf-8"));
	} catch (error) {
		throw new Error(`island: ${json} is not readable json: ${error.message}`);
	}

	if (doc.doctype !== "Page" || doc.type !== PAGE_ISLAND_TYPE) return null;

	const entry = path.join(dir, `${base}.island.js`);
	if (!fs.existsSync(entry))
		throw new Error(
			`island: the page "${doc.name}" is a ${PAGE_ISLAND_TYPE} page, but ` +
				`${base}.island.js is not beside its json in ${dir}. Save the ` +
				"Page again to write the starter files."
		);

	return { name: doc.name, dir, entry };
}

/**
 * Resolve a page island's bare imports against the framework toolchain.
 *
 * A page island's source sits in an app's python tree. The walk up from it can
 * reach `apps/node_modules` or the app's own frontend, and what it finds there
 * is not what this build compiles with. It also differs from bench to bench.
 *
 * Unenforced, so vite resolves first and this sees only what that walk missed.
 * The five shared singletons never reach here: `frameworkUI()` dedupes them, so
 * they resolve from the vite root already.
 *
 * @param {string[]} dirs  the page folders, from `discoverPageIslands`
 */
export function pageIslandResolver(dirs) {
	const roots = dirs.map((dir) => dir + path.sep);
	let toolchainImporter;

	return {
		name: "island-page-resolve",
		configResolved(config) {
			toolchainImporter = path.join(config.root, "index.html");
		},
		resolveId(source, importer) {
			if (!importer || !roots.some((root) => importer.startsWith(root))) return null;
			if (/^[./]/.test(source) || path.isAbsolute(source)) return null;
			return this.resolve(source, toolchainImporter, { skipSelf: true });
		},
	};
}

function subdirectories(dir) {
	if (!isDirectory(dir)) return [];
	return fs
		.readdirSync(dir, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
		.map((entry) => path.join(dir, entry.name));
}

function isDirectory(dir) {
	return fs.existsSync(dir) && fs.statSync(dir).isDirectory();
}
