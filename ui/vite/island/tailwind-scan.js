// What Tailwind scans: the source files the bundle is made of.
//
// The island's stylesheet is the only one inside its shadow root, so it has to
// carry a rule for every class the bundle applies, the app's own and
// frappe-ui's alike. Both are modules of the same build, so both are here.
// ../../island/decisions/0003-tailwind-scans-the-module-list-not-a-glob.md

import fs from "node:fs";
import path from "node:path";

/**
 * Extensions that can hold a class usage, and so are worth a scan.
 *
 * A stylesheet in the graph defines rules rather than uses them, and an imported
 * `.json` or image is data. Scanning those finds nothing, and the check below
 * would report them as gaps no app can close.
 */
const SCANNED = new Set([".vue", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html"]);

/**
 * The source files a bundle was built from.
 *
 * The preset scans the stylesheet from this list. The list is what the bundle is
 * made of, so it cannot drift from the bundle.
 *
 * @param {Iterable<string>} modules  module ids from the bundle
 * @returns {string[]}  absolute paths, sorted
 */
export function bundleSources(modules) {
	const sources = new Set();
	for (const id of modules) {
		const file = sourceFile(id);
		if (file) sources.add(file);
	}
	return [...sources].sort();
}

/**
 * The bundle's source files that the stylesheet was not scanned from.
 *
 * @param {Object} options
 * @param {Iterable<string>} options.modules  module ids the bundle was built from
 * @param {Set<string>} options.scanned  what the stylesheet was scanned from
 * @param {(string|RegExp)[]} [options.allowUnscanned]  paths to pass over
 * @returns {string[]}  absolute paths, sorted
 */
export function unscannedSources({ modules, scanned, allowUnscanned = [] }) {
	return bundleSources(modules).filter(
		(file) => !scanned.has(file) && !allowed(file, allowUnscanned)
	);
}

/**
 * A real source file, or null for anything that cannot hold a class literal.
 *
 * Vite ids carry a query (`Button.vue?vue&type=script`), and virtual modules
 * start with a NUL. Paths are real paths on both sides of the comparison, or a
 * file reached through a symlink never matches the same file reached directly.
 * Rollup already reports real paths.
 */
function sourceFile(id) {
	if (!id || id.startsWith("\0")) return null;

	const candidate = path.resolve(id.split("?")[0]);
	if (!SCANNED.has(path.extname(candidate))) return null;
	if (!fs.existsSync(candidate)) return null;

	return fs.realpathSync(candidate);
}

function allowed(file, patterns) {
	return patterns.some((pattern) =>
		pattern instanceof RegExp ? pattern.test(file) : file.endsWith(pattern)
	);
}
