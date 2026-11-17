const fs = require("fs");

// a writer that died holding the lock frees it after this long
const STALE_LOCK_MS = 10000;
const RETRY_MS = 20;

/**
 * Read, change and write an assets.json under a lock.
 *
 * The esbuild watcher and each island watcher rewrite one assets.json, and a
 * write that lands between another's read and write drops that writer's keys.
 * `update` takes the parsed file and returns the whole new object.
 *
 * @returns {Promise<{ previous: Object, next: Object }>}
 */
async function update_assets_json(assets_json_path, update) {
	const lock = assets_json_path + ".lock";
	await acquire(lock);
	try {
		const previous = read(assets_json_path);
		const next = update(previous);
		fs.writeFileSync(assets_json_path, JSON.stringify(next, null, 4));
		return { previous, next };
	} finally {
		fs.rmSync(lock, { recursive: true, force: true });
	}
}

async function acquire(lock) {
	for (;;) {
		try {
			fs.mkdirSync(lock);
			return;
		} catch (error) {
			if (error.code !== "EEXIST") throw error;
		}
		if (is_stale(lock)) fs.rmSync(lock, { recursive: true, force: true });
		await new Promise((resolve) => setTimeout(resolve, RETRY_MS));
	}
}

function is_stale(lock) {
	try {
		return Date.now() - fs.statSync(lock).mtimeMs > STALE_LOCK_MS;
	} catch {
		return false;
	}
}

function read(assets_json_path) {
	let contents;
	try {
		contents = fs.readFileSync(assets_json_path, "utf-8");
	} catch (error) {
		if (error.code === "ENOENT") return {};
		throw error;
	}
	return JSON.parse(contents);
}

module.exports = { update_assets_json };
