// What an island build was made from, so a later build with the same inputs can
// reuse its output instead of compiling it again.
//
// The key covers the entries, the mode, the options that reach the output, the
// toolchain's lockfile, the preset's own source, and every file the last build
// read outside the toolchain's node_modules. Files inside it are covered by the
// lockfile instead, so the key can be checked on a bench whose toolchain is not
// installed yet, such as one that downloaded prebuilt assets. Paths are relative
// to the bench, for the same reason.
//
// The stamp sits inside the output directory, which vite empties on every build,
// so output and stamp always go away together.

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { benchPaths, findBenchRoot } from "./assets.js";

const STAMP = ".inputs.json";

const presetDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/**
 * Whether the output of the last build is still what these inputs would build,
 * and still registered in assets.json.
 *
 * Takes the options of `buildIslands`, and resolves them the same way, so both
 * sides agree on paths.
 */
export function islandsUnchanged(options) {
	const { app, subdir, production } = options;
	let root, entries;
	try {
		root = fs.realpathSync(options.root);
		entries = Object.fromEntries(
			Object.entries(options.entries).map(([name, file]) => [name, fs.realpathSync(file)])
		);
	} catch {
		return false;
	}

	const paths = benchPaths(findBenchRoot(root), app, subdir);
	const stamp = readJson(path.join(paths.distDir, STAMP));
	if (!stamp?.key || !Array.isArray(stamp.files) || !stamp.assets) return false;

	const key = inputsKey({ ...options, paths, root, entries, production, files: stamp.files });
	if (key !== stamp.key) return false;

	const registered = readJson(paths.assetsJsonPath) ?? {};
	return Object.entries(stamp.assets).every(
		([name, url]) => registered[name] === url && fs.existsSync(path.join(paths.sitesPath, url))
	);
}

/**
 * Record what this build read, beside its output.
 *
 * @param {Object} context      the build's `islandContext`
 * @param {Iterable<string>} moduleIds  every module id the build loaded
 * @param {Object<string,string>} assets  asset key → URL this build registered
 */
export function writeInputsStamp(context, moduleIds, assets) {
	const { paths } = context;
	const files = sourceFiles(paths.benchRoot, context.root, moduleIds);
	const key = inputsKey({ ...context, production: context.mode === "production", files });
	fs.writeFileSync(path.join(paths.distDir, STAMP), JSON.stringify({ key, files, assets }));
}

function inputsKey({ paths, root, entries, production, files, ...options }) {
	const hash = crypto.createHash("sha256");
	const add = (label, value) => {
		hash.update(`${label}\0`);
		hash.update(value);
		hash.update("\0");
	};

	add("mode", production ? "production" : "development");
	for (const name of Object.keys(entries).sort())
		add("entry", `${name}=${path.relative(paths.benchRoot, entries[name])}`);
	for (const option of ["tailwindPlugins", "forbiddenImports", "allowUnscanned"])
		add(option, (options[option] ?? []).map(String).join("\n"));

	const fixed = [
		path.join(root, "yarn.lock"),
		path.join(root, "package.json"),
		...presetFiles(),
	];
	for (const file of fixed) add(path.relative(paths.benchRoot, file), contents(file));
	for (const file of files) add(file, contents(path.join(paths.benchRoot, file)));

	return hash.digest("hex");
}

/** Module ids as bench-relative paths of real files outside the toolchain's node_modules. */
function sourceFiles(benchRoot, root, moduleIds) {
	const toolchainModules = path.join(root, "node_modules") + path.sep;
	const files = new Set();
	for (const id of moduleIds) {
		const file = id.split("?")[0];
		if (!path.isAbsolute(file) || file.startsWith(toolchainModules)) continue;
		if (!fs.existsSync(file)) continue;
		files.add(path.relative(benchRoot, file));
	}
	return [...files].sort();
}

/** The preset's own source: its output changes when this code does. */
function presetFiles() {
	const files = [];
	const walk = (dir) => {
		for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
			const file = path.join(dir, entry.name);
			if (entry.isDirectory()) {
				if (entry.name !== "tests") walk(file);
			} else if (entry.name.endsWith(".js")) files.push(file);
		}
	};
	walk(presetDir);
	return files.sort();
}

/** A file's bytes, or a marker when it is gone, so a deleted file changes the key. */
function contents(file) {
	try {
		return fs.readFileSync(file);
	} catch {
		return "\0missing";
	}
}

function readJson(file) {
	try {
		return JSON.parse(fs.readFileSync(file, "utf-8"));
	} catch {
		return null;
	}
}
