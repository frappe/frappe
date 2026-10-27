// What an island build was made from, so a later build with the same inputs can
// reuse its output instead of compiling it again.
//
// The key covers the entries, the mode, the options that reach the output, the
// toolchain's lockfile, the preset's own source, and every file the last build
// read. A file inside a node_modules is covered by the nearest lockfile above it,
// or by its package's version, so the key can be checked on a bench whose
// packages are not installed, such as one that downloaded prebuilt assets. Paths
// are relative to the bench, for the same reason.
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

	const packages = stamp.packages ?? {};
	const reinstalled = Object.entries(packages).some(([dir, version]) => {
		const manifest = readJson(path.join(paths.benchRoot, dir, "package.json"));
		return manifest && manifest.version !== version;
	});
	if (reinstalled) return false;

	const key = inputsKey({
		...options,
		paths,
		root,
		entries,
		production,
		files: stamp.files,
		packages,
	});
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
	const { files, packages } = sourceFiles(paths.benchRoot, context.root, moduleIds);
	const production = context.mode === "production";
	const key = inputsKey({ ...context, production, files, packages });
	fs.writeFileSync(
		path.join(paths.distDir, STAMP),
		JSON.stringify({ key, files, packages, assets })
	);
}

function inputsKey({ paths, root, entries, production, files, packages, ...options }) {
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
	for (const dir of Object.keys(packages).sort()) add(`package ${dir}`, packages[dir]);

	return hash.digest("hex");
}

/**
 * The bench-relative files and packages that decide the build's modules.
 *
 * A file inside a node_modules is never listed, since a bench that downloaded
 * prebuilt assets may not have it. It stands for the nearest lockfile above that
 * node_modules, or, where none exists, for its package's version. The toolchain's
 * packages are covered by its own lockfile already.
 */
function sourceFiles(benchRoot, root, moduleIds) {
	const toolchainModules = path.join(root, "node_modules") + path.sep;
	const files = new Set();
	const packages = {};
	for (const id of moduleIds) {
		const file = id.split("?")[0];
		if (!path.isAbsolute(file) || file.startsWith(toolchainModules)) continue;
		if (!fs.existsSync(file)) continue;

		const installed = installedPackage(file);
		if (!installed) {
			files.add(path.relative(benchRoot, file));
			continue;
		}
		const lockfile = nearestLockfile(installed.owner, benchRoot);
		if (lockfile) files.add(path.relative(benchRoot, lockfile));
		else {
			const manifest = readJson(path.join(installed.dir, "package.json"));
			packages[path.relative(benchRoot, installed.dir)] = manifest?.version ?? "";
		}
	}
	return { files: [...files].sort(), packages };
}

/** The outermost package a file sits in, and the folder whose node_modules holds it. */
function installedPackage(file) {
	const parts = file.split(path.sep);
	const index = parts.indexOf("node_modules");
	if (index === -1 || index + 1 >= parts.length - 1) return null;
	const nameParts = parts[index + 1].startsWith("@") ? 2 : 1;
	return {
		owner: parts.slice(0, index).join(path.sep),
		dir: parts.slice(0, index + 1 + nameParts).join(path.sep),
	};
}

const LOCKFILES = ["yarn.lock", "package-lock.json", "pnpm-lock.yaml"];

/** The first lockfile in `dir` or a folder above it, up to the bench root. */
function nearestLockfile(dir, benchRoot) {
	for (;;) {
		for (const name of LOCKFILES) {
			const lockfile = path.join(dir, name);
			if (fs.existsSync(lockfile)) return lockfile;
		}
		if (dir === benchRoot || path.dirname(dir) === dir) return null;
		dir = path.dirname(dir);
	}
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
