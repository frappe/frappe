// Framework's own islands: what desk draws by default, and where their source
// sits. An explicit table and not a scan, because these are a fixed part of
// framework, and a missing entry has to fail the build rather than vanish from it.
// See ../../island/decisions/0015-framework-builds-its-own-islands.md.

import path from "node:path";

/** Island name → entry file, relative to `apps/frappe`. */
export const FRAMEWORK_ISLANDS = {};

/**
 * @param {string} frappeRoot  the `apps/frappe` checkout
 * @returns {{entries: Object<string,string>, dirs: string[]}}
 *          entry name -> entry file, and the folders they sit in
 */
export function frameworkIslands(frappeRoot) {
	const entries = Object.fromEntries(
		Object.entries(FRAMEWORK_ISLANDS).map(([name, file]) => [
			name,
			path.join(frappeRoot, file),
		])
	);
	return { entries, dirs: Object.values(entries).map((file) => path.dirname(file)) };
}
