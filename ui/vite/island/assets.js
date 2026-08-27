// Bench paths and assets.json registration for the island build. Registration
// merges into the file, rewrites only the keys this build owns, and drops the
// Redis copy so python re-reads the file.

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

/** Suffixes that make an island key unmistakable to the module loader. */
export const ISLAND_JS_SUFFIX = ".island.js";
export const ISLAND_CSS_SUFFIX = ".island.css";

/** Where an app's islands live under its dist directory. */
export const ISLAND_DIST_SUBDIR = "island";

export const islandJsKey = (name) => `${name}${ISLAND_JS_SUFFIX}`;
export const islandCssKey = (name) => `${name}${ISLAND_CSS_SUFFIX}`;

/**
 * The bench root: the directory holding `sites/` and `apps/`. The preset always
 * runs inside a bench, so it discovers the root instead of taking it as an
 * option. `FRAPPE_BENCH_ROOT` overrides the walk, the same escape hatch frappe's
 * own esbuild/utils.js honours.
 *
 * @param {string} from  Directory to start walking up from (the vite root).
 */
export function findBenchRoot(from) {
	if (process.env.FRAPPE_BENCH_ROOT) return path.resolve(process.env.FRAPPE_BENCH_ROOT);

	let dir = path.resolve(from);
	for (;;) {
		if (fs.existsSync(path.join(dir, "sites")) && fs.existsSync(path.join(dir, "apps")))
			return dir;
		const parent = path.dirname(dir);
		if (parent === dir)
			throw new Error(
				`island: no bench root above ${from} (looked for a directory with ` +
					"sites/ and apps/). Set FRAPPE_BENCH_ROOT to point at one."
			);
		dir = parent;
	}
}

/** Every path the build writes to or reads from, derived from one bench root. */
export function benchPaths(benchRoot, app) {
	const sitesPath = path.join(benchRoot, "sites");
	const assetsPath = path.join(sitesPath, "assets");
	return {
		benchRoot,
		sitesPath,
		assetsPath,
		assetsJsonPath: path.join(assetsPath, "assets.json"),
		distDir: path.join(assetsPath, app, "dist", ISLAND_DIST_SUBDIR),
		urlPrefix: path.posix.join("/", "assets", app, "dist", ISLAND_DIST_SUBDIR),
	};
}

export function readAssetsJson(assetsJsonPath) {
	try {
		return JSON.parse(fs.readFileSync(assetsJsonPath, "utf-8"));
	} catch {
		// Missing or empty — the esbuild pipeline populates the rest.
		return {};
	}
}

/**
 * Register an app's built islands in assets.json.
 *
 * The app's island build owns every key that points into its own output
 * directory, and each build rewrites that whole set. An entry the app has
 * dropped loses its keys in the same build, instead of leaving dangling ones
 * behind. This leaves the keys of other apps and of the legacy pipeline
 * untouched.
 *
 * @param {Object} paths        from `benchPaths`
 * @param {Object<string,string>} relMap  asset key → path relative to the app's
 *                                        island output directory
 * @returns {Promise<Object<string,string>>}  asset key → public URL
 */
export async function writeIslandAssets(paths, relMap) {
	const ownPrefix = `${paths.urlPrefix}/`;
	const existing = readAssetsJson(paths.assetsJsonPath);

	const kept = Object.fromEntries(
		Object.entries(existing).filter(([, url]) => !url.startsWith(ownPrefix))
	);
	const written = Object.fromEntries(
		Object.entries(relMap).map(([key, rel]) => [
			key,
			path.posix.join(ownPrefix, rel.split(path.sep).join("/")),
		])
	);

	await fs.promises.mkdir(path.dirname(paths.assetsJsonPath), {
		recursive: true,
	});
	await fs.promises.writeFile(
		paths.assetsJsonPath,
		JSON.stringify({ ...kept, ...written }, null, 4)
	);
	await invalidateAssetsCache(paths);
	return written;
}

/**
 * Drop the Redis copy of assets.json, so the next page render sees the new
 * hashes. The connection details live in the site config, so this calls frappe's
 * own helper instead of deriving them again. A tree without frappe, such as a
 * test fixture, skips this step.
 */
async function invalidateAssetsCache(paths) {
	if (process.env.FRAPPE_DOCKER_BUILD) return;
	const utils = loadFrappeBuildUtils(paths.benchRoot);
	if (!utils) return;

	let client;
	try {
		client = utils.get_redis_subscriber("redis_cache");
		await client.connect();
		await client.del("assets_json");
	} catch {
		console.warn("[island] cannot reach redis_cache to invalidate assets_json");
	} finally {
		// Close the client. Vite exits on its own, unlike esbuild.js, which
		// calls process.exit().
		try {
			await client?.quit();
		} catch {
			try {
				await client?.disconnect();
			} catch {
				// never connected
			}
		}
	}
}

function loadFrappeBuildUtils(benchRoot) {
	const utilsPath = path.join(benchRoot, "apps/frappe/esbuild/utils.js");
	if (!fs.existsSync(utilsPath)) return null;
	try {
		return createRequire(import.meta.url)(utilsPath);
	} catch {
		return null;
	}
}

/**
 * Announce a finished (re)build.
 *
 * TODO(hot_update): in watch mode, publish frappe's `build_event` on the
 * `events` Redis channel, with the payload `{ success: true, changed_files,
 * live_reload }`. Desk then busts its asset cache and re-mounts the island. This
 * needs the publisher the esbuild watcher uses. Until then, a rebuild is visible
 * only on reload. The changed URLs this function receives are the payload.
 */
export function notifyRebuild(urls) {
	for (const [key, url] of Object.entries(urls)) console.log(`[island] ${key} → ${url}`);
}
