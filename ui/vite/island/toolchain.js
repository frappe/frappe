// The island toolchain: the dependencies framework's own island builds compile
// with, page islands and framework islands alike. It sits in
// `island-toolchain/` beside `ui/`. See
// ../../island/decisions/0013-framework-builds-page-islands.md.

import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/** The vite root of every framework island build. */
export const TOOLCHAIN_ROOT = path.resolve(here, "../../../island-toolchain");

/**
 * Bring the toolchain's node_modules up to its lockfile.
 *
 * Its dependencies are pinned in its own package.json and lockfile. Nothing else
 * installs them, so every build asks yarn's integrity check, and installs only
 * when node_modules no longer matches the lockfile. They are all devDependencies,
 * which yarn skips under NODE_ENV=production unless told otherwise. Exits the
 * process when the install fails.
 *
 * @param {string} [root]  the toolchain folder
 */
export function installToolchain(root = TOOLCHAIN_ROOT) {
	const flags = ["--production=false", "--cwd", root];
	const check = spawnSync("yarn", ["check", "--integrity", "--silent", ...flags], {
		stdio: "ignore",
	});
	if (check.status === 0) return;

	console.log(`[island] installing the island toolchain at ${root}`);
	const install = spawnSync("yarn", ["install", "--frozen-lockfile", ...flags], {
		stdio: "inherit",
	});
	if (install.status !== 0) {
		console.error(
			`[island] could not install the island toolchain at ${root}.\n` +
				`Run it once for this bench:\n\n    yarn install --production=false --cwd ${root}\n`
		);
		process.exit(1);
	}
}

/**
 * Resolve bare imports from island sources outside the toolchain against it.
 *
 * Such a source sits in an app's python tree. The walk up from it can reach
 * `apps/node_modules`, the app's own node_modules or its frontend, and what it
 * finds there is not what this build compiles with. It also differs from bench
 * to bench.
 *
 * Unenforced, so vite resolves first and this sees only what that walk missed.
 * The five shared singletons never reach here: `frameworkUI()` dedupes them, so
 * they resolve from the vite root already.
 *
 * @param {string[]} dirs  the folders the island sources sit in
 */
export function toolchainResolver(dirs) {
	const roots = dirs.map((dir) => dir + path.sep);
	let toolchainImporter;

	return {
		name: "island-toolchain-resolve",
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
