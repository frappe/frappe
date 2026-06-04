/**
 * Bridge the Vite islands build into Frappe's asset machinery.
 *
 * The Vite islands pipeline (esbuild/build-islands.mjs) outputs hashed island
 * bundles into `sites/assets/<app>/dist`. Frappe's runtime resolves assets
 * through `assets.json` (logical key → hashed path) and caches it in Redis. The
 * esbuild pipeline keeps that file up to date for the bundles it builds; this
 * helper does the same for the Vite-built islands so
 * `frappe.require(["foo.bundle.js", "foo.bundle.css"])` resolves — islands keep
 * the `.bundle.` name so no runtime resolver change is needed.
 *
 * It deliberately reuses esbuild/utils.js (paths, redis) so both pipelines
 * share one assets.json and one cache-invalidation path.
 */
const fs = require("fs");
const path = require("path");
const { assets_path, sites_path, bench_path, get_redis_subscriber, log, log_warn } = require("./utils");

/**
 * Merge an island's built outputs into assets.json under stable logical keys,
 * then drop the Redis cache so Python re-reads it.
 *
 * @param {Object} relMap  Map of logical key → output path RELATIVE to the
 *                         app's dist dir, e.g.
 *                           { "foo.bundle.js":  "js/foo.bundle.<hash>.js",
 *                             "foo.bundle.css": "css/foo.bundle.<hash>.css" }
 * @param {string} app     App name (e.g. "frappe"); builds the public URL
 *                         prefix `/assets/<app>/dist`.
 * @returns {Promise<Object>}  Map of logical key → public asset URL written
 *                             (used for logging + live-reload).
 */
async function write_island_assets(relMap, app) {
	const dist_url_prefix = path.posix.join("/", "assets", app, "dist");
	const assets_json_path = path.resolve(assets_path, "assets.json");

	let existing = {};
	try {
		existing = JSON.parse(await fs.promises.readFile(assets_json_path, "utf-8"));
	} catch (_) {
		// Missing/empty → start fresh (esbuild build will also populate it).
	}

	const out = {};
	const superseded = [];
	for (const [key, rel] of Object.entries(relMap)) {
		const url = path.posix.join(dist_url_prefix, normalize_slashes(rel));
		out[key] = url;
		// Each island carries a content hash, so a rebuild produces a NEW
		// filename. Remember the previous one for this key to delete it (no
		// build-cleanup plugin runs for the Vite pipeline).
		if (existing[key] && existing[key] !== url) superseded.push(existing[key]);
	}

	const merged = Object.assign({}, existing, out);
	await fs.promises.mkdir(path.dirname(assets_json_path), { recursive: true });
	await fs.promises.writeFile(assets_json_path, JSON.stringify(merged, null, 4));
	await invalidate_assets_cache();
	await delete_superseded(superseded);
	return out;
}

function normalize_slashes(p) {
	return p.split(path.sep).join("/");
}

// Delete the previous hashed file (and its sourcemap) for a rebuilt island.
// URLs look like `/assets/<app>/dist/js/foo.island.<hash>.js`; the physical
// path resolves under sites/assets (a symlink to the app's public dir).
async function delete_superseded(urls) {
	for (const url of urls) {
		const file = path.join(sites_path, url);
		for (const target of [file, `${file}.map`]) {
			try {
				await fs.promises.unlink(target);
			} catch (_) {
				/* already gone */
			}
		}
	}
}

async function invalidate_assets_cache() {
	// Mirror esbuild.js: drop the Redis copy so Python re-reads assets.json.
	if (process.env.FRAPPE_DOCKER_BUILD) return;
	let client;
	try {
		client = get_redis_subscriber("redis_cache");
		await client.connect();
		await client.del("assets_json");
	} catch (_) {
		log_warn("island-assets: cannot connect to redis_cache to invalidate assets_json");
	} finally {
		// Close the connection so it doesn't keep Node's event loop alive — Vite
		// exits naturally (unlike esbuild.js, which calls process.exit()).
		await close_redis(client);
	}
}

async function close_redis(client) {
	if (!client) return;
	try {
		await client.quit();
	} catch (_) {
		try {
			await client.disconnect();
		} catch (_) {
			/* already closed / never connected */
		}
	}
}

// Publish a `build_event` on the same Redis channel ("events") esbuild's
// watcher uses, so the client's existing `frappe.realtime.on("build_event")`
// handler reacts identically (clear `_executed`, refetch assets_json, fire
// `frappe.hot_update`, show the success/error overlay).
async function publish_build_event(message) {
	let subscriber;
	try {
		subscriber = get_redis_subscriber("redis_queue");
		await subscriber.connect();
		await subscriber.publish("events", JSON.stringify({ event: "build_event", message }));
	} catch (_) {
		log_warn("island-assets: cannot connect to redis_queue for browser events");
	} finally {
		await close_redis(subscriber);
	}
}

/**
 * On a successful (re)build: same success payload esbuild emits. The client
 * busts `_executed` for the changed `.bundle.` files, refetches assets_json,
 * fires `frappe.hot_update` (→ island re-require + re-mount), and shows the
 * success toast (or full-reloads when `live_reload`).
 *
 * @param {string[]} changed_files  Asset URLs that changed this rebuild.
 * @param {boolean}  live_reload    Force a full Desk reload (esbuild `--live-reload`).
 */
async function notify_island_build({ changed_files = [], live_reload = false } = {}) {
	await publish_build_event({ success: true, changed_files, live_reload });
}

/**
 * On a build failure: mirror esbuild's error payload so the BuildError overlay
 * renders. The overlay reads `formatted[i]` (a string containing
 * ` > file:line:column`, made clickable), `error.errors[i].location`, and
 * `stack`. Maps a Vite/Rollup error into that shape.
 */
async function notify_island_error(err) {
	const loc = err?.loc || {};
	const location = {
		file: loc.file || err?.id || "unknown",
		line: loc.line || 0,
		column: loc.column || 0,
	};
	const where = `${location.file}:${location.line}:${location.column}`;
	const text = err?.message || String(err);
	// The codeframe (`err.frame`) goes after the ` > file:line:col` line so the
	// overlay's link-replacement (which looks for " > " + location) matches.
	const formatted = [`${text}\n > ${where}\n${err?.frame || ""}`];
	const stack = (err?.stack || text).replace(new RegExp(bench_path, "g"), "");

	await publish_build_event({
		error: { errors: [{ location, text }] },
		formatted,
		stack,
	});
}

module.exports = {
	write_island_assets,
	notify_island_build,
	notify_island_error,
	sites_path,
};
