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
 * A widget type's renderer sits beside its record the same way, and is built
 * with the pages:
 *
 *     apps/<app>/<app>/<module>/widget_type/<type>/<type>.island.js
 *
 * It is named `<app>.widget.<type folder>`. See island_name in
 * frappe/desk/widgets.py.
 */
export const WIDGET_ISLAND_INFIX = "widget";

/**
 * Every Frappe UI page and widget type renderer on the bench.
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
		const appPath = path.join(benchRoot, "apps", app, app);
		const islands = [
			...appPages(appPath).map((page) => ({
				...page,
				name: pageIslandName(app, page.name),
			})),
			...appWidgetTypes(appPath).map((type) => ({
				...type,
				name: `${app}.${WIDGET_ISLAND_INFIX}.${type.name}`,
			})),
		];
		for (const { name, dir, entry } of islands) {
			// One build now takes every app's pages, so two apps can reach the
			// same key. Last one wins would swap one page's island for another.
			const other = claimed.get(name);
			if (other)
				throw new Error(
					`island: two pages both claim "${name}":\n  ${other}\n  ${dir}\n` +
						"An island name is one bench-wide namespace. Rename one of the pages."
				);
			claimed.set(name, dir);

			entries[name] = entry;
			dirs.push(dir);
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

/** The widget types of one app that ship a renderer beside their record. */
function appWidgetTypes(appPath) {
	const types = [];
	for (const module of subdirectories(appPath)) {
		for (const dir of subdirectories(path.join(module, "widget_type"))) {
			const base = path.basename(dir);
			const entry = path.join(dir, `${base}.island.js`);
			if (fs.existsSync(entry)) types.push({ name: base, dir, entry });
		}
	}
	return types;
}

/**
 * One page folder, if a Frappe UI page lives in it.
 *
 * A page of any other type is not this build's, and a folder with no json at
 * all is not a page. Neither is a page that names an island, which the app's own
 * build registers.
 *
 * A Frappe UI page with no entry beside it is an error: the page is registered
 * and its route would show an unbuilt island.
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

	// The page names an island the app builds itself. There is no source here.
	if (doc.island) return null;

	const entry = path.join(dir, `${base}.island.js`);
	if (!fs.existsSync(entry))
		throw new Error(
			`island: the page "${doc.name}" is a ${PAGE_ISLAND_TYPE} page, but ` +
				`${base}.island.js is not beside its json in ${dir}. Save the ` +
				"Page again to write the starter files."
		);

	return { name: doc.name, dir, entry };
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
