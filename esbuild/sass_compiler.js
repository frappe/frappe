const path = require("path");
const fs = require("fs");
const { pathToFileURL } = require("url");
const { apps_path, app_list } = require("./utils");

// sass-embedded runs the native dart-sass compiler out of process, which is
// 2-4x faster than the pure-JS `sass` package. Fall back to `sass` on
// platforms without a prebuilt native binary; both expose the same modern
// compile API.
let sass;
try {
	sass = require("sass-embedded");
} catch (e) {
	sass = require("sass");
}

const app_paths = app_list.map((app) => path.resolve(apps_path, app));
const node_modules_paths = app_paths
	.map((app_path) => path.resolve(app_path, "node_modules"))
	.filter(fs.existsSync);

// Resolves webpack-style "~package/..." imports against every app's
// node_modules. Returns an extension-less file: URL; sass applies its own
// partial/extension/index resolution to whatever we return, so the probe only
// has to find which node_modules directory can satisfy the import.
const tilde_importer = {
	findFileUrl(url) {
		if (!url.startsWith("~")) return null;
		url = url.slice(1);
		for (const base of node_modules_paths) {
			const candidate = path.join(base, url);
			if (sass_target_exists(candidate)) {
				return pathToFileURL(candidate);
			}
		}
		return null;
	},
};

function sass_target_exists(base) {
	let stat = fs.statSync(base, { throwIfNoEntry: false });
	if (stat?.isFile()) return true;
	const dir = path.dirname(base);
	const name = path.basename(base);
	for (const prefix of ["", "_"]) {
		for (const ext of [".scss", ".sass", ".css"]) {
			if (fs.existsSync(path.join(dir, prefix + name + ext))) return true;
		}
	}
	if (stat?.isDirectory()) {
		for (const index of ["_index.scss", "_index.sass", "index.scss", "index.sass"]) {
			if (fs.existsSync(path.join(base, index))) return true;
		}
	}
	return false;
}

const sass_options = {
	loadPaths: [...node_modules_paths, ...app_paths],
	importers: [tilde_importer],
	quietDeps: true,
	// Frappe's stylesheets still use @import and pre-module built-ins;
	// migrating them is a separate project and the warning spam would drown
	// real problems. The feature-detect keeps the fallback `sass` (which may
	// predate these deprecation ids) working.
	silenceDeprecations: ["import", "global-builtin", "color-functions", "if-function"].filter(
		(id) => sass.deprecations?.[id]
	),
	sourceMap: true,
	sourceMapIncludeSources: true,
};

module.exports = { sass, sass_options, app_paths, node_modules_paths };
